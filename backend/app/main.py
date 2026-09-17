"""FastAPI 入口。

POST /api/analyze 接收 *原始 JSON*（而非 Pydantic 模型），以便一次性返回
按输入位置稳定排列的全部校验错误；校验通过才运行精确核心。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .algorithm import analyze
from .serialization import to_response
from .validation import ValidationError, validate

app = FastAPI(title="保护曲线选择性审查", version="1.0.0")

# 本地开发：Vite dev server 在 5173 端口。生产同源（nginx 反代 /api）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze_endpoint(request: Request) -> JSONResponse:
    try:
        payload: Any = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(
            status_code=400,
            content={"errors": [{"path": [], "message": "请求体不是合法 JSON"}]},
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400,
            content={"errors": [{"path": [], "message": "请求体必须是 JSON 对象"}]},
        )

    try:
        data = validate(payload)
    except ValidationError as exc:
        return JSONResponse(status_code=422, content={"errors": exc.errors})

    result = analyze(data)
    response = to_response(result, data.lo, data.hi)
    return JSONResponse(status_code=200, content=response.model_dump())
