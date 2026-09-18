# 配电柜上下级保护曲线选择性审查

全栈应用：浏览器编辑或上传 JSON 提交审查，后端以**整数与约分有理数**精确构造所有
下级曲线的逐段最大上包络，找出上级曲线与包络之差小于等于裕量的全部极大闭区间，
前端用 SVG 叠绘曲线并支持列表悬停高亮。

- 后端：Python 3.12 · FastAPI（`api/`）
- 前端：TypeScript · React · Vite（`web/`）
- 一次性验收服务：`verify/`（对运行中的 api/web 做端到端断言）
- 测试：pytest（算法 + 契约）、Vitest（前端单元）、Playwright（真实联调）

## 数据约定

| 概念 | 约定 |
| --- | --- |
| 电流 | 正整数，单位微安（µA） |
| 动作时间 | 正整数，单位微秒（µs） |
| 裕量 `margin` | 非负整数，单位微秒（µs） |
| 审查窗 `window` | 闭合区间 `[start, end]`，`start < end`，均为正整数电流 |
| 曲线 | 至少 2 个折点 `{current, time}`，折点电流**严格递增**，折点间按电流线性插值 |
| 覆盖 | 每条曲线的首折点电流 ≤ `window.start` 且末折点电流 ≥ `window.end` |
| 标识 `id` | 非空字符串，全部保护器（1 个上级 + ≥2 个下级）内唯一 |

判定规则（核心算法，全程只用整数与 `fractions.Fraction`，无浮点）：

1. 对审查窗内每个电流，取所有下级曲线动作时间的**最大值**构成上包络；
   包络分段点含下级折点与下级曲线两两交点，全部为精确有理数。
2. 记 `D(I) = 上级时间(I) − 包络时间(I)`，凡 `D(I) ≤ margin` 的电流即**不选择**；
   判据含等号，**区间端点属于结果**。
3. 不选择集合是若干闭区间的并；**相互接触（含仅共享一个端点）的闭区间合并**
   为极大区间；`D` 仅在单点触及裕量时产生**零长度区间**（如 `[2000, 2000]`），予以保留。
4. 每个极大区间返回**差值最小的电流**与**责任下级**（该电流处构成包络的下级）。
   并列时先取**最小电流**，再取**标识字典序**最小者。
5. 全窗无任何不选择区间时 `verdict = "pass"`。

有理数边界字符串：整数形如 `"5000"`，分数形如 `"28250/7"`（已约分，分母为正）。
前端原样展示，仅在换算 SVG 坐标时降级为浮点，绝不回传判定逻辑。

## API 契约

### `POST /api/review`

请求体：

```json
{
  "window": { "start": 1000, "end": 5000 },
  "margin": 200,
  "upstream": {
    "id": "QS-main",
    "points": [
      { "current": 500, "time": 10000 },
      { "current": 6000, "time": 1000 }
    ]
  },
  "downstream": [
    { "id": "QF-feeder-1", "points": [{ "current": 500, "time": 1000 }, { "current": 6000, "time": 6000 }] },
    { "id": "QF-feeder-2", "points": [{ "current": 500, "time": 2000 }, { "current": 6000, "time": 1500 }] }
  ]
}
```

`200 OK`（上例响应，边界为精确有理数）：

```json
{
  "verdict": "fail",
  "intervals": [
    {
      "start": "27700/7",
      "end": "5000",
      "min_current": "5000",
      "min_diff": "-27000/11",
      "responsible": "QF-feeder-1"
    }
  ]
}
```

`422`（整批拒绝：**全部**错误按输入位置 `window → margin → upstream → downstream[i]`
稳定返回，前端据此清除旧图，绝不残留）：

```json
{
  "errors": [
    { "path": "margin", "code": "negative", "message": "裕量必须是非负整数（>= 0）" },
    { "path": "downstream[0].id", "code": "duplicate_id", "message": "标识 'dup' 重复" }
  ]
}
```

错误码：`invalid_json`、`invalid_type`、`missing_field`、`not_positive`、`negative`、
`window_order`、`too_few_points`、`not_strictly_increasing`、`insufficient_coverage`、
`duplicate_id`、`too_few_downstream`。

另有 `GET /api/health` 返回 `{"status": "ok"}`。

## 运行

### Docker Compose（推荐）

```bash
docker compose up --build          # web: http://localhost:8080  api: http://localhost:8000
WEB_PORT=9000 API_PORT=9001 docker compose up --build   # 宿主端口覆盖
docker compose up --build --exit-code-from verify verify   # 一次性验收
```

`web` 容器内 nginx 将 `/api` 反代到 `api:8000`；`verify` 跑完 pytest 即退出，
退出码即验收结果。

### 本地开发

```bash
# 后端（Python 3.12+）
cd api && pip install -r requirements-dev.txt
uvicorn app.main:app --reload          # http://localhost:8000
pytest                                 # 算法 + 契约测试

# 前端（Node 20+）
cd web && npm ci
npm run dev                            # http://localhost:5173（/api 代理到 8000）
npm test                               # Vitest 单元测试
npx playwright install chromium        # 首次需要系统依赖：npx playwright install-deps
npm run test:e2e                       # Playwright 真实联调（自动拉起 api 与 web）
```

## 目录结构

```
├── docker-compose.yml      # web / api / verify 三服务，WEB_PORT、API_PORT 覆盖宿主端口
├── api/                    # FastAPI：core.py(精确算法) validation.py(整批校验) main.py(契约)
│   └── tests/              # pytest：算法单元 + API 契约
├── web/                    # React + TS + Vite
│   ├── src/                # App / CurveChart(SVG) / IntervalList / rational(精确解析)
│   │   └── __tests__/      # Vitest
│   └── e2e/                # Playwright 真实联调
└── verify/                 # 一次性验收服务（pytest 打运行中的 api/web）
```
