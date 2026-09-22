# WindLaya API

服务默认地址为 `http://127.0.0.1:8000`。所有响应包含 `X-Request-ID`，调用方可传入
1 到 128 个无空白可见 ASCII 字符作为该 Header。

## GET /

返回服务名称、版本和状态。

```bash
curl http://127.0.0.1:8000/
```

```json
{"name":"windlaya","version":"0.1.0","status":"ok"}
```

## GET /health

返回实际设备、已加载 checkpoint 和默认模型，不触发模型加载。

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status":"ok","device":"cpu","loaded_models":[],"default_model":"english"}
```

## GET /v1/models

列出 `auto`、`english`、`multilingual` 和 `typed-decisions` 及当前常驻模型。

```bash
curl http://127.0.0.1:8000/v1/models
```

## POST /v1/route

请求字段与 predict 相同，但只返回路由结果，不执行模型 forward。

```bash
curl -X POST http://127.0.0.1:8000/v1/route \
  -H 'Content-Type: application/json' \
  -d '{
    "state":"我需要退款",
    "model":"auto",
    "questions":{"refund":{"type":"noul","instructions":"用户是否要求退款？"}}
  }'
```

```json
{
  "request_id":"...",
  "requested_model":"auto",
  "selected_model":"multilingual",
  "reason":"...",
  "workflow":null,
  "detection":{}
}
```

## POST /v1/predict

`state` 可以是字符串、JSON 对象或列表。`questions` 至少包含一个具名问题：

- `choice`：`criteria` 是至少两个标签的对象。
- `score`：`criteria` 是至少两个有序 level 的列表。
- `noul`：`criteria` 可省略，或提供 `false`、`true` 的说明。

```bash
curl -X POST http://127.0.0.1:8000/v1/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "state":"I was charged twice. Please refund me.",
    "model":"auto",
    "questions":{
      "refund":{"type":"noul","instructions":"Does the user request a refund?"}
    }
  }'
```

```json
{
  "request_id":"...",
  "model":"english",
  "routing":{"model":"english","repo":"convaiinnovations/laya","reason":"..."},
  "answers":{"refund":{"type":"noul","noul":0.91,"confidence":0.91}},
  "usage":{"input_tokens":18,"output_tokens":0},
  "meta":{"api_version":"v1","device":"cpu","elapsed_ms":120.5}
}
```

## 错误

错误响应不会包含 Python traceback：

```json
{
  "error":{
    "code":"INVALID_MODEL",
    "message":"...",
    "request_id":"..."
  }
}
```

| HTTP | code | 含义 |
|---|---|---|
| 400 | `INVALID_MODEL` | 未知模型或别名 |
| 400 | `INVALID_REQUEST` | 非法 Request ID 等请求错误 |
| 422 | `INVALID_REQUEST` | JSON 或 Schema 校验失败 |
| 503 | `MODEL_LOAD_ERROR` | checkpoint 下载或加载失败 |
| 503 | `MODEL_UNAVAILABLE` | Router 尚不可用 |
| 500 | `INFERENCE_ERROR` | 路由或模型 forward 失败 |

未知请求字段会被拒绝。模型别名可用于请求，但所有响应都使用标准模型名。
