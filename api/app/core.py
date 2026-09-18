"""保护曲线选择性审查核心算法。

所有计算只使用整数与 fractions.Fraction（自动约分的有理数），
不使用任何浮点数，因此区间边界是精确的。

约定：
- 电流单位微安（µA），动作时间单位微秒（µs），输入均为正整数。
- 曲线为折点间按电流线性插值的分段线性函数。
- 包络为所有下级曲线逐点取最大（上包络）。
- 上级时间 - 包络时间 <= 裕量 即判定为不选择，区间闭，端点属于结果。
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Line:
    """直线 t = slope * current + intercept，系数为精确有理数。"""

    slope: Fraction
    intercept: Fraction

    def at(self, current: Fraction) -> Fraction:
        return self.slope * current + self.intercept


@dataclass(frozen=True)
class Curve:
    """一条保护曲线：折点 (current, time)，current 严格递增。"""

    device_id: str
    points: tuple[tuple[Fraction, Fraction], ...]

    def line_at(self, current: Fraction) -> Line:
        """返回覆盖给定电流的那一段折线所在的直线。"""
        currents = [p[0] for p in self.points]
        idx = bisect_right(currents, current) - 1
        idx = max(0, min(idx, len(self.points) - 2))
        (i0, t0), (i1, t1) = self.points[idx], self.points[idx + 1]
        slope = Fraction(t1 - t0, i1 - i0)
        return Line(slope=slope, intercept=t0 - slope * i0)

    def value_at(self, current: Fraction) -> Fraction:
        return self.line_at(current).at(current)


@dataclass(frozen=True)
class ViolationInterval:
    """一个极大的不选择闭区间及其特征量。"""

    start: Fraction
    end: Fraction
    min_current: Fraction  # 区间内差值最小的电流
    min_diff: Fraction  # 区间内的最小 (上级时间 - 包络时间)
    responsible: str  # 在 min_current 处构成包络的下级标识


@dataclass(frozen=True)
class ReviewResult:
    verdict: str  # "pass" | "fail"
    intervals: tuple[ViolationInterval, ...]


def build_envelope(
    curves: tuple[Curve, ...], lo: Fraction, hi: Fraction
) -> list[tuple[Fraction, Fraction, Line]]:
    """构造所有下级曲线在 [lo, hi] 上的逐段最大上包络。

    返回 [(seg_lo, seg_hi, line), ...]，相邻段首尾相接、覆盖整个 [lo, hi]。
    每个分段内部任意两条下级曲线都不相交，因此包络在该分段内是单条直线。
    """
    events: set[Fraction] = {lo, hi}
    for curve in curves:
        for current, _time in curve.points:
            if lo < current < hi:
                events.add(current)
    xs = sorted(events)

    pieces: list[tuple[Fraction, Fraction, Line]] = []
    for a, b in zip(xs, xs[1:]):
        # (a, b) 内没有任何折点，每条曲线在此都是单条直线。
        lines = [curve.line_at(a) for curve in curves]
        splits: set[Fraction] = {a, b}
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                l1, l2 = lines[i], lines[j]
                if l1.slope == l2.slope:
                    continue
                # 两直线交点的精确有理数横坐标
                x = (l2.intercept - l1.intercept) / (l1.slope - l2.slope)
                if a < x < b:
                    splits.add(x)
        sx = sorted(splits)
        for s0, s1 in zip(sx, sx[1:]):
            mid = (s0 + s1) / 2
            top = max(lines, key=lambda line: line.at(mid))
            pieces.append((s0, s1, top))
    return pieces


def _solve_leq_margin(
    line: Line, a: Fraction, b: Fraction, margin: Fraction
) -> tuple[Fraction, Fraction] | None:
    """求 {x in [a, b] : line.at(x) <= margin}，结果为闭区间或 None。

    line 是线性的，因此解集必为 [a,b] 的一个闭子区间（可能退化为点）。
    """
    ga = line.at(a) - margin
    gb = line.at(b) - margin
    if ga <= 0 and gb <= 0:
        return (a, b)
    if ga > 0 and gb > 0:
        return None
    # 恰好一端越界：线性求根，root 处 line.at(root) == margin（端点属于结果）
    root = a + (b - a) * (-ga) / (gb - ga)
    return (a, root) if ga <= 0 else (root, b)


def _merge_touching(
    spans: list[tuple[Fraction, Fraction]],
) -> list[tuple[Fraction, Fraction]]:
    """合并相互接触（含共享单个端点）的闭区间；零长度区间照常参与并保留。"""
    merged: list[list[Fraction]] = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def _piece_value_at(
    pieces: list[tuple[Fraction, Fraction, Line]], x: Fraction
) -> Fraction:
    starts = [p[0] for p in pieces]
    idx = bisect_right(starts, x) - 1
    idx = max(0, min(idx, len(pieces) - 1))
    return pieces[idx][2].at(x)


def _annotate(
    s: Fraction,
    e: Fraction,
    d_pieces: list[tuple[Fraction, Fraction, Line]],
    downstream: tuple[Curve, ...],
) -> ViolationInterval:
    """为极大区间找出差值最小的电流与责任下级。

    差值函数分段线性，最小值必在分段端点或区间端点处取得；
    并列时先取最小电流，再取标识字典序最小的下级。
    """
    candidates: set[Fraction] = {s, e}
    for a, b, _line in d_pieces:
        if s <= a <= e:
            candidates.add(a)
        if s <= b <= e:
            candidates.add(b)
    best_x: Fraction | None = None
    best_v: Fraction | None = None
    for x in sorted(candidates):
        v = _piece_value_at(d_pieces, x)
        if best_v is None or v < best_v:
            best_v, best_x = v, x
    assert best_x is not None and best_v is not None
    top = max(curve.value_at(best_x) for curve in downstream)
    responsible = min(
        curve.device_id for curve in downstream if curve.value_at(best_x) == top
    )
    return ViolationInterval(
        start=s, end=e, min_current=best_x, min_diff=best_v, responsible=responsible
    )


def analyze(
    window_start: Fraction,
    window_end: Fraction,
    margin: Fraction,
    upstream: Curve,
    downstream: tuple[Curve, ...],
) -> ReviewResult:
    """对闭合审查窗 [window_start, window_end] 执行选择性审查。"""
    lo, hi = window_start, window_end
    env_pieces = build_envelope(downstream, lo, hi)

    # 差值函数 D = 上级 - 包络 的全部候选分段点
    events: set[Fraction] = {lo, hi}
    for a, b, _line in env_pieces:
        events.add(a)
        events.add(b)
    for current, _time in upstream.points:
        if lo < current < hi:
            events.add(current)
    xs = sorted(events)

    env_starts = [p[0] for p in env_pieces]

    def env_line_at(x: Fraction) -> Line:
        idx = bisect_right(env_starts, x) - 1
        idx = max(0, min(idx, len(env_pieces) - 1))
        return env_pieces[idx][2]

    d_pieces: list[tuple[Fraction, Fraction, Line]] = []
    raw: list[tuple[Fraction, Fraction]] = []
    for a, b in zip(xs, xs[1:]):
        up_line = upstream.line_at(a)
        env_line = env_line_at(a)
        d_line = Line(
            slope=up_line.slope - env_line.slope,
            intercept=up_line.intercept - env_line.intercept,
        )
        d_pieces.append((a, b, d_line))
        span = _solve_leq_margin(d_line, a, b, margin)
        if span is not None:
            raw.append(span)

    merged = _merge_touching(raw)
    intervals = tuple(_annotate(s, e, d_pieces, downstream) for s, e in merged)
    return ReviewResult(verdict="fail" if intervals else "pass", intervals=intervals)


def format_rational(value: Fraction) -> str:
    """约分有理数的字符串形式：整数不带分母，否则 "p/q"（q > 0）。"""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"
