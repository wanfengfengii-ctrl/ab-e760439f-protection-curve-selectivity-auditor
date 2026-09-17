"""把精确核心的 ``Fraction`` 结果序列化为对外的 [num, den] 形式。"""
from __future__ import annotations

from fractions import Fraction

from .algorithm import AnalysisResult
from .models import (
    AnalysisResponse,
    EnvelopeSegment,
    Interval,
    Rational,
    ReviewWindow,
)


def rational(f: Fraction) -> Rational:
    # Fraction 保证分母为正；显式规范化以杜绝符号歧义。
    if f.denominator < 0:
        return Rational(num=-f.numerator, den=-f.denominator)
    return Rational(num=f.numerator, den=f.denominator)


def to_response(result: AnalysisResult, lo: int, hi: int) -> AnalysisResponse:
    return AnalysisResponse(
        safe=len(result.intervals) == 0,
        intervals=[
            Interval(
                lo=rational(i.lo),
                hi=rational(i.hi),
                min_diff=rational(i.min_diff),
                min_current=rational(i.min_current),
                responsible=i.responsible,
            )
            for i in result.intervals
        ],
        envelope=[
            EnvelopeSegment(
                lo=rational(s.lo),
                hi=rational(s.hi),
                lo_time=rational(s.lo_time),
                hi_time=rational(s.hi_time),
                responsible=s.pid,
            )
            for s in result.envelope
        ],
        window=ReviewWindow(lo=lo, hi=hi),
    )
