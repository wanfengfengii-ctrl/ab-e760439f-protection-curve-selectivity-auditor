"""核心算法单元测试：全部断言使用精确有理数，不接受浮点近似。"""

from fractions import Fraction

from app.core import analyze
from app.validation import validate_payload


def run(payload: dict):
    errors, review_input = validate_payload(payload)
    assert errors == [], f"payload should be valid, got {errors}"
    assert review_input is not None
    return analyze(
        window_start=review_input.window_start,
        window_end=review_input.window_end,
        margin=review_input.margin,
        upstream=review_input.upstream,
        downstream=review_input.downstream,
    )


def make_payload(window, margin, upstream, downstream):
    return {
        "window": {"start": window[0], "end": window[1]},
        "margin": margin,
        "upstream": upstream,
        "downstream": downstream,
    }


def curve(device_id, points):
    return {"id": device_id, "points": [{"current": c, "time": t} for c, t in points]}


def test_fractional_boundary_exact():
    """上级与包络斜率不同，边界为分数 28250/7，必须精确命中。"""
    payload = make_payload(
        (1000, 5000),
        0,
        curve("QS-main", [(500, 10000), (6000, 1000)]),
        [
            curve("QF-feeder-1", [(500, 1000), (6000, 6000)]),
            curve("QF-feeder-2", [(500, 2000), (6000, 1500)]),
        ],
    )
    result = run(payload)
    assert result.verdict == "fail"
    assert len(result.intervals) == 1
    iv = result.intervals[0]
    assert iv.start == Fraction(28250, 7)
    assert iv.end == Fraction(5000)
    assert iv.min_current == Fraction(5000)
    assert iv.min_diff == Fraction(-27000, 11)
    assert iv.responsible == "QF-feeder-1"


def test_zero_length_contact_preserved():
    """差值仅在单点触及裕量：零长度区间必须保留，端点属于结果。"""
    payload = make_payload(
        (1000, 3000),
        300,
        curve("QS-main", [(500, 3000), (2000, 1500), (4000, 3000)]),
        [
            curve("feeder-lo", [(500, 1000), (4000, 1000)]),
            curve("feeder-hi", [(500, 1200), (4000, 1200)]),
        ],
    )
    result = run(payload)
    assert result.verdict == "fail"
    assert len(result.intervals) == 1
    iv = result.intervals[0]
    assert iv.start == Fraction(2000)
    assert iv.end == Fraction(2000)
    assert iv.min_current == Fraction(2000)
    assert iv.min_diff == Fraction(300)
    assert iv.responsible == "feeder-hi"


def test_touching_intervals_merge_and_min_current_tie():
    """W 形上级：相邻分段产生的接触闭区间合并为一个极大区间；
    最小差值在两个折点并列，取最小电流。"""
    payload = make_payload(
        (1000, 3000),
        300,
        curve(
            "QS-main",
            [(500, 3000), (1500, 1000), (2000, 1500), (2500, 1000), (4000, 3000)],
        ),
        [
            curve("feeder-lo", [(500, 1000), (4000, 1000)]),
            curve("feeder-hi", [(500, 1200), (4000, 1200)]),
        ],
    )
    result = run(payload)
    assert result.verdict == "fail"
    assert len(result.intervals) == 1
    iv = result.intervals[0]
    assert iv.start == Fraction(1250)
    assert iv.end == Fraction(2875)
    # 差值在 1500 与 2500 处同为 -200，取最小电流 1500
    assert iv.min_current == Fraction(1500)
    assert iv.min_diff == Fraction(-200)
    assert iv.responsible == "feeder-hi"


def test_disjoint_intervals_stay_separate():
    """同一 W 形上级、更小裕量：得到两个互不相接的极大区间。"""
    payload = make_payload(
        (1000, 3000),
        100,
        curve(
            "QS-main",
            [(500, 3000), (1500, 1000), (2000, 1500), (2500, 1000), (4000, 3000)],
        ),
        [
            curve("feeder-lo", [(500, 1000), (4000, 1000)]),
            curve("feeder-hi", [(500, 1200), (4000, 1200)]),
        ],
    )
    result = run(payload)
    assert result.verdict == "fail"
    assert [(iv.start, iv.end) for iv in result.intervals] == [
        (Fraction(1350), Fraction(1800)),
        (Fraction(2200), Fraction(2725)),
    ]
    assert [iv.min_current for iv in result.intervals] == [
        Fraction(1500),
        Fraction(2500),
    ]


def test_responsible_tie_breaks_by_identifier():
    """最小差值电流处两条下级并列包络，取标识字典序最小者。"""
    payload = make_payload(
        (1000, 3000),
        0,
        curve("QS-main", [(500, 1800), (4000, 1800)]),
        [
            curve("zeta", [(500, 1500), (2000, 2000), (4000, 1500)]),
            curve("alpha", [(500, 1000), (2000, 2000), (4000, 1000)]),
        ],
    )
    result = run(payload)
    assert result.verdict == "fail"
    assert len(result.intervals) == 1
    iv = result.intervals[0]
    assert iv.start == Fraction(1400)
    assert iv.end == Fraction(2800)
    assert iv.min_current == Fraction(2000)
    assert iv.min_diff == Fraction(-200)
    assert iv.responsible == "alpha"


def test_flat_difference_takes_smallest_current():
    """差值在全窗恒定：最小电流为窗口左端点。"""
    payload = make_payload(
        (1000, 3000),
        0,
        curve("QS-main", [(500, 1000), (4000, 1000)]),
        [
            curve("feeder-hi", [(500, 1200), (4000, 1200)]),
            curve("feeder-lo", [(500, 1100), (4000, 1100)]),
        ],
    )
    result = run(payload)
    assert result.verdict == "fail"
    assert len(result.intervals) == 1
    iv = result.intervals[0]
    assert iv.start == Fraction(1000)
    assert iv.end == Fraction(3000)
    assert iv.min_current == Fraction(1000)
    assert iv.min_diff == Fraction(-200)
    assert iv.responsible == "feeder-hi"


def test_difference_equal_margin_everywhere_is_violation():
    """差值恰好等于裕量（<= 判据）时全窗不选择，端点属于结果。"""
    payload = make_payload(
        (1000, 3000),
        300,
        curve("QS-main", [(500, 1500), (4000, 1500)]),
        [
            curve("feeder-hi", [(500, 1200), (4000, 1200)]),
            curve("feeder-lo", [(500, 1000), (4000, 1000)]),
        ],
    )
    result = run(payload)
    assert result.verdict == "fail"
    assert len(result.intervals) == 1
    iv = result.intervals[0]
    assert (iv.start, iv.end) == (Fraction(1000), Fraction(3000))
    assert iv.min_diff == Fraction(300)


def test_pass_when_upstream_clear():
    """上级全程高于包络加裕量：全窗安全，明确通过。"""
    payload = make_payload(
        (1000, 3000),
        500,
        curve("QS-main", [(500, 100000), (4000, 100000)]),
        [
            curve("feeder-hi", [(500, 1200), (4000, 1200)]),
            curve("feeder-lo", [(500, 1100), (4000, 1100)]),
        ],
    )
    result = run(payload)
    assert result.verdict == "pass"
    assert result.intervals == ()
