"""API 契约测试：健康检查、成功响应形状、整批 422 与错误位置。"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def valid_payload():
    return {
        "window": {"lo": 1, "hi": 7},
        "margin": 0,
        "upstream": {"id": "U", "points": [
            {"current": 1, "time": 10}, {"current": 7, "time": 4}
        ]},
        "downstream": [
            {"id": "D1", "points": [
                {"current": 1, "time": 5}, {"current": 7, "time": 5}
            ]},
            {"id": "D2", "points": [
                {"current": 1, "time": 1}, {"current": 7, "time": 1}
            ]},
        ],
    }


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_safe_response_shape():
    p = valid_payload()
    p["margin"] = 0
    p["upstream"]["points"] = [
        {"current": 1, "time": 100}, {"current": 7, "time": 100}
    ]
    r = client.post("/api/analyze", json=p)
    assert r.status_code == 200
    body = r.json()
    assert body["safe"] is True
    assert body["intervals"] == []
    assert body["window"] == {"lo": 1, "hi": 7}


def test_non_safe_exact_rational_boundaries():
    r = client.post("/api/analyze", json=valid_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["safe"] is False
    assert len(body["intervals"]) == 1
    iv = body["intervals"][0]
    # d = 6 - x <= 0 -> x >= 6
    assert iv["lo"] == {"num": 6, "den": 1}
    assert iv["hi"] == {"num": 7, "den": 1}
    assert iv["responsible"] == "D1"
    assert iv["min_diff"] == {"num": -1, "den": 1}
    assert iv["min_current"] == {"num": 7, "den": 1}


def test_fractional_boundary_serialized_reduced():
    # U 恒 7；D1=2x，交点 x=7/2。
    p = valid_payload()
    p["upstream"]["points"] = [
        {"current": 1, "time": 7}, {"current": 4, "time": 7}
    ]
    p["window"] = {"lo": 1, "hi": 4}
    p["downstream"][0]["points"] = [
        {"current": 1, "time": 2}, {"current": 4, "time": 8}
    ]
    r = client.post("/api/analyze", json=p)
    body = r.json()
    iv = body["intervals"][0]
    assert iv["lo"] == {"num": 7, "den": 2}


def test_zero_width_window_single_point():
    # 单点审查窗 lo=hi=4，裕量 2：d=2 <= 2 -> 零长度区间 [4,4]。
    p = valid_payload()
    p["window"] = {"lo": 4, "hi": 4}
    p["margin"] = 2
    r = client.post("/api/analyze", json=p)
    assert r.status_code == 200
    body = r.json()
    assert body["safe"] is False
    iv = body["intervals"][0]
    assert iv["lo"] == iv["hi"] == {"num": 4, "den": 1}
    assert iv["min_diff"] == {"num": 2, "den": 1}
    assert iv["responsible"] == "D1"
    assert body["envelope"][0]["lo"] == body["envelope"][0]["hi"] == {"num": 4, "den": 1}


def test_envelope_field_present_and_connected():
    r = client.post("/api/analyze", json=valid_payload())
    body = r.json()
    assert body["envelope"], "必须返回上包络分段"
    # 相邻段首尾相接，整体恰好覆盖审查窗 [1,7]。
    assert body["envelope"][0]["lo"] == {"num": 1, "den": 1}
    assert body["envelope"][-1]["hi"] == {"num": 7, "den": 1}
    p = valid_payload()
    p["margin"] = -5
    p["downstream"][0]["points"][0]["current"] = 0
    r = client.post("/api/analyze", json=p)
    assert r.status_code == 422
    errors = r.json()["errors"]
    paths = [tuple(e["path"]) for e in errors]
    assert ("margin",) in paths
    assert ("downstream", 0, "points", 0, "current") in paths
    assert all("message" in e for e in errors)


def test_malformed_json_returns_400():
    r = client.post(
        "/api/analyze",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 400
    assert "errors" in r.json()


def test_json_non_object_returns_400():
    r = client.post("/api/analyze", json=[1, 2, 3])
    assert r.status_code == 400
