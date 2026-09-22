# 对外发布稳定的预测响应信封

`/v1/predict` 只公开 `request_id`、`model`、`routing`、`answers`、`usage` 和 `meta`，不会自动透传 Laya 新增的未知顶层字段；其中 `model` 表示 WindLaya 的已选模型，而不是 Laya 当前固定返回的内部标识 `laya-rl-agent`。这一边界用少量适配代码换取稳定的公共 API，避免上游升级在没有 WindLaya 版本变更的情况下改变客户端契约。
