"""一次性验收服务：对运行中的 api 与 web 做端到端断言。

通过环境变量 API_BASE / WEB_BASE 指向被测服务，
在 docker compose 中默认为 http://api:8000 与 http://web:80。
全部断言使用精确的约分有理数字符串，不接受浮点近似。
"""

import os

import httpx

API_BASE = os.environ.get("API_BASE", "http://api:8000")
WEB_BASE = os.environ.get("WEB_BASE", "http://web:80")
TIMEOUT = httpx.Timeout(10.0)


def post_review(payload: dict) -> httpx.Response:
    return httpx.post(f"{API_BASE}/api/review", json=payload, timeout=TIMEOUT)


def test_api_health():
    resp = httpx.get(f"{API_BASE}/api/health", timeout=TIMEOUT)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_fractional_boundary_is_exact():
    payload = {
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
    resp = post_review(payload)
    assert resp.status_code == 200
    assert resp.json() == {
        "verdict": "fail",
        "intervals": [
            {
                "start": "28250/7",
                "end": "5000",
                "min_current": "5000",
                "min_diff": "-27000/11",
                "responsible": "QF-feeder-1",
            }
        ],
    }


def test_zero_length_contact_preserved():
    payload = {
        "window": {"start": 1000, "end": 3000},
        "margin": 300,
        "upstream": {
            "id": "QS-main",
            "points": [
                {"current": 500, "time": 3000},
                {"current": 2000, "time": 1500},
                {"current": 4000, "time": 3000},
            ],
        },
        "downstream": [
            {
                "id": "feeder-lo",
                "points": [
                    {"current": 500, "time": 1000},
                    {"current": 4000, "time": 1000},
                ],
            },
            {
                "id": "feeder-hi",
                "points": [
                    {"current": 500, "time": 1200},
                    {"current": 4000, "time": 1200},
                ],
            },
        ],
    }
    resp = post_review(payload)
    assert resp.status_code == 200
    assert resp.json()["intervals"] == [
        {
            "start": "2000",
            "end": "2000",
            "min_current": "2000",
            "min_diff": "300",
            "responsible": "feeder-hi",
        }
    ]


def test_touching_intervals_merge():
    payload = {
        "window": {"start": 1000, "end": 3000},
        "margin": 300,
        "upstream": {
            "id": "QS-main",
            "points": [
                {"current": 500, "time": 3000},
                {"current": 1500, "time": 1000},
                {"current": 2000, "time": 1500},
                {"current": 2500, "time": 1000},
                {"current": 4000, "time": 3000},
            ],
        },
        "downstream": [
            {
                "id": "feeder-lo",
                "points": [
                    {"current": 500, "time": 1000},
                    {"current": 4000, "time": 1000},
                ],
            },
            {
                "id": "feeder-hi",
                "points": [
                    {"current": 500, "time": 1200},
                    {"current": 4000, "time": 1200},
                ],
            },
        ],
    }
    resp = post_review(payload)
    assert resp.status_code == 200
    assert resp.json()["intervals"] == [
        {
            "start": "1250",
            "end": "2875",
            "min_current": "1500",
            "min_diff": "-200",
            "responsible": "feeder-hi",
        }
    ]


def test_pass_verdict():
    payload = {
        "window": {"start": 1000, "end": 3000},
        "margin": 500,
        "upstream": {
            "id": "QS-main",
            "points": [
                {"current": 500, "time": 100000},
                {"current": 4000, "time": 100000},
            ],
        },
        "downstream": [
            {
                "id": "feeder-hi",
                "points": [
                    {"current": 500, "time": 1200},
                    {"current": 4000, "time": 1200},
                ],
            },
            {
                "id": "feeder-lo",
                "points": [
                    {"current": 500, "time": 1100},
                    {"current": 4000, "time": 1100},
                ],
            },
        ],
    }
    resp = post_review(payload)
    assert resp.status_code == 200
    assert resp.json() == {"verdict": "pass", "intervals": []}


def test_batch_rejection_all_errors_in_order():
    payload = {
        "window": {"start": 5000, "end": 1000},
        "margin": -5,
        "upstream": {"id": "dup", "points": [{"current": 100, "time": 100}]},
        "downstream": [
            {
                "id": "dup",
                "points": [
                    {"current": 100, "time": 100},
                    {"current": 100, "time": 50},
                ],
            },
            {
                "id": "ok",
                "points": [
                    {"current": 0, "time": 100},
                    {"current": 200, "time": 100},
                ],
            },
        ],
    }
    resp = post_review(payload)
    assert resp.status_code == 422
    assert [(e["path"], e["code"]) for e in resp.json()["errors"]] == [
        ("window", "window_order"),
        ("margin", "negative"),
        ("upstream.points", "too_few_points"),
        ("downstream[0].id", "duplicate_id"),
        ("downstream[0].points[1].current", "not_strictly_increasing"),
        ("downstream[1].points[0].current", "not_positive"),
    ]


def test_web_serves_index():
    resp = httpx.get(f"{WEB_BASE}/", timeout=TIMEOUT)
    assert resp.status_code == 200
    assert 'id="root"' in resp.text


def test_web_proxies_api():
    resp = httpx.get(f"{WEB_BASE}/api/health", timeout=TIMEOUT)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
