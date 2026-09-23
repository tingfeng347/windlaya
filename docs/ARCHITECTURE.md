# WindLaya 架构

## 请求链路

```text
Request
  -> FastAPI Router
  -> Schema Validation
  -> DecisionService
  -> ModelManager
  -> Laya Router
  -> Language Detection / Explicit Selection
  -> Laya Agent
  -> choice / score / noul
```

FastAPI 负责 HTTP、Request ID 和错误信封。`DecisionService` 负责稳定的 API 响应结构、
耗时和业务日志。`ModelManager` 是唯一接触 `laya.Router` 的模块，拥有模型生命周期、
设备一致性检查和进程内推理锁。

## 路由模式

`auto` 不向 Laya 传递 model 参数，由 Laya 根据显式 `lang` 或状态语言选择 English 或
Multilingual。显式模型会先规范化别名，再直接传递给 Laya；它的优先级高于 `lang`。
WindLaya 关闭 Laya 的自动 task detection，因此 typed-decisions 只能显式选择。

`/v1/route` 只调用 `Router.route()`，不会加载 checkpoint。`/v1/predict` 先路由，确认对应
本地制品已经由部署流程校验，再显式加载并检查 Agent 的实际设备，最后调用 `Router.predict()`。

## 模型制品

`ModelArtifactProvider` 隔离远程 Hub 与 Laya。`windlaya-models download` 在构建或部署阶段
默认从固定 ModelScope commit 下载必要文件，失败时回退到固定 Hugging Face commit，并按
Hugging Face 来源的 SHA256 manifest 完整校验。校验成功的目录通过原子 rename 发布；运行时
只检查 marker、文件存在性和大小，不执行网络请求或重复计算大文件哈希。

`ModelManager` 将三个本地目录通过 `Router(models=...)` 注入 Laya。ModelScope/Hugging Face
类型不会进入 API 或 service 层。`local` 来源可用 `windlaya-models verify --publish-marker`
校验并接管人工准备的目录。

## 生命周期

FastAPI lifespan 创建和启动进程级 `ModelManager`，关闭时调用 `Router.unload()`。
默认只从本地目录预加载 Multilingual。显式选择其他模型时由 Router 动态热加载；`max_loaded` 控制
常驻 checkpoint 数量，超限后按 LRU 淘汰，且不得小于预加载模型数。每个 Uvicorn worker
都有独立模型副本，所以 MVP 只支持单 worker。

## 设备策略

`auto` 按 CUDA、MPS、CPU 的顺序选择可用设备。显式不可用设备会在启动时失败。如果
Laya 因显存不足静默将某个 Agent 放到 CPU，WindLaya 会检测设备不一致并拒绝加载，避免
健康状态与真实执行位置不一致。

## 并发

PyTorch 推理是阻塞计算，FastAPI 用同步 endpoint 在线程池执行。默认锁覆盖 checkpoint
加载和完整 predict 调用，优先保证 Router LRU 与模型状态稳定。关闭该锁是实验行为。

## 响应与错误

WindLaya 不透传未知 Laya 顶层字段。预测响应固定为 `request_id`、`model`、`routing`、
`answers`、`usage` 和 `meta`。加载、不可用和推理错误分别映射为稳定错误码，原始异常只
进入服务端日志。

## Playground 边界

`streamlit_app.py` 是独立的演示入口，只通过 HTTP 调用 FastAPI 的 `/health`、`/v1/models`、
`/v1/route` 和 `/v1/predict`，不会导入 `DecisionService`、`ModelManager` 或 Laya。这样演示端
不会绕过公共 API，也能在后端独立部署或不可用时显示明确的离线状态。Streamlit 依赖位于独立的
`playground` 依赖组；会话历史只保存在浏览器会话的内存中，不写入模型或业务数据。
