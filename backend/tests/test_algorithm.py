"""精确算法测试：上包络、有理边界、零长度接触、合并与并列责任。"""
from fractions import Fraction as F

from app.algorithm import ValidatedCurve, ValidatedInput, analyze as _analyze


def analyze(data):
    # 算法现在返回 AnalysisResult；这些用例只断言非选择区间。
    return _analyze(data).intervals


def curve(pid, pts):
    return ValidatedCurve(pid=pid, points=pts)


def make_input(upstream, downstream, lo, hi, margin=0):
    return ValidatedInput(
        lo=lo, hi=hi, margin=margin, upstream=upstream, downstream=downstream
    )


def test_all_safe_when_upstream_always_slower():
    # 上级恒 100us，下级最大恒 10us -> 差值 90 > 裕量 0，全窗安全。
    up = curve("U", [(1, 100), (10, 100)])
    d1 = curve("D1", [(1, 10), (10, 10)])
    d2 = curve("D2", [(1, 5), (10, 5)])
    assert analyze(make_input(up, [d1, d2], 1, 10)) == []


def test_single_crossing_gives_exact_rational_boundary():
    # U(x) = 11 - x，窗 [1,7]；包络 D1 恒 5。d(x) = 6 - x，裕量 0。
    # 非选择 {x >= 6} => 极大区间 [6,7]；端点 6 属于结果。
    up = curve("U", [(1, 10), (7, 4)])
    d1 = curve("D1", [(1, 5), (7, 5)])
    d2 = curve("D2", [(1, 1), (7, 1)])
    res = analyze(make_input(up, [d1, d2], 1, 7))
    assert len(res) == 1
    iv = res[0]
    assert iv.lo == F(6) and iv.hi == F(7)
    assert iv.responsible == "D1"
    assert iv.min_diff == F(-1)          # x=7：4 - 5
    assert iv.min_current == F(7)


def test_envelope_switch_responsibility_and_boundary():
    # U 恒 5；D1 恒 4，D2(x) = x（(1,1)->(10,10)）。
    # 包络在 x=4 处由 D1 切换到 D2。裕量 1：d<=1 覆盖整窗 [1,10]。
    up = curve("U", [(1, 5), (10, 5)])
    d1 = curve("D1", [(1, 4), (10, 4)])
    d2 = curve("D2", [(1, 1), (10, 10)])
    res = analyze(make_input(up, [d1, d2], 1, 10, margin=1))
    assert len(res) == 1
    assert (res[0].lo, res[0].hi) == (F(1), F(10))
    # 最小值在 x=10：d = 5 - 10 = -5，责任 D2。
    assert res[0].responsible == "D2"
    assert res[0].min_current == F(10)
    assert res[0].min_diff == F(-5)


def test_tangent_zero_length_contact_is_retained():
    # d 在内点 x=2 恰好等于裕量 1，两侧严格大于。
    # U 折线 (1,9),(2,6),(5,9)；D1 恒 5。左段 d=7-3x，右段 d=3x-5。
    d1 = curve("D1", [(1, 5), (5, 5)])
    d2 = curve("D2", [(1, 1), (5, 1)])
    up = curve("U", [(1, 9), (2, 6), (5, 9)])
    res = analyze(make_input(up, [d1, d2], 1, 5, margin=1))
    assert len(res) == 1
    assert res[0].lo == res[0].hi == F(2)
    assert res[0].min_diff == F(1)
    assert res[0].responsible == "D1"


def test_two_separate_bad_zones_do_not_merge():
    # U: (1,1),(3,10),(5,1)；包络恒 5，裕量 0。
    # 左段 d=4.5x-8.5 <=0 -> x<=17/9；右段 d=18.5-4.5x <=0 -> x>=37/9.
    d1 = curve("D1", [(1, 5), (5, 5)])
    d2 = curve("D2", [(1, 1), (5, 1)])
    up = curve("U", [(1, 1), (3, 10), (5, 1)])
    res = analyze(make_input(up, [d1, d2], 1, 5))
    assert len(res) == 2
    assert (res[0].lo, res[0].hi) == (F(1), F(17, 9))
    assert (res[1].lo, res[1].hi) == (F(37, 9), F(5))


def test_touching_intervals_merge_across_knot():
    # d=0 贯穿整窗（多段拼接），接触的闭区间合并为 [1,5]。
    up = curve("U", [(1, 5), (3, 5), (5, 5)])
    d1 = curve("D1", [(1, 5), (5, 5)])
    d2 = curve("D2", [(1, 1), (5, 1)])
    res = analyze(make_input(up, [d1, d2], 1, 5))
    assert len(res) == 1
    assert (res[0].lo, res[0].hi) == (F(1), F(5))


