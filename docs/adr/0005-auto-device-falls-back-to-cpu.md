# 自动设备优先 GPU 并回退 CPU

`WINDLAYA_DEVICE=auto` 按 CUDA、MPS、CPU 的顺序选择设备。若 GPU 在模型加载阶段不可用，
WindLaya 接受 Laya 回退到 CPU，并将进程的实际设备更新为 CPU，使 `/health`、日志和推理响应
保持一致。

显式配置 `WINDLAYA_DEVICE=cuda` 或 `mps` 表示部署方要求该设备，因此仍拒绝任何设备回退并
返回模型加载错误。这样，本地默认启动具有可恢复性，而要求固定性能特征的部署仍可采用严格模式。
