"""整批输入校验。

不依赖 Pydantic 的“首个错误即停”，而是直接检查已解析的 JSON，把 *所有*
错误一次性收集起来，并按输入位置（window → margin → upstream →
downstream[i]）稳定返回。任一字段非法都会整批拒绝，调用方因此不会残留
旧图。

错误位置用 JSON 指针风格的路径片段表示，例如
``["downstream", 0, "points", 1, "current"]``。
"""
from __future__ import annotations

from typing import Any

from .algorithm import ValidatedCurve, ValidatedInput


class ValidationError(Exception):
    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__(f"{len(errors)} 个校验错误")
        self.errors = errors


def _is_int(v: Any) -> bool:
    # bool 是 int 的子类，但 JSON 里的 true/false 绝不能当作电流。
    return isinstance(v, int) and not isinstance(v, bool)


def _err(path: list[Any], message: str) -> dict[str, Any]:
    return {"path": path, "message": message}


def _validate_protector(
    obj: Any, base: list[Any], window: tuple[Any, Any] | None
) -> tuple[list[dict[str, Any]], ValidatedCurve | None]:
    """校验单个保护器，返回 (错误, 仅在完全有效时的曲线)。"""
    errors: list[dict[str, Any]] = []
    pid: Any = None

    if not isinstance(obj, dict):
        return [_err(base, "必须是保护器对象 {id, points}")], None

    allowed = {"id", "points"}
    for key in obj:
        if key not in allowed:
            errors.append(_err(base + [key], "未知字段"))

    pid = obj.get("id")
    if "id" not in obj:
        errors.append(_err(base + ["id"], "缺少标识 id"))
    elif not isinstance(pid, str) or pid == "":
        errors.append(_err(base + ["id"], "id 必须是非空字符串"))

    points_ok = True
    points: list[tuple[int, int]] = []
    if "points" not in obj:
        errors.append(_err(base + ["points"], "缺少折点列表 points"))
        points_ok = False
    elif not isinstance(obj["points"], list):
        errors.append(_err(base + ["points"], "points 必须是数组"))
        points_ok = False
    else:
        raw_points = obj["points"]
        if len(raw_points) < 2:
            errors.append(
                _err(base + ["points"], "每条曲线至少需要 2 个折点")
            )
            points_ok = False
        prev_current: int | None = None
        for i, p in enumerate(raw_points):
            ppath = base + ["points", i]
            if not isinstance(p, dict):
                errors.append(_err(ppath, "折点必须是对象 {current, time}"))
                points_ok = False
                continue
            for key in p:
                if key not in {"current", "time"}:
                    errors.append(_err(ppath + [key], "未知字段"))
            cur = p.get("current")
            tim = p.get("time")
            cur_ok = tim_ok = inc_ok = True
            if "current" not in p:
                errors.append(_err(ppath + ["current"], "缺少电流 current"))
                cur_ok = False
            elif not _is_int(cur) or cur <= 0:
                errors.append(
                    _err(ppath + ["current"], "电流必须是正整数（微安 uA）")
                )
                cur_ok = False
            if "time" not in p:
                errors.append(_err(ppath + ["time"], "缺少动作时间 time"))
                tim_ok = False
            elif not _is_int(tim) or tim <= 0:
                errors.append(
                    _err(ppath + ["time"], "动作时间必须是正整数（微秒 us）")
                )
                tim_ok = False
            if cur_ok and prev_current is not None:
                if not cur > prev_current:  # type: ignore[operator]
                    errors.append(
                        _err(
                            ppath + ["current"],
                            "折点电流必须严格递增",
                        )
                    )
                    inc_ok = False
            if cur_ok:
                prev_current = cur  # type: ignore[assignment]
            if not (cur_ok and tim_ok and inc_ok):
                points_ok = False
            else:
                points.append((cur, tim))

        # 覆盖闭合审查窗：首折点电流 <= lo，末折点电流 >= hi。
        if points_ok and window is not None:
            lo, hi = window
            if _is_int(lo) and _is_int(hi):
                if points[0][0] > lo:
                    errors.append(
                        _err(
                            base + ["points"],
                            f"覆盖不足：首折点电流 {points[0][0]} 大于审查窗下界 {lo}",
                        )
                    )
                    points_ok = False
                if points[-1][0] < hi:
                    errors.append(
                        _err(
                            base + ["points"],
                            f"覆盖不足：末折点电流 {points[-1][0]} 小于审查窗上界 {hi}",
                        )
                    )
                    points_ok = False

    if errors or not points_ok or pid is None or not isinstance(pid, str) or pid == "":
        return errors, None
    return errors, ValidatedCurve(pid=pid, points=points)


