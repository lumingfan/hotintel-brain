# llm-project 文档索引

`HotIntel Brain` 副项目的文档入口。这里只放轻量但稳定的工作上下文。

## 先读哪些

1. `STATUS.md` — 副项目当前阶段与下一步
2. `WORKFLOW.md` — 仓库工作流（提交、文档版本、ADR 触发条件）
3. `specs/direction.md` — 副项目定位、与 HotPulse 衔接、不做的部分
4. `specs/three-layer-capability.md` — L1 / L2 / L3 能力定义与递进逻辑
5. `architecture.md` — 服务架构、数据流、降级策略
6. `api/contract.md` — `/v1/judge` 等接口契约
7. `eval/protocol.md` — 评测协议、指标定义、报告模板
8. `data/labeling-guide.md` — 标注口径
9. `roadmap.md` — V1 / V2 / V3 阶段切片
10. `runbooks/` — 本地启动、跑评测、对接 HotPulse 的可重复操作
11. `adr/` — 关键技术取舍
    - `0001-language-and-runtime.md` — Python + FastAPI + uv + ruff
    - `0002-rag-on-shared-elasticsearch.md` — 共用 HotPulse ES，不引入独立向量库
    - `0003-structured-output-and-agent-framework.md` — instructor + Pydantic AI
    - `0004-observability-with-langfuse.md` — Langfuse 自托管
    - `0005-evaluation-stack.md` — DeepEval + ragas + 自写 metric

## 原则

- 文档保持简短、常新
- 每类信息只保留一个事实来源
- 实验结果留在 `eval/reports/` 而不是散落在各 spec
- 任何长篇结论先写 ADR，再回写其他 spec
