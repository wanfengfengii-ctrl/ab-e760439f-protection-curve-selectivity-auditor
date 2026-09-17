"""请求 / 响应的 Pydantic 模型。

领域量一律使用 *整数计数*：
- 电流单位为微安 (uA)；
- 动作时间单位为微秒 (us)；
- 时间裕量单位也为微秒 (us)。

折点之间的内部坐标、上包络交点与非选择区间边界都在算法层用
``fractions.Fraction`` 表示，对外再序列化为 ``[分子, 分母]``（分母恒正、
已约分），见 :mod:`app.serialization`。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Point(BaseModel):
    """保护曲线上的一个折点。"""

    current: int = Field(..., description="电流，单位微安 (uA)，正整数")
    time: int = Field(..., description="动作时间，单位微秒 (us)，正整数")


class Protector(BaseModel):
    """单条保护曲线（上级或下级）。"""

    id: str = Field(..., description="保护器标识，审查窗内唯一")
    points: list[Point] = Field(..., description="折点，电流严格递增")


class ReviewWindow(BaseModel):
    """闭合审查窗 [lo, hi]。"""

    lo: int = Field(..., description="窗下界电流，单位微安 (uA)")
    hi: int = Field(..., description="窗上界电流，单位微安 (uA)")


class AnalysisRequest(BaseModel):
    """整批审查输入。任一字段非法都整批拒绝，不残留旧结果。"""

    window: ReviewWindow
    upstream: Protector
    downstream: list[Protector]
    margin: int = Field(..., description="时间裕量，单位微秒 (us)，非负整数")


class Rational(BaseModel):
    """约分后的有理数：值 = num / den，den 恒为正。"""

    num: int
    den: int


class Interval(BaseModel):
    """一个极大非选择（失去选择性）闭区间。"""

    lo: Rational
    hi: Rational
    min_diff: Rational = Field(..., description="区间内 (上级时间-包络时间) 的最小值")
    min_current: Rational = Field(..., description="取到最小差值的电流（并列时取最小电流）")
    responsible: str = Field(..., description="责任下级保护器标识（再并列按字典序）")


class EnvelopeSegment(BaseModel):
    """精确上包络的一段（用于前端叠绘，端点为有理数）。"""

    lo: Rational
    hi: Rational
    lo_time: Rational
    hi_time: Rational
    responsible: str


class AnalysisResponse(BaseModel):
    safe: bool = Field(..., description="全审查窗安全（不存在任何非选择点）")
    intervals: list[Interval]
    envelope: list[EnvelopeSegment] = Field(
        ..., description="下级逐段最大上包络（精确有理端点）"
    )
    window: ReviewWindow
