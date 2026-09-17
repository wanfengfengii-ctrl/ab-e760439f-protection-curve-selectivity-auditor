# 配电柜上下级保护曲线 · 选择性精确审查

FastAPI + Python 3.12（后端）与 React + TypeScript + Vite（前端）全栈应用。
用于审查配电柜中**一个上级**与**至少两个下级**保护器的时间‑电流曲线，在
给定的**闭合审查窗**内是否保持选择性。

核心不做采样画图：所有内部坐标、交点与区间边界都用整数构造并以
**约分有理数**精确给出，狭窄到只剩单个电流点的“零长度接触”也不会被漏掉。

---

## 1. 数据约定（重要）

### 1.1 单位与类型

所有物理量都以**整数计数**表示，禁止小数、布尔或字符串：

| 字段 | 含义 | 单位 | 取值 |
| --- | --- | --- | --- |
| `window.lo` / `window.hi` | 闭合审查窗下界 / 上界电流 | 微安 μA | 正整数，`lo <= hi` |
| `margin` | 允许的时间裕量 | 微秒 μs | **非负整数**（可为 0） |
| `points[].current` | 折点电流 | 微安 μA | **正整数**，曲线内**严格递增** |
| `points[].time` | 折点动作时间 | 微秒 μs | **正整数** |
| `id` | 保护器标识 | — | 非空字符串，上、下级之间**唯一** |

> 微安 / 微秒是最小整数粒度。若实际数据是毫安或秒，请先换算成整数微安 / 微秒。

### 1.2 结构约束

- 一个 `upstream`（上级）；
- `downstream` 至少 **2** 个下级；
- 每条曲线 `points` 至少 **2** 个折点；
- 折点电流必须**严格递增**（相等即非法）；
- 每条曲线必须**覆盖整个闭合审查窗**：
  首折点电流 `<= window.lo` 且末折点电流 `>= window.hi`；
- 折点之间**按电流线性插值**；
- 上、下级 `id` 不得重复。

任一项不满足都会**整批拒绝**（HTTP 422），一次性返回所有错误，按输入位置
（window → margin → upstream → downstream[i]）稳定排列；前端据此清空旧图，
绝不残留上一次的分析结果。

### 1.3 请求示例

```json
{
  "window": { "lo": 1, "hi": 7 },
  "margin": 0,
  "upstream": {
    "id": "U",
    "points": [
      { "current": 1, "time": 10 },
      { "current": 7, "time": 4 }
    ]
  },
  "downstream": [
    {
      "id": "D1",
      "points": [
        { "current": 1, "time": 5 },
        { "current": 7, "time": 5 }
      ]
    },
    {
      "id": "D2",
      "points": [
        { "current": 1, "time": 1 },
        { "current": 7, "time": 1 }
      ]
    }
  ]
}
```

更多示例见 [`examples/`](examples/)：安全、分数边界、零长度接触。

---

## 2. 判定与精确语义

记审查窗为 `[lo, hi]`：

1. 对所有下级曲线在每个电流处取**逐段最大上包络** `E(x)`（分段线性）。
2. 上级曲线为 `U(x)`，定义差值 `d(x) = U(x) − E(x)`。
3. 当且仅当 `d(x) <= margin` 时，电流 `x` 处**失去选择性（不选择）**。
4. 不选择集合是若干**极大闭区间**：
   - **端点属于结果**（含等号，判的是 `<=`）；
   - 两个在端点处**接触**的闭区间会合并为一个；
   - 仅在单个电流点相切形成的**零长度接触 `[r, r]` 会被保留**。
5. 每个极大区间返回：
   - 精确有理端点 `lo`、`hi`；
   - 区间内 `d(x)` 的最小值 `min_diff`；
   - 取到该最小值的电流 `min_current`；
   - 责任下级 `responsible`（该电流处构成上包络的下级）。
6. 并列裁决规则（确定性）：
   - 差值并列时先取**最小电流**；
   - 同一电流仍并列（多条下级等值）时取 `id` **字典序最小**者。

### 为什么边界是精确的

整数输入进入算法后，斜率、截距、两线交点全部用
`fractions.Fraction`（约分有理数）表示，全程**无浮点**。对外把每个边界
序列化为 `{ "num": 分子, "den": 分母 }`（分母恒正、已约分）。前端显示
形如 `7/2 (≈3.5000)`：**分数是精确边界，小数仅为工程近似**。SVG 像素定位
才使用浮点，不影响返回的数学边界。

---

