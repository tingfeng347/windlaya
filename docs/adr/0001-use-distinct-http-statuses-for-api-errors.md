# 为 API 错误使用可区分的 HTTP 状态

WindLaya 将未知模型映射为 `400 INVALID_MODEL`，将请求结构或字段错误映射为 `422 INVALID_REQUEST`，将模型加载失败和模型不可用分别映射为 `503 MODEL_LOAD_ERROR` 与 `503 MODEL_UNAVAILABLE`，并将推理执行失败映射为 `500 INFERENCE_ERROR`。原始规范对模型加载失败同时使用了 500 和 503；选择 503 可以让调用者把可能通过重试恢复的模型可用性问题与服务内部推理错误区分开。
