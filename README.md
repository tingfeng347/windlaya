# WindLaya

WindLaya 是一个可本地部署的多语言 Laya System-1 Decision API。它通过统一的
FastAPI 接口提供 `choice`、`score` 和 `noul` 判断，并根据语言自动选择 English 或
Multilingual checkpoint，也允许调用方显式选择模型。

## 功能

- 中文、英文、日文、德文及其他多语言自动路由
- `auto`、`english`、`multilingual`、`typed-decisions` 四种模型模式
- CPU、CUDA、MPS 设备选择
- checkpoint 预加载、LRU 常驻上限和进程内串行保护
- Request ID、统一错误信封和 OpenAPI 文档
- 完全离线的单元测试与显式启用的真实模型测试

## 架构

```text
HTTP -> FastAPI -> DecisionService -> ModelManager -> laya.Router -> checkpoint
```

API 层不直接接触 Laya。进程中只有一个 `ModelManager` 和一个 `Router`，因此本地部署
必须使用单 worker，避免每个 worker 重复占用模型内存。详见
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 支持模型

| 模式 | checkpoint | 用途 |
|---|---|---|
| `auto` | 自动选择 | 英文选 English，其他语言选 Multilingual |
| `english` | `convaiinnovations/laya` | 英文通用决策 |
| `multilingual` | `convaiinnovations/laya-multilingual` | 中文及 100+ 语言 |
| `typed-decisions` | `convaiinnovations/laya-typed-decisions` | 专项 typed-decisions 工作流 |

别名包括 `en`、`laya`、`multi`、`ml`、`typed` 和 `typed_decisions`。响应始终返回标准名。
`typed-decisions` 不是 English 的高级版本，也不会被 `auto` 静默选中。
Laya Router 可能从等价的 bundle repo subfolder 加载权重，API 模型目录保持使用 standalone ID。

## 环境要求

- Python 3.12
- uv 0.12 或更高版本
- 首次运行所需的 Hugging Face 网络访问，或已经准备好的本地 cache
- 可选 CUDA 或 MPS；CPU 始终受支持

## 安装

```bash
uv sync
cp .env.example .env
```

依赖由 `uv.lock` 固定。第一次加载 checkpoint 会下载权重，之后复用 Hugging Face cache。
可通过 `HF_HOME=/path/to/cache` 改变缓存位置。

## 启动

开发模式：

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

本机服务模式：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

不要增加多个 worker。默认 `device=auto` 且只预加载 Multilingual；首次显式选择 English
或 typed-decisions 时，Laya Router 会动态热加载对应 checkpoint。需要时可明确使用 CPU：

```bash
WINDLAYA_DEVICE=cpu uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

也可将 `WINDLAYA_PRELOAD_MODELS` 设为空实现完全 lazy load。默认 `max_loaded=2`，第三个
checkpoint 热加载时按 LRU 淘汰较久未使用的模型。显式 CUDA/MPS 和自动选择出的设备都
不会在 OOM 后静默退回 CPU；加载失败会直接报告，确保健康信息真实。

OpenAPI 页面位于 `/docs` 和 `/redoc`。

## 中文示例

```bash
curl -X POST "http://127.0.0.1:8000/v1/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "state": {"message": "我的账户昨天被扣了两次款，请尽快帮我退款。"},
    "model": "auto",
    "questions": {
      "intent": {
        "type": "choice",
        "instructions": "判断用户主要诉求",
        "criteria": {
          "refund": "退款、退钱、撤销扣款",
          "technical": "软件、系统或网络问题",
          "sales": "价格、套餐或采购咨询",
          "other": "其他"
        }
      },
      "refund_requested": {
        "type": "noul",
        "instructions": "用户是否明确要求退款？"
      }
    }
  }'
```

预期 `model` 与 `routing.model` 为 `multilingual`。

## 英文示例

```bash
curl -X POST "http://127.0.0.1:8000/v1/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "I was charged twice. Please refund the duplicate payment.",
    "model": "auto",
    "questions": {
      "intent": {
        "type": "choice",
        "instructions": "Classify the primary user intent.",
        "criteria": {
          "refund": "refunds and duplicate payments",
          "technical": "software or system problems",
          "sales": "pricing and purchasing",
          "other": "everything else"
        }
      }
    }
  }'
```

预期 `model` 为 `english`。

## 其他语言与显式选择

日文、德文等非英语输入在 `auto` 下路由到 Multilingual。显式模型的优先级高于语言提示：

```bash
curl -X POST "http://127.0.0.1:8000/v1/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Please refund my duplicate payment.",
    "model": "multilingual",
    "lang": "en",
    "questions": {
      "refund": {
        "type": "noul",
        "instructions": "Does the user explicitly ask for a refund?"
      }
    }
  }'