## 3. HTTP 契约

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /api/analyze`

成功 `200`：

```json
{
  "safe": false,
  "intervals": [
    {
      "lo": { "num": 6, "den": 1 },
      "hi": { "num": 7, "den": 1 },
      "min_diff": { "num": -1, "den": 1 },
      "min_current": { "num": 7, "den": 1 },
      "responsible": "D1"
    }
  ],
  "envelope": [
    {
      "lo": { "num": 1, "den": 1 },
      "hi": { "num": 7, "den": 1 },
      "lo_time": { "num": 5, "den": 1 },
      "hi_time": { "num": 5, "den": 1 },
      "responsible": "D1"
    }
  ],
  "window": { "lo": 1, "hi": 7 }
}
```

- `safe: true` 且 `intervals: []` 表示**全窗安全，审查通过**；
- `envelope` 是精确上包络分段（有理端点），供前端叠绘。

整批校验失败 `422`：

```json
{
  "errors": [
    { "path": ["margin"], "message": "裕量必须是非负整数（微秒 us）" },
    { "path": ["downstream", 0, "points", 0, "current"], "message": "电流必须是正整数（微安 uA）" }
  ]
}
```

请求体不是合法 JSON / 不是对象时返回 `400`。

---

## 4. 前端

- 左侧多行 JSON 编辑器，可直接编辑或**上传 `.json` 文件**；
- “提交审查”调用后端；非法时整批列出错误并清空图区；
- 右侧 **SVG 叠绘**：上级、各下级、精确上包络（黑色虚线）与红色非选择
  区间带；零长度接触用红色竖线 + 菱形显式标出；
- 区间结果列表：边界以精确分数显示；**鼠标悬停某行会高亮图中对应区间
  与责任曲线**（其余曲线变淡），反之悬停图带也会联动；
- 全窗安全时显示明确的“审查通过”横幅。

---

## 5. 本地开发与测试（不使用 Docker）

### 后端（需要 Python 3.12；本地用 3.11 亦可跑测试）

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest                 # 算法 + 整批校验 + API 契约
```

### 前端（Node 22）

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 ，/api 自动反代到 :8000
npm test               # Vitest：有理数 / 几何 / API 客户端
npm run build          # 类型检查 + 生产构建
npx playwright install chromium
npm run pw             # Playwright 真实联调（自动拉起 api 与 web 预览）
```

> Playwright 在受限环境若缺少浏览器系统库，可设置 `PW_NO_SANDBOX=1`
> 并为浏览器提供所需动态库后再 `npm run pw`。

---

## 6. Docker Compose

三个服务：长期运行的 `web`、`api`，以及**一次性**验收服务 `verify`
（成功后退出，用于交付门禁）。

```bash
# 构建并启动长期服务
docker compose up -d --build web api
# 浏览器打开 http://localhost:8080 （web）；api 在 http://localhost:8000

# 一次性端到端验收：真实请求 api，并经 web(nginx) 反代比对结果一致性
docker compose run --rm --build verify
```

宿主端口可用环境变量覆盖：

```bash
WEB_PORT=8080 API_PORT=9000 docker compose up -d --build
```

| 服务 | 容器端口 | 宿主端口（默认 / 覆盖变量） | 说明 |
| --- | --- | --- | --- |
| `web` | 80（nginx） | `8080` / `WEB_PORT` | 托管静态文件并反代 `/api`、`/health` |
| `api` | 8000（uvicorn） | `8000` / `API_PORT` | FastAPI |
| `verify` | — | 不暴露 | 运行一次 `verify/verify.py` 后退出 |

`verify` 会等待两服务健康，再断言：健康检查、整数 / 分数精确边界、
责任下级、上包络分段、web 与 api 结果一致、全窗安全、以及 422 整批拒绝。

---

## 7. 目录结构

```
backend/            FastAPI + 精确算法（Fraction）+ pytest
  app/
    algorithm.py      上包络、差值、下水平集、极大闭区间合并（核心）
    validation.py     整批校验，错误按输入位置稳定返回
    serialization.py  Fraction -> {num, den}
    main.py / models.py
frontend/           React + TS + Vite
  src/lib/            有理数 / SVG 几何 / API 客户端（含 Vitest）
  src/components/     Chart(SVG) / IntervalList / JsonEditor
  e2e/                Playwright 真实联调
verify/             一次性端到端验收脚本与镜像
examples/           安全 / 分数边界 / 零长度接触 示例输入
docker-compose.yml
```