def validate(payload: Any) -> ValidatedInput:
    """校验整批请求；非法时抛出 :class:`ValidationError`（含全部错误）。"""
    errors: list[dict[str, Any]] = []

    if not isinstance(payload, dict):
        raise ValidationError([_err([], "请求体必须是 JSON 对象")])

    for key in payload:
        if key not in {"window", "upstream", "downstream", "margin"}:
            errors.append(_err([key], "顶层未知字段"))

    # --- 审查窗 -----------------------------------------------------------
    lo: Any = None
    hi: Any = None
    window_ok = False
    if "window" not in payload:
        errors.append(_err(["window"], "缺少审查窗 window"))
    elif not isinstance(payload["window"], dict):
        errors.append(_err(["window"], "window 必须是对象 {lo, hi}"))
    else:
        win = payload["window"]
        for key in win:
            if key not in {"lo", "hi"}:
                errors.append(_err(["window", key], "未知字段"))
        lo = win.get("lo")
        hi = win.get("hi")
        lo_ok = hi_ok = True
        if "lo" not in win:
            errors.append(_err(["window", "lo"], "缺少窗下界 lo"))
            lo_ok = False
        elif not _is_int(lo) or lo <= 0:
            errors.append(
                _err(["window", "lo"], "窗下界必须是正整数（微安 uA）")
            )
            lo_ok = False
        if "hi" not in win:
            errors.append(_err(["window", "hi"], "缺少窗上界 hi"))
            hi_ok = False
        elif not _is_int(hi) or hi <= 0:
            errors.append(
                _err(["window", "hi"], "窗上界必须是正整数（微安 uA）")
            )
            hi_ok = False
        if lo_ok and hi_ok and lo > hi:
            errors.append(
                _err(["window", "hi"], "窗上界必须不小于窗下界")
            )
            hi_ok = False
        window_ok = lo_ok and hi_ok

    # --- 裕量 -------------------------------------------------------------
    if "margin" not in payload:
        errors.append(_err(["margin"], "缺少时间裕量 margin"))
    elif not _is_int(payload["margin"]) or payload["margin"] < 0:
        errors.append(
            _err(["margin"], "裕量必须是非负整数（微秒 us）")
        )

    # --- 上级 -------------------------------------------------------------
    upstream: ValidatedCurve | None = None
    # 已见到的标识 -> 首次出现的位置；重复时把错误挂在后出现者身上。
    seen: dict[str, list[Any]] = {}
    if "upstream" not in payload:
        errors.append(_err(["upstream"], "缺少上级保护器 upstream"))
    else:
        window = (lo, hi) if window_ok else None
        up_errs, upstream = _validate_protector(
            payload["upstream"], ["upstream"], window
        )
        errors.extend(up_errs)
        if upstream is not None:
            seen[upstream.pid] = ["upstream", "id"]

    # --- 下级 -------------------------------------------------------------
    downstream: list[ValidatedCurve] = []
    raw_downstream: list[Any] = []
    if "downstream" not in payload:
        errors.append(_err(["downstream"], "缺少下级保护器列表 downstream"))
    elif not isinstance(payload["downstream"], list):
        errors.append(_err(["downstream"], "downstream 必须是数组"))
    else:
        raw_downstream = payload["downstream"]
        if len(raw_downstream) < 2:
            errors.append(
                _err(["downstream"], "至少需要 2 个下级保护器")
            )
        window = (lo, hi) if window_ok else None
        # 沿文档顺序逐个处理：重复标识错误紧跟该保护器自身错误返回，
        # 因而全部错误严格按输入位置稳定排列。
        for i, d in enumerate(raw_downstream):
            d_errs, curve = _validate_protector(
                d, ["downstream", i], window
            )
            errors.extend(d_errs)
            if isinstance(d, dict):
                did = d.get("id")
                if isinstance(did, str) and did:
                    path = ["downstream", i, "id"]
                    if did in seen:
                        errors.append(
                            _err(path, f"标识 {did!r} 与更早的保护器重复")
                        )
                    else:
                        seen[did] = path
            if curve is not None:
                downstream.append(curve)

    if errors:
        raise ValidationError(errors)

    assert upstream is not None and window_ok
    return ValidatedInput(
        lo=lo,
        hi=hi,
        margin=payload["margin"],
        upstream=upstream,
        downstream=downstream,
    )
