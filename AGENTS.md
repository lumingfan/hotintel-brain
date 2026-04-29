# llm-project 工作守则

这是 `HotIntel Brain` 副项目的工作守则。在此目录里启动新会话时按下面顺序读：

1. `README.md`
2. `docs/INDEX.md`
3. `docs/STATUS.md`
4. `docs/specs/direction.md`
5. 当前任务文档（如果存在）
6. 与本次工作相关的 `docs/specs/` / `docs/api/` / `docs/eval/`
7. `docs/adr/` 下相关决策

## 文档语言

- 内部工作文档默认中文
- 代码注释、commit message、API 名称用英文
- prompt 模板优先英文（模型对英文 prompt 普遍更稳），输出结构里的内容字段允许中文

## 项目铁律

- **副项目和主项目要一起讲得通**。任何与 HotPulse 主项目无法对接的方向都不进这个仓
- 不做"科研任务"。论文复现、benchmark 跑分、模型架构创新都不是这个仓的目标
- 不微调、不蒸馏、不训练。重心是 prompt / schema / RAG / agent / eval 的工程化
- 不引入 Milvus / Qdrant / Pinecone。共用 HotPulse 的 Elasticsearch
- L1 → L2 → L3 顺序推进。L1 评测稳定前不进 RAG，L2 评测稳定前不进 Agent

## 工作节奏

- 文档先于代码：specs / contract / eval 协议先定，再起 src/
- 同一份 eval 集贯穿 L1 / L2 / L3，不同层之间可比
- 每次 prompt / chain 改动都要留版本号和 diff 说明，eval 报告里能追溯
- 涉及与 HotPulse 主项目的对接契约变更，必须同步回写到 `fullstack-product/docs/api/`

## 范围

- `docs/`: specs / architecture / api / eval / runbook / adr
- `src/`（待起）: FastAPI 服务、prompt 模板、chain、agent、eval 脚本
- `tests/`（待起）: pytest 集成测试、eval 端到端
- `data/`（待起，样本走 git-ignore）: 标注集与 eval 输出

## 提交规范

- conventional commits（`feat:` / `fix:` / `docs:` / `chore:` / `eval:`）
- eval 实验用 `eval:` 前缀，commit message 中带版本号
- ADR 文件名 `NNNN-short-title.md`，内容遵循 Decision / Context / Consequences

## 与 HotPulse 主项目交互

- 在 llm-project 中能完成的事不要去改 HotPulse
- 真要改 HotPulse 时先在 `fullstack-product/docs/tasks/` 起任务
- 共用配置（如 ES 连接、模型 API key）以环境变量为准，不硬编码
