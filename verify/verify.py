"""一次性验收：真实地请求 api 与 web（经 nginx 反代），断言端到端契约。

任一断言失败即以非零码退出，供 ``docker compose run --rm verify`` 作为
CI / 交付门禁。全程只使用标准库，镜像无需额外依赖。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

# 容器内走 compose 服务名；本地可用 API_BASE / WEB_BASE 覆盖做同样的真实验收。
API = os.environ.get("API_BASE", "http://api:8000")
WEB = os.environ.get("WEB_BASE", "http://web:80")


def request(method: str, url: str, payload=None, timeout: float = 5.0):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def wait_for(url: str, what: str, attempts: int = 60) -> None:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    print(f"[ready] {what} ({url})")
                    return
        except Exception:
            time.sleep(1)
    print(f"[FAIL] 等待 {what} 超时：{url}")
    sys.exit(1)


CROSSING = {
    "window": {"lo": 1, "hi": 7},
    "margin": 0,
    "upstream": {"id": "U", "points": [
        {"current": 1, "time": 10}, {"current": 7, "time": 4}]},
    "downstream": [
        {"id": "D1", "points": [
            {"current": 1, "time": 5}, {"current": 7, "time": 5}]},
        {"id": "D2", "points": [
            {"current": 1, "time": 1}, {"current": 7, "time": 1}]},
    ],
}

FRACTION = {
    "window": {"lo": 1, "hi": 4},
    "margin": 0,
    "upstream": {"id": "U", "points": [
        {"current": 1, "time": 7}, {"current": 4, "time": 7}]},
    "downstream": [
        {"id": "D1", "points": [
            {"current": 1, "time": 2}, {"current": 4, "time": 8}]},
        {"id": "D2", "points": [
            {"current": 1, "time": 1}, {"current": 4, "time": 1}]},
    ],
}

SAFE = {
    "window": {"lo": 1, "hi": 10},
    "margin": 0,
    "upstream": {"id": "U", "points": [
        {"current": 1, "time": 100}, {"current": 10, "time": 100}]},
    "downstream": [
        {"id": "D1", "points": [
            {"current": 1, "time": 10}, {"current": 10, "time": 10}]},
        {"id": "D2", "points": [
            {"current": 1, "time": 5}, {"current": 10, "time": 5}]},
    ],
}


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name} {detail}")
        sys.exit(1)


def main() -> None:
    wait_for(f"{API}/health", "api")
    wait_for(WEB + "/", "web")

    # 1) 健康检查。
    status, body = request("GET", f"{API}/health")
    check("api 健康检查 200/ok", status == 200 and body.get("status") == "ok", str(body))

    # 2) 交叉案例：经 api 直连，边界精确为 6。
    status, body = request("POST", f"{API}/api/analyze", CROSSING)
    check("交叉案例 api 200", status == 200, str(body))
    check("交叉案例非安全", body.get("safe") is False, str(body))
    iv = body["intervals"][0]
    check("左边界精确为 6/1", iv["lo"] == {"num": 6, "den": 1}, str(iv))
    check("右边界为窗上界 7", iv["hi"] == {"num": 7, "den": 1}, str(iv))
    check("责任下级为 D1", iv["responsible"] == "D1", str(iv))
    check("返回精确上包络分段", len(body.get("envelope", [])) >= 1, str(body)[:200])

    # 3) 同一案例经 web（nginx 反代）结果必须一致 -> 真实联调。
    status_w, body_w = request("POST", WEB + "/api/analyze", CROSSING)
    check("经 web 反代 200", status_w == 200, str(body_w))
    check("web 与 api 结果一致", body_w == body, "经两条路径结果不同")

    # 4) 分数边界 7/2，不被采样漏掉。
    status, body = request("POST", f"{API}/api/analyze", FRACTION)
    lo = body["intervals"][0]["lo"]
    check("分数边界精确为 7/2", lo == {"num": 7, "den": 2}, str(lo))

    # 5) 全窗安全。
    status, body = request("POST", f"{API}/api/analyze", SAFE)
    check("安全案例 safe=true 且无区间",
          status == 200 and body.get("safe") is True and body["intervals"] == [], str(body))

    # 6) 整批拒绝：一次返回多处、按位置标注的错误。
    bad = json.loads(json.dumps(CROSSING))
    bad["margin"] = -1
    bad["downstream"][0]["points"][0]["current"] = 0
    status, body = request("POST", f"{API}/api/analyze", bad)
    paths = [tuple(e["path"]) for e in body.get("errors", [])]
    check("非法输入返回 422", status == 422, str(status))
    check("同时报出 margin 与 current 两处错误",
          ("margin",) in paths and ("downstream", 0, "points", 0, "current") in paths,
          str(paths))

    print("\n全部验收通过 ✅")


if __name__ == "__main__":
    main()
