"""选择性分析的精确核心。

输入全部是 *整数计数*（微安 / 微秒），进入本模块后所有内部坐标、斜率、
截距、交点与区间边界都使用 :class:`fractions.Fraction`，绝不使用浮点，
因此浏览器看到的区间边界就是数学上的精确有理数边界。

算法概述
========
1. 每条折线在相邻折点之间按电流线性插值，截到闭合审查窗 ``[lo, hi]``。
2. 取所有下级曲线的 *逐段最大上包络*：把全部下级线段的端点作为事件，
   在每个事件开区间内活动线段集合不变；枚举活动两两段内交点，再次切分，
   中点比较选出包络线段（等值时责任标识取字典序最小者）。
3. 差值 ``d(x) = 上级时间(x) - 包络时间(x)`` 仍是分段线性函数。
4. ``d(x) <= margin`` 的点集即“失去选择性”。逐段求其与闭区间的交
   （线性函数的下水平集至多是一个闭区间），再把相互接触的闭区间合并：
   端点相切而形成的零长度接触 ``[r, r]`` 会被保留。
5. 每个极大区间内，差值最小值只可能落在分段结点（含平坦段起点）或区间
   端点；并列时先取最小电流，同一电流再取责任下级标识字典序最小者。
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

# ---------------------------------------------------------------------------
# 基础结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineSeg:
    """闭区间 [a, b] 上的线性函数 y = m*x + c，pid 为所属保护器标识。"""

    a: Fraction
    b: Fraction
    m: Fraction
    c: Fraction
    pid: str

    def value(self, x: Fraction) -> Fraction:
        return self.m * x + self.c


@dataclass(frozen=True)
class ValidatedCurve:
    pid: str
    points: list[tuple[int, int]]  # (电流 uA, 时间 us)，电流严格递增


@dataclass(frozen=True)
class ValidatedInput:
    lo: int
    hi: int
    margin: int
    upstream: ValidatedCurve
    downstream: list[ValidatedCurve]


@dataclass(frozen=True)
class DiffSeg:
    a: Fraction
    b: Fraction
    slope: Fraction
    intercept: Fraction  # d(x) = slope * x + intercept

    def value(self, x: Fraction) -> Fraction:
        return self.slope * x + self.intercept


@dataclass(frozen=True)
class NonSelectiveInterval:
    lo: Fraction
    hi: Fraction
    min_diff: Fraction
    min_current: Fraction
    responsible: str


@dataclass(frozen=True)
class EnvelopeSeg:
    """上包络的一段：[lo, hi] 上时间为线性，责任下级为 pid。"""

    lo: Fraction
    hi: Fraction
    lo_time: Fraction
    hi_time: Fraction
    pid: str


@dataclass(frozen=True)
class AnalysisResult:
    intervals: list[NonSelectiveInterval]
    envelope: list[EnvelopeSeg]


# ---------------------------------------------------------------------------
# 折线构造与裁剪
# ---------------------------------------------------------------------------


def _raw_segments(curve: ValidatedCurve) -> list[LineSeg]:
    """由折点构造完整的分段线性函数（电流严格递增，分母非零）。"""
    segs: list[LineSeg] = []
    for (x1, y1), (x2, y2) in zip(curve.points, curve.points[1:]):
        fx1, fy1, fx2, fy2 = (
            Fraction(x1),
            Fraction(y1),
            Fraction(x2),
            Fraction(y2),
        )
        m = (fy2 - fy1) / (fx2 - fx1)
        c = fy1 - m * fx1
        segs.append(LineSeg(fx1, fx2, m, c, curve.pid))
    return segs


def _clip(segs: list[LineSeg], lo: Fraction, hi: Fraction) -> list[LineSeg]:
    """把线段截到 [lo, hi]，丢弃退化的内部零长度段。

    覆盖性（见 validation）保证裁剪后仍有非退化段拼出整个 [lo, hi]。
    """
    out: list[LineSeg] = []
    for s in segs:
        a, b = max(s.a, lo), min(s.b, hi)
        if a < b:
            out.append(LineSeg(a, b, s.m, s.c, s.pid))
    return out


# ---------------------------------------------------------------------------
# 下级逐段最大上包络
# ---------------------------------------------------------------------------


def _build_envelope(
    funcs: list[LineSeg], lo: Fraction, hi: Fraction
) -> list[LineSeg]:
    """构造所有下级曲线在 [lo, hi] 上的逐段最大上包络。

    返回的线段首尾相接、恰好覆盖 [lo, hi]；每段的 ``pid`` 是该段包络的
    责任下级（等值时字典序最小）。
    """
    # 事件点：全部活动线段的端点。
    events = {lo, hi}
    for f in funcs:
        events.add(f.a)
        events.add(f.b)
    xs = sorted(events)

    pieces: list[LineSeg] = []
    for j in range(len(xs) - 1):
        cell_lo, cell_hi = xs[j], xs[j + 1]
        if cell_lo >= cell_hi:
            continue
        # 覆盖整个闭格子的线段 = 在格子内部活动的线段。
        active = [
            f for f in funcs if f.a <= cell_lo and f.b >= cell_hi
        ]
        assert active, "审查窗内每个点都应至少被一条下级曲线覆盖"

        # 段内两两交点作为额外切分点；交点之外各函数大小关系恒定。
        cuts: set[Fraction] = {cell_lo, cell_hi}
        for i, f in enumerate(active):
            for g in active[i + 1 :]:
                if f.m != g.m:
                    x = (g.c - f.c) / (f.m - g.m)
                    if cell_lo < x < cell_hi:
                        cuts.add(x)
        cut_xs = sorted(cuts)

        for k in range(len(cut_xs) - 1):
            u, v = cut_xs[k], cut_xs[k + 1]
            mid = (u + v) / 2
            # 最大值；同值取标识字典序最小者。
            winner = min(
                active, key=lambda f: (-f.value(mid), f.pid)
            )
            pieces.append(LineSeg(u, v, winner.m, winner.c, winner.pid))

    # 跨事件点的同一直线段合并。
    merged: list[LineSeg] = []
    for p in pieces:
        if merged and merged[-1].b == p.a and merged[-1].m == p.m \
                and merged[-1].c == p.c and merged[-1].pid == p.pid:
            prev = merged[-1]
            merged[-1] = LineSeg(prev.a, p.b, p.m, p.c, p.pid)
        else:
            merged.append(p)
    return merged


# ---------------------------------------------------------------------------
# 差值分段线性函数
# ---------------------------------------------------------------------------


def _build_diff(
    upstream: list[LineSeg], envelope: list[LineSeg],
    lo: Fraction, hi: Fraction,
) -> list[DiffSeg]:
    knots = {lo, hi}
    for s in upstream:
        knots.add(s.a)
        knots.add(s.b)
    for p in envelope:
        knots.add(p.a)
        knots.add(p.b)
    xs = sorted(k for k in knots if lo <= k <= hi)

    def covering(segs, x):
        for s in segs:
            if s.a <= x <= s.b:
                return s
        raise AssertionError("裁剪后的线段必须覆盖审查窗内所有点")

    out: list[DiffSeg] = []
    for j in range(len(xs) - 1):
        a, b = xs[j], xs[j + 1]
        mid = (a + b) / 2
        u = covering(upstream, mid)
        e = covering(envelope, mid)
        slope = u.m - e.m
        intercept = u.c - e.c
        out.append(DiffSeg(a, b, slope, intercept))
    return out


# ---------------------------------------------------------------------------
# 下水平集 {x : d(x) <= margin}
# ---------------------------------------------------------------------------


def _sublevel_intervals(
    diff: list[DiffSeg], margin: Fraction
) -> list[tuple[Fraction, Fraction]]:
    """逐段求 d(x) <= margin 的闭区间（线性函数，形状最多四种）。"""
    raw: list[tuple[Fraction, Fraction]] = []
    for seg in diff:
        dp = seg.value(seg.a)
        dq = seg.value(seg.b)
        if dp <= margin and dq <= margin:
            raw.append((seg.a, seg.b))
        elif dp <= margin < dq:
            # 单调上升穿出：margin = dp + slope*(root-a)。
            root = seg.a + (margin - dp) / seg.slope
            raw.append((seg.a, root))  # root 可能 == a（零长度接触）
        elif dq <= margin < dp:
            # 单调下降穿入：margin = dq + slope*(root-b)。
            root = seg.b + (margin - dq) / seg.slope
            raw.append((root, seg.b))  # root 可能 == b（零长度接触）
        # 两端都严格大于时，线性函数中段不可能更低。
    return _merge_closed(raw)


def _merge_closed(
    intervals: list[tuple[Fraction, Fraction]],
) -> list[tuple[Fraction, Fraction]]:
    """合并闭区间：接触（端点相等）即合并；零长度区间保留。"""
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged: list[tuple[Fraction, Fraction]] = [ordered[0]]
    for a, b in ordered[1:]:
        la, lb = merged[-1]
        if a <= lb:  # 闭区间端点接触也算同一个极大区间
            merged[-1] = (la, max(lb, b))
        else:
            merged.append((a, b))
    return merged


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def _covering(segs: list[LineSeg], x: Fraction) -> LineSeg:
    for s in segs:
        if s.a <= x <= s.b:
            return s
    raise AssertionError("覆盖性保证该电流处存在线段")


def _analyze_point_window(
    data: ValidatedInput, x: Fraction, margin: Fraction
) -> AnalysisResult:
    """闭合审查窗退化为单点 {x} 时的精确求值。"""
    up_seg = _covering(_raw_segments(data.upstream), x)
    down_segs = [_covering(_raw_segments(c), x) for c in data.downstream]

    # 包络：取时间最大者；等值取 id 字典序最小。
    winner = min(down_segs, key=lambda f: (-f.value(x), f.pid))
    env_time = winner.value(x)
    diff_value = up_seg.value(x) - env_time

    envelope = [
        EnvelopeSeg(
            lo=x, hi=x, lo_time=env_time, hi_time=env_time, pid=winner.pid
        )
    ]
    intervals: list[NonSelectiveInterval] = []
    if diff_value <= margin:
        intervals.append(
            NonSelectiveInterval(
                lo=x,
                hi=x,
                min_diff=diff_value,
                min_current=x,
                responsible=winner.pid,
            )
        )
    return AnalysisResult(intervals=intervals, envelope=envelope)


def analyze(data: ValidatedInput) -> AnalysisResult:
    lo, hi = Fraction(data.lo), Fraction(data.hi)
    margin = Fraction(data.margin)

    # 零宽度闭合审查窗：只审查单个电流点。
    if lo == hi:
        return _analyze_point_window(data, lo, margin)

    downstream_segs: list[LineSeg] = []
    for curve in data.downstream:
        downstream_segs.extend(_clip(_raw_segments(curve), lo, hi))
    upstream_segs = _clip(_raw_segments(data.upstream), lo, hi)

    envelope = _build_envelope(downstream_segs, lo, hi)
    diff = _build_diff(upstream_segs, envelope, lo, hi)
    bad = _sublevel_intervals(diff, margin)

    # 差值分段结点（最小值候选）。
    knot_set = {lo, hi}
    for seg in diff:
        knot_set.add(seg.a)
        knot_set.add(seg.b)

    def eval_diff(x: Fraction) -> Fraction:
        for seg in diff:
            if seg.a <= x <= seg.b:
                return seg.value(x)
        raise AssertionError("差值函数应覆盖审查窗")

    def responsible(x: Fraction) -> str:
        # 回到全部原始下级线段判定，正确处理结点处的多曲线等值并列。
        best_value: Fraction | None = None
        best_id: str | None = None
        for f in downstream_segs:
            if f.a <= x <= f.b:
                v = f.value(x)
                if best_value is None or v > best_value or (
                    v == best_value and f.pid < best_id  # type: ignore[operator]
                ):
                    best_value, best_id = v, f.pid
        assert best_id is not None
        return best_id

    results: list[NonSelectiveInterval] = []
    for a, b in bad:
        candidates = sorted(k for k in knot_set if a <= k <= b)
        candidates = [a, b] + [k for k in candidates if k not in (a, b)]
        # candidates 首元素为 a，遍历时仅在严格更小时更新，
        # 因而等值时自动保留最小电流。
        best_x = candidates[0]
        best_d = eval_diff(best_x)
        for x in candidates[1:]:
            v = eval_diff(x)
            if v < best_d:
                best_d, best_x = v, x
        results.append(
            NonSelectiveInterval(
                lo=a,
                hi=b,
                min_diff=best_d,
                min_current=best_x,
                responsible=responsible(best_x),
            )
        )

    envelope_out = [
        EnvelopeSeg(
            lo=s.a,
            hi=s.b,
            lo_time=s.value(s.a),
            hi_time=s.value(s.b),
            pid=s.pid,
        )
        for s in envelope
    ]
    return AnalysisResult(intervals=results, envelope=envelope_out)