def test_tie_responsibility_lexicographic_on_equal_value():
    # 两下级全程等值，责任取 id 字典序（与列表顺序相反）。
    up = curve("UP", [(1, 5), (4, 5)])
    da = curve("ZZ", [(1, 5), (4, 5)])
    db = curve("AA", [(1, 5), (4, 5)])
    res = analyze(make_input(up, [da, db], 1, 4, margin=0))
    assert len(res) == 1
    assert res[0].responsible == "AA"


def test_tie_prefers_smallest_current():
    # 最小差值 -4 在平坦段 [1,2] 处处取得，应选最小电流 1。
    up = curve("U", [(1, 1), (2, 1), (4, 9)])
    d1 = curve("D1", [(1, 5), (4, 5)])
    d2 = curve("D2", [(1, 1), (4, 1)])
    res = analyze(make_input(up, [d1, d2], 1, 4))
    assert res[0].min_diff == F(-4)
    assert res[0].min_current == F(1)
    assert res[0].responsible == "D1"


def test_fractional_intersection_boundary_exact():
    # U 恒 7；D1(x)=2x 过 (1,2),(4,8)，交点 x=7/2。非选择 [7/2, 4]。
    up = curve("U", [(1, 7), (4, 7)])
    d1 = curve("D1", [(1, 2), (4, 8)])
    d2 = curve("D2", [(1, 1), (4, 1)])
    res = analyze(make_input(up, [d1, d2], 1, 4))
    assert len(res) == 1
    assert res[0].lo == F(7, 2)
    assert res[0].hi == F(4)


def test_margin_shifts_boundary():
    # U(x)=11-x，包络恒 5；裕量 2：d=6-x<=2 -> x>=4（而非 6）。
    up = curve("U", [(1, 10), (7, 4)])
    d1 = curve("D1", [(1, 5), (7, 5)])
    d2 = curve("D2", [(1, 1), (7, 1)])
    res = analyze(make_input(up, [d1, d2], 1, 7, margin=2))
    assert len(res) == 1
    assert res[0].lo == F(4)


def test_envelope_segments_switch_at_exact_intersection():
    # D1 恒 4，D2(x)=x（(1,1)->(10,10)）；包络应在 x=4 处切换责任。
    up = curve("U", [(1, 20), (10, 20)])
    d1 = curve("D1", [(1, 4), (10, 4)])
    d2 = curve("D2", [(1, 1), (10, 10)])
    result = _analyze(make_input(up, [d1, d2], 1, 10))
    env = result.envelope
    # 找到分界点 4，并验证两侧责任下级。
    boundaries = [s.lo for s in env] + [env[-1].hi]
    assert F(4) in boundaries
    left = next(s for s in env if s.hi == F(4))
    right = next(s for s in env if s.lo == F(4))
    assert left.pid == "D1"
    assert right.pid == "D2"
    # 切换点两侧包络时间都精确为 4。
    assert left.hi_time == F(4)
    assert right.lo_time == F(4)
    # 分段首尾恰好覆盖审查窗。
    assert env[0].lo == F(1) and env[-1].hi == F(10)


def test_zero_width_window_non_selective_point():
    # 审查窗退化为单点 x=4：U(4)=7，包络 D1(4)=5 -> d=2。
    # 裕量 2（含等号）=> 恰好在该点不选择，零长度区间 [4,4]。
    up = curve("U", [(1, 10), (7, 4)])
    d1 = curve("D1", [(1, 5), (7, 5)])
    d2 = curve("D2", [(1, 1), (7, 1)])
    result = _analyze(make_input(up, [d1, d2], 4, 4, margin=2))
    assert len(result.intervals) == 1
    iv = result.intervals[0]
    assert iv.lo == iv.hi == iv.min_current == F(4)
    assert iv.min_diff == F(2)
    assert iv.responsible == "D1"
    # 包络也是单点段。
    assert len(result.envelope) == 1
    assert result.envelope[0].lo == result.envelope[0].hi == F(4)


def test_zero_width_window_safe_point():
    # 同点 x=4，裕量 1：d=2 > 1，单点安全。
    up = curve("U", [(1, 10), (7, 4)])
    d1 = curve("D1", [(1, 5), (7, 5)])
    d2 = curve("D2", [(1, 1), (7, 1)])
    result = _analyze(make_input(up, [d1, d2], 4, 4, margin=1))
    assert result.intervals == []
    assert result.envelope[0].pid == "D1"


def test_zero_width_window_tie_responsibility():
    # x=3 处两下级等值，责任取字典序最小。
    up = curve("UP", [(1, 9), (5, 1)])
    da = curve("ZZ", [(1, 5), (5, 5)])
    db = curve("AA", [(1, 5), (5, 5)])
    result = _analyze(make_input(up, [da, db], 3, 3, margin=100))
    assert result.intervals[0].responsible == "AA"
