"""FastAPI 入口：POST /api/review 执行选择性审查。"""

from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core import analyze, format_rational
from .validation import ApiError, validate_payload

app = FastAPI(title="配电柜保护选择性审查", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/review")
async def review(request: Request):
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        err = ApiError("", "invalid_json", f"请求体不是合法 JSON：{exc.msg}")
        return JSONResponse(status_code=422, content={"errors": [err.as_dict()]})
    errors, review_input = validate_payload(payload)
    if errors:
        # 整批拒绝：一次性返回全部错误，客户端据此清除旧图
        return JSONResponse(
            status_code=422, content={"errors": [e.as_dict() for e in errors]}
        )
    assert review_input is not None
    result = analyze(
        window_start=review_input.window_start,
        window_end=review_input.window_end,
        margin=review_input.margin,
        upstream=review_input.upstream,
        downstream=review_input.downstream,
    )
    return {
        "verdict": result.verdict,
        "intervals": [
            {
                "start": format_rational(iv.start),
                "end": format_rational(iv.end),
                "min_current": format_rational(iv.min_current),
                "min_diff": format_rational(iv.min_diff),
                "responsible": iv.responsible,
            }
            for iv in result.intervals
        ],
    }
