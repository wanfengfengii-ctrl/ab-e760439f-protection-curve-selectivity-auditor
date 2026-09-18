"""API 契约测试：响应形状、有理数边界字符串、整批拒绝与错误顺序。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def valid_payload():
    return {
        "window": {"start": 1000, "end": 5000},
        "margin": 0,
        "upstream": {
            "id": "QS-main",
            "points": [
                {"current": 500, "time": 10000},
                {"current": 6000, "time": 1000},
            ],
        },
        "downstream": [
            {
                "id": "QF-feeder-1",
                "points": [
                    {"current": 500, "time": 1000},
                    {"current": 6000, "time": 6000},
                ],
            },
            {
                "id": "QF-feeder-2",
                "points": [
                    {"current": 500, "time": 2000},
                    {"current": 6000, "time": 1500},
                ],
            },
        ],
    }


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_valid_fail_returns_exact_rational_strings():
    resp = client.post("/api/review", json=valid_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "fail"
    assert body["intervals"] == [
        {
            "start": "28250/7",
            "end": "5000",
            "min_current": "5000",
            "min_diff": "-27000/11",
            "responsible": "QF-feeder-1",
        }
    ]


def test_valid_pass():
    payload = valid_payload()
    payload["margin"] = 0
    payload["upstream"] = {
        "id": "QS-main",
        "points": [
            {"current": 500, "time": 100000},
            {"current": 6000, "time": 100000},
        ],
    }
    resp = client.post("/api/review", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"verdict": "pass", "intervals": []}


def test_batch_rejection_returns_all_errors_in_input_order():
    payload = {
        "window": {"start": 5000, "end": 1000},  # window_order
        "margin": -5,  # negative
        "upstream": {
            "id": "dup",
            "points": [{"current": 100, "time": 100}],  # too_few_points
        },
        "downstream": [
            {
                "id": "dup",  # duplicate_id
                "points": [
                    {"current": 100, "time": 100},
                    {"current": 100, "time": 50},  # not_strictly_increasing
                ],
            },
            {
                "id": "ok",
                "points": [
                    {"current": 0, "time": 100},  # not_positive
                    {"current": 200, "time": 100},
                ],
            },
        ],
    }
    resp = client.post("/api/review", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert [(e["path"], e["code"]) for e in errors] == [
        ("window", "window_order"),
        ("margin", "negative"),
        ("upstream.points", "too_few_points"),
        ("downstream[0].id", "duplicate_id"),
        ("downstream[0].points[1].current", "not_strictly_increasing"),
        ("downstream[1].points[0].current", "not_positive"),
    ]


def test_insufficient_coverage_rejected():
    payload = valid_payload()
    payload["downstream"][0]["points"] = [
        {"current": 2000, "time": 1000},
        {"current": 6000, "time": 6000},
    ]
    resp = client.post("/api/review", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert [(e["path"], e["code"]) for e in errors] == [
        ("downstream[0].points", "insufficient_coverage")
    ]


def test_too_few_downstream_rejected():
    payload = valid_payload()
    payload["downstream"] = payload["downstream"][:1]
    resp = client.post("/api/review", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert [(e["path"], e["code"]) for e in errors] == [
        ("downstream", "too_few_downstream")
    ]


def test_non_integer_and_bool_rejected():
    payload = valid_payload()
    payload["margin"] = True  # bool 不是合法整数
    payload["window"]["start"] = 1000.5
    resp = client.post("/api/review", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert [(e["path"], e["code"]) for e in errors] == [
        ("window.start", "invalid_type"),
        ("margin", "invalid_type"),
    ]


def test_malformed_json_rejected():
    resp = client.post(
        "/api/review",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert len(errors) == 1
    assert errors[0]["code"] == "invalid_json"


def test_non_object_body_rejected():
    resp = client.post("/api/review", json=[1, 2, 3])
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert errors[0]["code"] == "invalid_type"