```

该请求仍使用 `multilingual`。

## 自动路由

`POST /v1/route` 只执行 Laya 的语言分析，不加载 checkpoint，也不执行 neural forward：

```bash
curl -X POST "http://127.0.0.1:8000/v1/route" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "我需要申请退款",
    "model": "auto",
    "questions": {
      "refund": {"type": "noul", "instructions": "用户是否要求退款？"}
    }
  }'
```

显式 `model` 覆盖 `lang`，`lang` 覆盖自动语言检测。无法判断语言时使用
`WINDLAYA_DEFAULT_MODEL`。

## API

- `GET /`：服务元数据
- `GET /health`：设备、默认模型和已加载 checkpoint
- `GET /v1/models`：模型目录
- `POST /v1/route`：仅路由
- `POST /v1/predict`：路由并执行判断

所有响应都有 `X-Request-ID` Header。route、predict 与错误 JSON 也包含 `request_id`。
完整契约见 [docs/API.md](docs/API.md)。

## Docker

```bash
docker build -t windlaya:0.1.0 .
docker run --rm \
  -p 8000:8000 \
  -v windlaya-hf-cache:/root/.cache/huggingface \
  -e WINDLAYA_DEVICE=cpu \
  windlaya:0.1.0
```

镜像构建不会下载 checkpoint；第一次容器启动时下载到挂载的 cache volume。

## 测试

```bash
uv run pytest tests/unit -q
uv run ruff check .
```

真实模型测试默认跳过：

```bash
WINDLAYA_RUN_MODEL_TESTS=true WINDLAYA_DEVICE=cpu uv run pytest tests/integration -q
uv run python scripts/smoke_test.py --model multilingual --device cpu
```

## Benchmark

```bash
uv run python scripts/benchmark.py --model multilingual --runs 20 --warmup 3
```

该脚本测量进程内路由与推理延迟；checkpoint 首次加载发生在计时前。

## 配置项

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `WINDLAYA_HOST` | `127.0.0.1` | CLI 监听地址 |
| `WINDLAYA_PORT` | `8000` | CLI 端口 |
| `WINDLAYA_DEVICE` | `auto` | `auto/cuda/cpu/mps` |
| `WINDLAYA_PRELOAD_MODELS` | `multilingual` | 启动预加载列表，空值表示 lazy load |
| `WINDLAYA_MAX_LOADED` | `2` | 最大常驻 checkpoint 数 |
| `WINDLAYA_DEFAULT_MODEL` | `english` | 无法判断语言时的 English 或 Multilingual |
| `WINDLAYA_HF_TOKEN` | 空 | Hugging Face token，不写入日志 |
| `WINDLAYA_LOG_LEVEL` | `INFO` | 日志级别 |
| `WINDLAYA_RUN_MODEL_TESTS` | `false` | 是否启用真实集成测试 |
| `WINDLAYA_SERIALIZE_INFERENCE` | `true` | 是否串行保护 Router 与推理 |

`WINDLAYA_SERIALIZE_INFERENCE=false` 属于实验选项。只有本机 benchmark 和压力测试证明
Laya/PyTorch 并发稳定且有收益后才应启用。

## 已知限制

- 不提供鉴权、限流、数据库、任务队列、批处理或分布式推理。
- 默认单进程锁使一个 Router 上的推理串行执行。
- 首次 checkpoint 下载和加载耗时不属于推理延迟。
- Laya 候选项共享 `head_max_len` token budget；choice 超过 20 项时 WindLaya 记录 warning，
  但不会拒绝请求。几十或上百个选项可能显著降低准确率。
- `laya-multilingual` 可直接处理中文，但未经业务校准，不应把 confidence 当作高风险动作的
  严格概率阈值。生产阈值必须使用领域 held-out 数据验证和 calibration。
- `typed-decisions` 仅适用于对应专项工作流，必须由调用方显式选择。

## 项目结构

```text
app/                 FastAPI、服务、Schema、配置和 Laya 适配
tests/unit/          无网络、无 checkpoint 的离线测试
tests/integration/   显式启用的真实模型测试
scripts/             smoke test 与进程内 benchmark
docs/                API、架构和 ADR
```

## License 与上游归属

WindLaya 使用 [Apache-2.0](LICENSE)。模型运行能力来自
[NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)，Laya 及对应 checkpoint 的
版权与许可证归其各自权利人所有。
