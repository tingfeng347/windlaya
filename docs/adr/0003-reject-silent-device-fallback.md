# 拒绝模型加载时的静默设备降级

WindLaya 在每次加载 checkpoint 后核对 Laya Agent 的实际设备，只要它与配置解析出的设备不一致，就卸载模型并返回 `503 MODEL_LOAD_ERROR`，即使上游 Laya 已因 CUDA 或 MPS 加载失败而自动退回 CPU。该选择牺牲自动恢复能力，以保证 `/health`、日志和性能预期不会与真实执行设备失配；需要 CPU fallback 的部署必须显式配置 `WINDLAYA_DEVICE=cpu`。
