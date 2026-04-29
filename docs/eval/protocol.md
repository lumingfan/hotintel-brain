# 评测协议

创建时间：2026-04-27
状态：Draft
适用版本：v1

评测是这个项目的核心信号，所有 prompt / chain / agent 改动都通过同一份评测协议给出可比结果。

## 1. 数据集

### 1.1 v1 数据集

- 大小：200 条
- 来源：HotPulse `raw_document` 表抽样，按来源 stratified（HN / Bilibili / Bing / Sogou / Weibo / Twitter 各 30-35 条）
- 时间窗口：抽样时取最近 30 天
- 文件：`data/labeled-v1.jsonl`（不进 git，本地维护）

### 1.2 标注字段（与 `JudgementResult` 对齐）

每条样本的标注字段：

```json
{
  "rawDocumentId": "rd_001",
  "topicContext": {...},
  "labels": {
    "isReal": true,
    "importance": "high",
    "summary": "标准摘要，≤ 100 字",
    "summaryKeyPoints": ["发布时间", "影响范围", "对比基线"],
    "keywordMentioned": true,
    "relevanceBucket": "high"
  },
  "labelerNotes": "可选，难判断点的备注"
}
```

注意：

- `relevanceScore` 是连续值，标注里只标 `relevanceBucket`（low/medium/high/urgent），评测时再映射回区间
- `summary` 标注是"参考摘要"，不是模型必须复现的字符串；评测用 ROUGE-L 或 LLM-judge

详细标注口径见 `data/labeling-guide.md`。

## 2. 指标

### 2.1 importance 准确率

- 主指标：**macro-F1**（4 类不平衡，避免被 medium 主导）
- 辅指标：confusion matrix
- 退出阈值（V1）：macro-F1 ≥ 0.65

### 2.2 isReal 检测

- 主指标：**precision** / **recall**
- 退出阈值（V1）：precision ≥ 0.7，recall ≥ 0.6
- 解读：宁可漏判（recall 略低），也不能误把假新闻判为 real（precision 优先）

### 2.3 summary 质量

V1 用两套指标并行，互为 sanity check：

- **ROUGE-L F1**：参考摘要 vs 模型摘要
- **LLM-judge**：用第三方模型按"信息密度 / 事实一致 / 长度合理"三维打 1-5 分
- 退出阈值（V1）：ROUGE-L F1 ≥ 0.25 或 LLM-judge 平均 ≥ 3.5（任一即可）

### 2.4 relevanceScore

- 把模型连续值映射到 bucket：[0,40)=low / [40,60)=medium / [60,80)=high / [80,100]=urgent
- 与 `relevanceBucket` 标签做 macro-F1
- 不设硬阈值，作为辅参指标

### 2.5 keywordMentioned

- precision / recall 各列一次
- 不设硬阈值，作为辅参

### 2.6 工程指标（每次跑必须报告）

- `p50_latency_ms`
- `p95_latency_ms`
- `total_tokens_per_sample`
- `cost_usd_per_100_samples`（按当前模型定价折算）
- `partial_rate`（schema 校验失败比例）

## 3. 评测流程

### 3.1 一次完整跑分

```bash
python -m eval.run \
  --dataset data/labeled-v1.jsonl \
  --layer L1 \
  --model gpt-4o-mini \
  --prompt-version judge-v1.0 \
  --output eval/reports/2026-MM-DD-l1-baseline.md
```

### 3.2 输出报告固定结构

`eval/reports/<date>-<title>.md` 必含：

1. 元数据：日期 / 数据集版本 / 模型 / prompt 版本 / 层级
2. 指标表（importance / isReal / summary / 工程指标）
3. confusion matrix（importance）
4. 错例摘要（10 条，含模型输出 + 人工 label + 简短分析）
5. 与上一次的 diff（如果有 baseline）
6. 下一步建议

### 3.3 三层对比报告（V2 / V3 必备）

升 L2 / L3 后，必出三层对比报告：

```
| 指标 | L1 | L2 | L3 |
| --- | --- | --- | --- |
| importance macro-F1 | 0.66 | 0.72 | 0.74 |
| isReal precision | 0.71 | 0.75 | 0.78 |
| isReal recall | 0.62 | 0.68 | 0.71 |
| ROUGE-L | 0.27 | 0.31 | 0.32 |
| p95 latency (ms) | 1200 | 2400 | 6800 |
| tokens / sample | 800 | 1500 | 3200 |
| partial rate | 2% | 3% | 5% |
```

并附"L3 升级触发后翻转 / 未翻转"的样本分布。

## 4. 防过拟合

- v1 标注集**不**被反复用作迭代验证集；当出现"prompt 改了 5 版后 macro-F1 持续涨"时，准备 v2 标注集（再抽 100 条）做 holdout
- prompt 修订必须留版本号；同一报告内用同一 prompt
- 不允许把 eval 报告里的错例直接喂回 prompt（这是过拟合捷径）

## 5. 仓内目录约定

```
eval/
├── harness.py        ← 单一入口，跑 layer / model / dataset 组合
├── metrics.py        ← 各指标实现
├── reports/          ← 历史报告（进 git，方便 review）
└── datasets/         ← .gitignore，本地标注数据
```

## 6. 与 HotPulse 的关系

- HotPulse 不直接消费 eval 报告；但 V2 切换 L2 / V3 切换 L3 的决策依据来自这里
- HotPulse 的 demo 账号数据可以用作 sanity check，但不能算入 v1 / v2 标注集（避免数据泄漏）
