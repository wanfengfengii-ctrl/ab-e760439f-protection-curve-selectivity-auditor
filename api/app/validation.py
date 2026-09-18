"""请求体验证：任何一条不合法都整批拒绝，全部错误按输入位置稳定返回。"

错误顺序固定为文档位置顺序：window → margin → upstream → downstream[0..n]，
同一对象内按字段与数组下标顺序。绝不只返回第一个错误。
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .core import Curve


@dataclass(frozen=True)
class ApiError:
    path: str
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class ReviewInput:
    window_start: Fraction
    window_end: Fraction
    margin: Fraction
    upstream: Curve
    downstream: tuple[Curve, ...]


def _is_int(value: Any) -> bool:
    # bool 是 int 的子类，必须排除
    return isinstance(value, int) and not isinstance(value, bool)


def _positive_int(
    node: Any, path: str, label: str, errors: list[ApiError]
) -> int | None:
    if not _is_int(node):
        code = "missing_field" if node is None else "invalid_type"
        errors.append(ApiError(path, code, f"{label}必须是正整数"))
        return None
    if node <= 0:
        errors.append(ApiError(path, "not_positive", f"{label}必须为正整数（> 0）"))
        return None
    return node


def _validate_window(
    node: Any, errors: list[ApiError]
) -> tuple[Fraction, Fraction] | None:
    if not isinstance(node, dict):
        code = "missing_field" if node is None else "invalid_type"
        errors.append(ApiError("window", code, "审查窗必须是对象 {start, end}"))
        return None
    start = _positive_int(node.get("start"), "window.start", "审查窗起点电流（微安）", errors)
    end = _positive_int(node.get("end"), "window.end", "审查窗终点电流（微安）", errors)
    if start is None or end is None:
        return None
    if start >= end:
        errors.append(ApiError("window", "window_order", "审查窗起点必须严格小于终点"))
        return None
    return Fraction(start), Fraction(end)


def _validate_margin(node: Any, errors: list[ApiError]) -> Fraction | None:
    if not _is_int(node):
        code = "missing_field" if node is None else "invalid_type"
        errors.append(ApiError("margin", code, "裕量必须是非负整数（微秒）"))
        return None
    if node < 0:
        errors.append(ApiError("margin", "negative", "裕量必须是非负整数（>= 0）"))
        return None
    return Fraction(node)


def _validate_points(
    node: Any, path: str, errors: list[ApiError]
) -> list[tuple[Fraction, Fraction]] | None:
    if not isinstance(node, list):
        code = "missing_field" if node is None else "invalid_type"
        errors.append(ApiError(path, code, "折点必须是数组"))
        return None
    points: list[tuple[Fraction, Fraction]] = []
    ok = True
    for i, item in enumerate(node):
        ipath = f"{path}[{i}]"
        if not isinstance(item, dict):
            errors.append(ApiError(ipath, "invalid_type", "折点必须是对象 {current, time}"))
            ok = False
            continue
        current = _positive_int(
            item.get("current"), f"{ipath}.current", "折点电流（微安）", errors
        )
        time = _positive_int(
            item.get("time"), f"{ipath}.time", "折点动作时间（微秒）", errors
        )
        if current is None or time is None:
            ok = False
            continue
        points.append((Fraction(current), Fraction(time)))
    if len(node) < 2:
        errors.append(ApiError(path, "too_few_points", "每条曲线至少需要两个折点"))
        ok = False
    if not ok or len(points) != len(node):
        return None
    for k in range(len(points) - 1):
        if points[k][0] >= points[k + 1][0]:
            errors.append(
                ApiError(
                    f"{path}[{k + 1}].current",
                    "not_strictly_increasing",
                    "折点电流必须严格递增",
                )
            )
            return None
    return points


def _validate_curve(
    node: Any,
    path: str,
    errors: list[ApiError],
    seen_ids: set[str],
    window: tuple[Fraction, Fraction] | None,
) -> Curve | None:
    if not isinstance(node, dict):
        code = "missing_field" if node is None else "invalid_type"
        errors.append(ApiError(path, code, "保护器必须是对象 {id, points}"))
        return None
    device_id = node.get("id")
    id_ok = True
    if not isinstance(device_id, str) or not device_id:
        code = "missing_field" if device_id is None else "invalid_type"
        errors.append(ApiError(f"{path}.id", code, "标识必须是非空字符串"))
        id_ok = False
    elif device_id in seen_ids:
        errors.append(ApiError(f"{path}.id", "duplicate_id", f"标识 {device_id!r} 重复"))
        id_ok = False
    else:
        seen_ids.add(device_id)
    points = _validate_points(node.get("points"), f"{path}.points", errors)
    if points is not None and window is not None:
        lo, hi = window
        if points[0][0] > lo or points[-1][0] < hi:
            errors.append(
                ApiError(
                    f"{path}.points",
                    "insufficient_coverage",
                    "曲线电流范围必须覆盖整个闭合审查窗",
                )
            )
            points = None
    if not id_ok or points is None:
        return None
    return Curve(device_id=device_id, points=tuple(points))


def _validate_downstream(
    node: Any,
    errors: list[ApiError],
    seen_ids: set[str],
    window: tuple[Fraction, Fraction] | None,
) -> list[Curve] | None:
    if not isinstance(node, list):
        code = "missing_field" if node is None else "invalid_type"
        errors.append(ApiError("downstream", code, "下级保护器必须是数组"))
        return None
    if len(node) < 2:
        errors.append(ApiError("downstream", "too_few_downstream", "至少需要两个下级保护器"))
    curves: list[Curve] = []
    for i, item in enumerate(node):
        curve = _validate_curve(item, f"downstream[{i}]", errors, seen_ids, window)
        if curve is not None:
            curves.append(curve)
    return curves or None


def validate_payload(payload: Any) -> tuple[list[ApiError], ReviewInput | None]:
    """整批验证：收集全部错误；有错则拒绝，绝不返回部分结果。"""
    errors: list[ApiError] = []
    if not isinstance(payload, dict):
        return [ApiError("", "invalid_type", "请求体必须是 JSON 对象")], None
    window = _validate_window(payload.get("window"), errors)
    margin = _validate_margin(payload.get("margin"), errors)
    seen_ids: set[str] = set()
    upstream = _validate_curve(payload.get("upstream"), "upstream", errors, seen_ids, window)
    downstream = _validate_downstream(payload.get("downstream"), errors, seen_ids, window)
    if errors:
        return errors, None
    assert window is not None and margin is not None
    assert upstream is not None and downstream is not None
    return (
        [],
        ReviewInput(
            window_start=window[0],
            window_end=window[1],
            margin=margin,
            upstream=upstream,
            downstream=tuple(downstream),
        ),
    )
