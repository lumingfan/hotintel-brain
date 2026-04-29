# llm-project 工作流

这里只写规则，不写当前任务。

## 文档触发条件

- **新增 ADR**：当一个决策影响"语言/框架/对外契约/评测口径/与主项目对接方式"任何一条
- **更新 spec**：当 specs 中的事实或边界发生变化（不只是文字润色）
- **更新 STATUS**：每完成一个有产物的子步骤后；阻塞 / 风险变化时立即更新
- **新建任务文档**：当一个目标超过两个工作日且涉及多文件 / 多 commit 时

## prompt 与 chain 改动

- 每次 prompt 改动都要打版本（如 `judge-v1.0` / `summarize-v1.1`）
- prompt 文件命名沿用仓内约定（如 `prompts/judge_v1.md`），版本号写在 frontmatter `version:` 字段
- 同一个 task 的 prompt 历史版本不删除，方便 eval 报告里 diff
- chain 结构变化要更新 `architecture.md` 的对应小节

## eval 实验

- 每次 eval 跑分都落 `eval/reports/<date>-<title>.md`
- 报告固定字段：数据集版本、模型、prompt 版本、指标、错例摘要、下一步
- commit message 用 `eval:` 前缀，body 中带 prompt 版本号
- 若是低成本 sanity / silver-label 报告，标题里明确标注 `sanity` 或 `silver`

## 与主项目交互

- llm-project 自己范围内的事不动 HotPulse 代码
- 真要改 HotPulse 时，先在 `fullstack-product/docs/tasks/T-XXX-...md` 起任务，再实现
- 接口契约变更必须双写：本仓 `docs/api/contract.md` + 主仓 `fullstack-product/docs/api/`

## Git / 提交

- 默认分支 `main`
- conventional commits：`feat: / fix: / docs: / chore: / eval: / refactor:`
- commit message 标题中文 / 英文均可，但全仓保持一致
- 涉及 prompt / eval 的 commit 标题用英文 + 版本号方便 diff

## 大下载操作

- 首次拉取大体积 Docker 镜像、模型文件、系统依赖包等步骤时，默认由用户手动执行下载
- assistant 先给出可直接复制的命令；用户确认下载完成后，再继续后续部署 / 验证 / 联调
- 只有用户明确要求代为执行时，assistant 才自行承担长时间下载

## 不要做

- 不在仓内提交模型 API key、标注数据、eval 输出（用 `.gitignore`）
- 不直接在 main 分支修复 prompt 后立刻 push 而不留 eval 报告
- 不为了"能跑通"绕过 schema 校验（绕过等于把降级藏在了背后）
