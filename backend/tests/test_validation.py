"""整批校验测试：错误一次性、按位置稳定、重复标识、覆盖不足等。"""
import pytest

from app.validation import ValidationError, validate


def valid_payload(**over):
    p = {
        "window": {"lo": 1, "hi": 10},
        "margin": 0,
        "upstream": {"id": "U", "points": [
            {"current": 1, "time": 100}, {"current": 10, "time": 100}
        ]},
        "downstream": [
            {"id": "D1", "points": [
                {"current": 1, "time": 10}, {"current": 10, "time": 10}
            ]},
            {"id": "D2", "points": [
                {"current": 1, "time": 5}, {"current": 10, "time": 5}
            ]},
        ],
    }
    p.update(over)
    return p


def paths(errors):
    return [tuple(e["path"]) for e in errors]


def test_valid_payload_passes():
    data = validate(valid_payload())
    assert data.upstream.pid == "U"
    assert len(data.downstream) == 2


def test_duplicate_ids_rejected():
    p = valid_payload()
    p["downstream"][1]["id"] = "D1"
    with pytest.raises(ValidationError) as ei:
        validate(p)
    assert ("downstream", 1, "id") in paths(ei.value.errors)


def test_upstream_duplicate_id_rejected():
    p = valid_payload()
    p["upstream"]["id"] = "D1"
    with pytest.raises(ValidationError) as ei:
        validate(p)
    # upstream 先出现；冲突标记在其后的同标识下级处（按输入位置稳定）。
    assert ("downstream", 0, "id") in paths(ei.value.errors)


def test_non_positive_current_and_time_rejected():
    p = valid_payload()
    p["downstream"][0]["points"][0]["current"] = 0
    p["downstream"][0]["points"][1]["time"] = -3
    with pytest.raises(ValidationError) as ei:
        validate(p)
    got = paths(ei.value.errors)
    assert ("downstream", 0, "points", 0, "current") in got
    assert ("downstream", 0, "points", 1, "time") in got


def test_bool_is_not_a_valid_integer():
    p = valid_payload()
    p["window"]["lo"] = True
    p["margin"] = False
    with pytest.raises(ValidationError) as ei:
        validate(p)
    got = paths(ei.value.errors)
    assert ("window", "lo") in got
    assert ("margin",) in got


def test_too_few_points_rejected():
    p = valid_payload()
    p["upstream"]["points"] = [{"current": 1, "time": 5}]
    with pytest.raises(ValidationError) as ei:
        validate(p)
    assert ("upstream", "points") in paths(ei.value.errors)


def test_non_increasing_current_rejected():
    p = valid_payload()
    p["downstream"][1]["points"] = [
        {"current": 5, "time": 5}, {"current": 5, "time": 6}
    ]
    with pytest.raises(ValidationError) as ei:
        validate(p)
    assert ("downstream", 1, "points", 1, "current") in paths(ei.value.errors)


def test_insufficient_coverage_rejected():
    p = valid_payload()
    # 首折点电流 > 窗下界。
    p["downstream"][0]["points"] = [
        {"current": 3, "time": 5}, {"current": 10, "time": 5}
    ]
    with pytest.raises(ValidationError) as ei:
        validate(p)
    assert ("downstream", 0, "points") in paths(ei.value.errors)


def test_insufficient_upper_coverage_rejected():
    p = valid_payload()
    p["upstream"]["points"] = [
        {"current": 1, "time": 5}, {"current": 9, "time": 5}
    ]
    with pytest.raises(ValidationError) as ei:
        validate(p)
    assert ("upstream", "points") in paths(ei.value.errors)


def test_negative_margin_rejected_but_zero_allowed():
    p = valid_payload()
    p["margin"] = -1
    with pytest.raises(ValidationError):
        validate(p)
    validate(valid_payload(margin=0))


def test_fewer_than_two_downstream_rejected():
    p = valid_payload()
    p["downstream"] = p["downstream"][:1]
    with pytest.raises(ValidationError) as ei:
        validate(p)
    assert ("downstream",) in paths(ei.value.errors)


def test_multiple_errors_all_reported_and_stable_order():
    p = valid_payload()
    p["window"]["lo"] = 0
    p["margin"] = -1
    p["upstream"]["points"][0]["time"] = 0
    p["downstream"][0]["points"][0]["current"] = -2
    with pytest.raises(ValidationError) as ei:
        validate(p)
    got = paths(ei.value.errors)
    # 一次性返回 4 处错误，且顺序按输入位置稳定。
    assert len(got) == 4
    assert got == sorted(got, key=lambda t: _pos_key(t)) or got.index(
        ("window", "lo")
    ) < got.index(("downstream", 0, "points", 0, "current"))
    assert got.index(("window", "lo")) < got.index(("margin",))
    assert got.index(("margin",)) < got.index(
        ("upstream", "points", 0, "time")
    )
    assert got.index(("upstream", "points", 0, "time")) < got.index(
        ("downstream", 0, "points", 0, "current")
    )


def _pos_key(t):
    # 仅用于断言的辅助：把字符串片段映射为稳定秩。
    rank = {"window": 0, "margin": 1, "upstream": 2, "downstream": 3}
    return tuple(rank.get(x, x) if isinstance(x, str) else x for x in t)


def test_window_lo_greater_than_hi_rejected():
    p = valid_payload()
    p["window"] = {"lo": 10, "hi": 1}
    with pytest.raises(ValidationError):
        validate(p)


def test_empty_id_rejected():
    p = valid_payload()
    p["downstream"][0]["id"] = ""
    with pytest.raises(ValidationError):
        validate(p)
