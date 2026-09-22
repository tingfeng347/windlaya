# WindLaya 使用 ModelScope 下载 Laya Checkpoint 的方案调研

> 调研日期：2026-09-22  
> 范围：`windlaya` 当前代码、Laya 0.3.5、ModelScope/ModelScope Hub 当前官方接口。本文只讨论模型制品获取，不改变 WindLaya 的推理 API。

## 结论

Laya 确实提供 Python SDK，当前项目已经在使用它：`pyproject.toml` 依赖 `laya>=0.3.4,<0.4`，实际锁定环境为 `laya==0.3.5`，`ModelManager` 持有一个 `laya.Router`。但 Laya SDK **没有 ModelScope 下载后端**。远程模型 ID 会在 `laya.Agent` 内部固定交给 `huggingface_hub.snapshot_download()`；它同时接受本地 checkpoint 目录。因此 ModelScope 不能通过改一个 endpoint 或 token 直接替换 Laya 当前的 Hugging Face 下载链路。[Laya `agent.py`](https://github.com/NandhaKishorM/laya/blob/main/laya/agent.py) [Laya `router.py`](https://github.com/NandhaKishorM/laya/blob/main/laya/router.py)

截至调研日，ModelScope 确实存在 `convaiinnovations/laya`、`convaiinnovations/laya-multilingual`、`convaiinnovations/laya-typed-decisions` 三个可下载仓库。它们是 2026-09-20 建立的社区镜像，组织页面明确声明并非原作者官方所有；因此 Hugging Face 仍是权威来源，ModelScope 可作为经过校验的分发镜像。[Laya ModelScope bundle](https://modelscope.cn/models/convaiinnovations/laya) [Laya Hugging Face bundle](https://huggingface.co/convaiinnovations/laya)

若项目的目标是改善中国大陆网络下的下载可用性，推荐架构是：

```text
启动/部署阶段
  -> ModelArtifactProvider（hf / modelscope / local）
  -> 得到 3 个本地 checkpoint 目录
  -> laya.Router(models={标准名: 本地目录})
  -> 现有 ModelManager / 单 Router / LRU / 设备检查 / 推理锁
```

即让 ModelScope 只负责“制品供应”，Laya 仍负责“模型加载和推理”。不要 fork Laya，也不要 monkey-patch `huggingface_hub`。本项目决定默认使用 ModelScope，并在部署期失败时回退到 Hugging Face；无论来源如何，都以 Hugging Face 固定 revision 的文件 manifest 作为验收基准。

## 当前事实

### 1. Laya SDK 已经自动下载模型

Laya 0.3.5 的 `Agent(model_id_or_path, ...)` 先判断参数是否为本地现存路径；不是本地路径时，导入 `huggingface_hub.snapshot_download` 并下载以下必要文件：

- `rl_agent_config.json`
- `model.safetensors`
- `tokenizer/*`
- `encoder/*`

其 `allow_patterns` 会避免把 bundle 中不需要的 sibling checkpoint 全部下载。`Router` 默认把 English 指向 bundle 根目录，把 Multilingual 和 Typed Decisions 指向 bundle 子目录；也支持通过 `models` 参数覆盖为自定义 repo 或本地路径。[Laya `agent.py`](https://github.com/NandhaKishorM/laya/blob/main/laya/agent.py) [Laya `router.py`](https://github.com/NandhaKishorM/laya/blob/main/laya/router.py)

WindLaya 目前在 `app/core/model_manager.py` 创建 Router 时传入 device、Hugging Face token、LRU 容量、默认模型和 task detection 配置，但没有传 `models`。默认启动预加载 Multilingual，其他 checkpoint 热加载。这与 `docs/ARCHITECTURE.md` 的单进程、单 Router、单 worker 设计一致。

### 2. ModelScope 提供下载 SDK，但前提是模型已在其 Hub

ModelScope 官方 `snapshot_download` 支持 `revision`、`cache_dir`、`local_dir`、文件 include/exclude pattern、token、endpoint 和 `local_files_only`，并返回本地目录字符串。CLI 也支持等价的 `--revision`、`--cache_dir`、`--local_dir`、`--include` 和 `--exclude`。[ModelScope 实现](https://github.com/modelscope/modelscope/blob/master/modelscope/hub/snapshot_download.py) [ModelScope CLI 文档](https://github.com/modelscope/modelscope/blob/master/docs/source/command.md)

对 WindLaya 这种只需要 Hub 下载、不需要 ModelScope 训练或 pipeline 的服务，优先考虑官方轻量包 `modelscope-hub`，而不是完整 `modelscope`。官方说明其仅依赖 `requests`、`tqdm`、`filelock`、`urllib3`，提供断点续传、并行下载、SHA256 完整性检查、多进程文件锁和离线模式；兼容入口为 `from modelscope_hub.compat import snapshot_download`。[modelscope-hub README](https://github.com/modelscope/modelscope_hub/blob/main/README.md) [兼容 API 源码](https://github.com/modelscope/modelscope_hub/blob/main/src/modelscope_hub/compat/snapshot_download.py)

### 3. ModelScope 有可用但非官方的社区镜像

Laya 官方模型卡列出的发布位置是 Hugging Face，bundle 当前包含三套权重；模型元数据声明 Apache-2.0。[Laya bundle 文件树](https://huggingface.co/convaiinnovations/laya/tree/main) [Laya 模型卡](https://huggingface.co/convaiinnovations/laya/raw/main/README.md)

ModelScope 三个社区镜像都只有 `master` 分支。通过 ModelScope API 与 Hugging Face API 对比，三个 `model.safetensors` 的 SHA256 完全一致：

| Checkpoint | SHA256 |
|---|---|
| English | `891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c` |
| Multilingual | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` |
| Typed Decisions | `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e` |

这证明调研时的权重内容一致，但不把社区镜像升级成官方来源，也不保证未来 `master` 永远不漂移。实际验证还确认 `modelscope==1.40.1` 的 `snapshot_download(..., allow_patterns=["rl_agent_config.json"])` 只下载一个匹配文件并返回 `local_dir`；传完整 commit SHA 给 `revision` 也能成功。可固定的 ModelScope revision 是：

- bundle：`0d52b645226dc836d8efdb7e9dc197ddca7b98c9`
- multilingual standalone：`5ad6e84d70d70edde0d5a3241c5233d0b11cd6b8`
- typed-decisions standalone：`9407bd3545af9115f4799f4f4e11801e05b0600b`

English standalone 就是 bundle 根目录。上线仍应通过 ModelScope API 按准确 repo ID 和 revision 复核，并校验所有必需文件，而不只校验权重。

## Context7 与 Tavily 调研记录

- Context7 对 `Laya` 的解析只返回无关的 LayaAir 游戏引擎文档，没有覆盖本项目的 Python Laya SDK。因此 Laya 结论改以官方 GitHub 源码、PyPI 发布信息和 Hugging Face 模型仓库验证。
- Context7 能解析官方 `/modelscope/modelscope`；其文档确认 `snapshot_download()` 和 `modelscope download` 的基本用法，但未单独索引 2026 年拆出的 `modelscope-hub` 包。
- Tavily 用官方域名白名单补查了 `github.com/modelscope`、`github.com/NandhaKishorM`、`modelscope.cn`、`huggingface.co/convaiinnovations` 和 `pypi.org`；ModelScope 动态模型页未被 Tavily 稳定抽取，因此仓库存在性、revision 和 hash 另通过 ModelScope/Hugging Face API 直接验证。
- PyPI 显示 Laya 0.3.5 的 wheel 由其 GitHub Actions 发布并带 provenance attestation，可用于锁定 SDK 来源。[PyPI laya](https://pypi.org/project/laya/)

## 方案比较

| 方案 | 现在可用 | 改动 | 供应链风险 | 建议 |
|---|---:|---:|---:|---|
| 保持 Laya 原生 Hugging Face 下载 | 是 | 无 | 依赖 HF 网络；当前来源最权威 | 不采用，运行期不应下载 |
| 部署时预下载 HF snapshot，再给 Laya 本地路径 | 是 | 小 | 需管理目录、revision 和缓存 | **离线部署首选** |
| 从现有 ModelScope 社区镜像下载，再给 Laya 本地路径 | 是 | 中 | 非官方镜像，必须固定 revision 和校验 hash | **项目默认** |
| 建立团队自有 ModelScope 镜像 | 是 | 中到大 | 团队承担同步、许可、完整性和版本管理 | 供应链要求更高时采用 |
| 直接把 ModelScope repo ID 传给 Laya | 否 | 看似小 | Laya 会把它当 HF repo ID | 不采用 |
| 修改/monkey-patch Laya 的下载函数 | 技术上可做 | 中到大 | 上游升级脆弱、测试面扩大 | 不采用 |
| 同时安装完整 `modelscope` 仅为下载 | 是 | 小 | 不必要的依赖和漏洞面 | 不推荐，使用 `modelscope-hub` |

## 推荐设计

### 第一阶段：固定双源版本并让制品可复现

Laya 作者没有在 ModelScope 官方发布，因此 ModelScope 作为默认分发镜像、Hugging Face 作为备选和权威校验源。无论使用哪个 Hub，都先做以下运维收敛：

1. 在构建或部署阶段显式预取，而不是让生产进程第一次请求时下载。
2. 固定 Hugging Face commit SHA，而非漂移的 `main`。调研时 bundle API 返回的 revision 是 `1c5edc17a7acd8701df6fc341c0d179f1c62c982`；实施时必须重新核对并由项目配置持有，不要把本文中的 SHA 永久视为最新版本。[Hugging Face model API](https://huggingface.co/api/models/convaiinnovations/laya)
3. 持久化并挂载 cache；容器镜像内是否打包权重取决于发布体积和许可策略。
4. 启动时继续 preload + fail-fast。WindLaya 已将下载/加载异常转为 `ModelLoadError`，且能拒绝 Laya 的静默设备回退。

### 第二阶段：按部署环境启用 ModelScope provider

优先按三个 standalone 目录下载：Multilingual 和 Typed Decisions 使用各自仓库，English 使用 bundle 根目录但必须用 `allow_patterns` 排除两个子目录：

```text
convaiinnovations/laya
convaiinnovations/laya-multilingual
convaiinnovations/laya-typed-decisions
```

每个仓库根目录保留 Laya 要求的四类文件。这样 `Router.models` 的值都是普通本地路径，不依赖 Laya 内部的 tuple/subfolder 表示：

```python
from modelscope_hub.compat import snapshot_download
from laya import Router

required_files = [
    "rl_agent_config.json",
    "model.safetensors",
    "tokenizer/*",
    "encoder/*",
]

paths = {
    "english": snapshot_download(
        "convaiinnovations/laya",
        revision="0d52b645226dc836d8efdb7e9dc197ddca7b98c9",
        local_dir="/var/lib/windlaya/models/english",
        allow_patterns=required_files,
    ),
    "multilingual": snapshot_download(
        "convaiinnovations/laya-multilingual",
        revision="5ad6e84d70d70edde0d5a3241c5233d0b11cd6b8",
        local_dir="/var/lib/windlaya/models/multilingual",
        allow_patterns=required_files,
    ),
    "typed-decisions": snapshot_download(
        "convaiinnovations/laya-typed-decisions",
        revision="9407bd3545af9115f4799f4f4e11801e05b0600b",
        local_dir="/var/lib/windlaya/models/typed-decisions",
        allow_patterns=required_files,
    ),
}

router = Router(models=paths, ...)
```

这是说明接口边界的草图，不应直接放进 `ModelManager.startup()`。更合适的做法是增加一个小型 `ModelArtifactProvider`，由 CLI/FastAPI lifespan 在创建 Router 前调用；`ModelManager` 仍只管理 Router 和内存中 Agent。下载锁、重试和原子目录发布应在 provider 内完成，不能持有当前推理锁做长时间网络下载。

建议新增配置语义：

| 配置 | 示例 | 说明 |
|---|---|---|
| `WINDLAYA_MODEL_SOURCE` | `huggingface` / `modelscope` / `local` | 默认保持 `huggingface` |
| `WINDLAYA_MODEL_ROOT` | `/var/lib/windlaya/models` | 统一的本地制品目录 |
| `WINDLAYA_MODEL_MANIFEST` | manifest 文件路径 | 保存每个模型各自的 repo、commit 和文件 hash |
| `WINDLAYA_MS_TOKEN` | secret | 仅私有/受限 ModelScope repo 需要 |

不要复用 `WINDLAYA_HF_TOKEN` 表示 ModelScope token；两个 secret 的权限域不同。

## 迁移步骤

1. **确认来源和许可**：验证 Laya 模型卡、LICENSE、NOTICE/归属要求；记录社区镜像、上游 repo 和精确 commit 的关系。Apache-2.0 元数据允许宽松使用，但组织仍应完成自己的许可证审查。
2. **生成制品 manifest**：从固定 Hugging Face commit 和固定 ModelScope commit 分别读取三套必需文件，记录每个文件 SHA256、大小和来源。若任何文件不一致则拒绝发布；供应链要求更高时，将通过校验的文件同步到团队自有 namespace。
3. **验证结构**：每个镜像根目录必须至少包含 `rl_agent_config.json`、`model.safetensors`、`tokenizer/`、`encoder/`。用 `laya.load(local_path, device="cpu")` 做离线 smoke test。
4. **增加 provider 抽象**：只返回 `{model_name: local_path}`，不泄漏 ModelScope 类型到 API/service 层；Router factory 接收该映射。
5. **双源一致性测试**：对同一组固定输入，分别加载 HF 制品和 ModelScope 镜像，校验文件 hash 相同、路由结果相同、概率输出在确定性条件下相同。
6. **灰度上线**：ModelScope 先作为显式 opt-in；下载失败不得悄悄切换到另一 revision。是否允许回退到 HF 应作为部署策略明确配置并记录日志。
7. **离线验收**：完成一次联网预取后断网启动，运行现有 multilingual 集成测试、smoke test，并验证重启不产生网络请求。

## 主要风险与控制

- **社区镜像冒名或失控**：现有 ModelScope namespace 并非 Laya 作者官方所有；白名单精确 repo ID 和 commit，并以 Hugging Face 上游 hash manifest 为准。更高信任等级应使用团队自有镜像。
- **模型漂移**：固定 revision 和文件 SHA256；不要使用浮动 `master/main`。ModelScope SDK 自带 SHA256 校验，但仍需把期望 manifest 纳入发布流程。
- **目录布局不兼容**：Laya 不读取 ModelScope 元数据，只读取上述 checkpoint 文件；下载后必须在本地用 Laya 加载验证。
- **半下载目录被读取**：使用 SDK 文件锁/原子下载能力，并在 manifest 验证完成后才切换 active 目录。
- **重复占用磁盘**：`local_dir` 会绕过普通 cache 语义；在 `cache_dir` 与发布目录方案中二选一，避免同一权重保存两份。[ModelScope CLI 文档](https://github.com/modelscope/modelscope/blob/master/docs/source/command.md)
- **启动时间过长**：模型下载与构建镜像/部署阶段分离；运行时只校验并加载。当前默认预加载 Multilingual 的行为保持不变。
- **依赖膨胀**：仅下载时使用 `modelscope-hub`，并锁定版本；不要引入完整训练框架。
- **多 worker 重复模型**：本方案不改变现有单 worker 约束；每个 worker 仍会持有自己的模型内存副本。

## 最终决策建议

**不要把 Laya 内部下载直接改写成 ModelScope，而应使用独立的 ModelScope 制品 provider。** 默认使用已验证的三个 ModelScope standalone 社区镜像，固定上述 commit SHA；失败时从 Hugging Face 固定 commit 获取，并始终以 Hugging Face 的全文件 hash manifest 验收。若不能接受社区镜像信任边界，再同步到团队自有 namespace。provider 的输出只应是本地目录，后续仍交给现有 `laya.Router`。

这个方案改动集中在启动期，保留了 WindLaya 当前最重要的边界：单 `ModelManager`、单 Router、默认只预加载 Multilingual、其他模型动态热加载、设备一致性检查和稳定 HTTP 契约。
