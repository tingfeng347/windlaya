# WindLaya

WindLaya 是面向本地部署的多语言 System-1 决策服务。本文件约定项目讨论、API 文档与代码中使用的领域语言。

## Language

**决策请求（Decision Request）**:
一次由状态、一个或多个问题以及模型模式组成的判断请求。
_Avoid_: 推理任务、聊天请求

**状态（State）**:
决策请求所依据的原始上下文，可以是文本、对象或列表。
_Avoid_: Prompt、消息

**问题（Question）**:
针对状态提出的一个具名判断，采用 choice、score 或 noul 中的一种决策原语。
_Avoid_: Query、题目

**决策原语（Decision Primitive）**:
Laya 提供的基础判断形态，即 choice、score 和 noul；WindLaya 不改变其语义。
_Avoid_: 任务类型、模型类型

**模型模式（Model Mode）**:
调用者要求的模型选择方式，包括 auto、english、multilingual 和 typed-decisions。
_Avoid_: 模型名称、语言模式

**自动路由（Automatic Routing）**:
模型模式为 auto 时，依据状态的语言选择 english 或 multilingual checkpoint 的行为；它不会自动选择 typed-decisions。
_Avoid_: 自动推理、任务检测

**路由预览（Route Preview）**:
针对决策请求只确定已选模型和选择依据、但不执行模型推理的操作。
_Avoid_: 试运行、预测

**显式模型选择（Explicit Model Selection）**:
调用者直接指定 english、multilingual 或 typed-decisions，并覆盖语言提示与自动路由结果的选择方式。
_Avoid_: 强制路由

**语言提示（Language Hint）**:
调用者提供的可选语言标识，仅在自动路由时辅助选择 checkpoint；其优先级低于显式模型选择。
_Avoid_: 语言检测结果、模型模式

**已选模型（Selected Model）**:
一次决策请求最终使用或将要使用的标准 checkpoint 名称，即 english、multilingual 或 typed-decisions。
_Avoid_: 请求模型、Laya Agent

**Checkpoint**:
承载某一种 Laya 决策能力的模型权重与配置集合。WindLaya 的标准 checkpoint 为 english、multilingual 和 typed-decisions。
_Avoid_: 模型模式、Agent

**noul**:
返回命题为真的概率 `P(true)` 的二元决策原语。该名称沿用 Laya 上游契约，不展开或翻译。

**WindLaya Playground**:
面向业务体验者与开发者、用于构造并执行决策请求的交互式工作台，同时呈现易读结果与开发者细节。
_Avoid_: 聊天页面、聊天机器人、API 浏览器

**示例场景（Example Scenario）**:
用于演示一组 WindLaya 能力的具名决策请求，用户可以载入后继续修改；场景只提供输入，不提供模拟结果。
_Avoid_: Mock、固定结果、Prompt 模板

**倾向结论（Directional Conclusion）**:
根据概率给出的非确定性文字概括，必须与精确概率和置信度一同呈现。
_Avoid_: 最终答案、确定结论
