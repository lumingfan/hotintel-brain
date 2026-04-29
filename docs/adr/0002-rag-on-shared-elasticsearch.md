# ADR 0002 — RAG 检索：V2 起步共用 ES，V3 引入 Milvus 做 ablation

状态：Accepted
最近更新：2026-04-27（加 V3 Milvus ablation 计划）

## Context

V2 引入 RAG 时需要选向量库。候选：

1. **共用 HotPulse 的 Elasticsearch，加 `dense_vector` 字段**（本 ADR 选项）
2. 引入 Milvus / Qdrant / Pinecone 之一作为独立向量库
3. 使用 FAISS 本地索引文件

## Decision

**V2 起步**：复用 HotPulse 已有的 `hotspot_search` ES 索引，给 mapping 加 `dense_vector` 字段（768 维），由 HotPulse 写链路在已研判热点入库时同步生成 embedding。

**V3 实验**：引入 Milvus 作为对比候选库，针对同一份评测集与同一 embedding 模型跑 ablation study，对比 ES dense vs Milvus dense 的：

- 召回率（Recall@10）
- Top-k 检索 P50 / P95 延迟
- 资源占用（内存 / CPU）
- 维护复杂度（reindex / 故障恢复）

V3 ablation 的产出物就直接决定 V3 之后是否真切到 Milvus —— **决策本身就是 evaluation-driven**。

具体（V2 起步）：

- Embedding 模型：`bge-large-zh-v1.5`（首选，按 ADR 0007 V2 启动时定）
- 字段：`hotspot_search.embedding`，dims=768，similarity=`cosine`
- 写入：HotPulse `intelligence` 模块在 hotspot 入库后调用 Brain 的 `/v1/embed`（V2 时新增）拿到 embedding，再写回 ES
- 检索：Brain 的 L2 链路用 BM25 + `script_score` (dense) hybrid query，rerank 后取 top-5

具体（V3 ablation 实验）：

- Brain 仓内 `infra/milvus/compose.yaml` 起 Milvus standalone（含 etcd + minio）
- 为 `hotspot_search` 同样的内容建一份 Milvus collection，用同一 embedding 模型批量回填
- 在 `chains/l2_rag.py` 加 `vector_backend = "es" | "milvus"` 切换开关
- 评测时按 `vector_backend` 维度跑双路对比，输出报告
- 实验结束后视结果决定：
  - 结果显著（Milvus 提升 ≥ 5%）→ 切到 Milvus，本 ADR 升级为 Superseded，开 ADR 0008
  - 结果接近 → 保留 ES，简历可讲"通过 ablation 排除了 Milvus 的必要性"
  - Milvus 占优但代价过高 → 保留 ES，简历可讲取舍

## Consequences

### 正面

- 不引入新基础设施，本地 compose 维持现状
- 主项目 ES 已有完善的索引治理（`search_reindex_job`、coverage 状态机），向量字段天然继承这套治理
- 共用一套 mapping 让 HotPulse `search` 模块和 Brain `retrieval` 模块对齐数据
- 简历讲述更紧凑：「副项目 RAG 复用主项目的 ES，避免引入新组件」是个清晰的工程取舍

### 负面

- ES 不是专门的向量库，大规模高维向量性能不如 Milvus / Qdrant
- HNSW / IVF 等高级索引调优没有专用向量库灵活
- 简历词频弱：「Milvus」是大模型岗位语境的高频词，仅有「ES + dense_vector」相对低调
- V2 评测如果 retrieval 召回不达标，可能要回头评估迁移

### 缓解

- 当前数据规模（个人项目 10k 量级文档）在 ES 上完全可承受
- 评测协议里有"检索召回率"作为辅指标，及早发现 retrieval 短板
- **V3 阶段引入 Milvus ablation 实验**：用 evaluation-driven 方式回答"是否需要 Milvus"，简历讲述时既有 ES 起步的工程理由，也有 Milvus 对比的实验产出
- 若 V3 ablation 显示 Milvus 显著占优，再开 ADR 0008 评估正式迁移方案

## 不选其他方案的理由

### 不选 Milvus / Qdrant / Pinecone

- 引入额外服务 → 本地 compose 复杂度上升
- 对副项目"和主项目耦合度"是负向信号（看起来副项目和主项目"各搞一套基础设施"）
- 简历讲述时多一个组件需要解释

### 不选 FAISS 本地索引

- FAISS 适合静态数据集，不适合 HotPulse 持续写入的动态数据
- 与 HotPulse 已有 ES 治理不耦合
- 服务化需要自己包装一层，反而比直接用 ES 更复杂

## 验证条件（V2 启动时检查）

- HotPulse `hotspot_search` 索引能成功加 `dense_vector` 字段
- 单条 hotspot 写入 + embedding 生成 + ES 索引同步在本地链路上 < 1.5s
- L2 在 v1 评测集上至少一项主指标提升 ≥ 0.05
- 本地 ES 在 10k 文档规模下，dense top-k=5 检索 P95 < 200ms

任何一条不达标，回到本 ADR 重新评估。

## 验证条件（V3 ablation 启动时）

- Milvus standalone 本地起来稳定运行 24 小时不 OOM
- 同一 embedding 模型 + 同一 evaluation 集合上能跑出 ES vs Milvus 的对比报告
- 报告含：Recall@10 / P50 / P95 / 内存占用 / 维护成本评估
- 若 Milvus 提升不到 5%，决策保留 ES（这本身就是一个有意义的实验结论）

## 关联文档

- `specs/three-layer-capability.md` L2 段
- `architecture.md` 第 4.2 节
- `eval/protocol.md` 第 2.1 / 2.6 节
- HotPulse `fullstack-product/docs/data-model/hot-intel-core-entities.md`（待 V2 时同步更新 mapping）
