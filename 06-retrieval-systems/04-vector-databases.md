# 向量資料庫

向量資料庫是專門為儲存、索引及搜尋高維度嵌入向量而建的系統。市場已分為**託管無伺服器**與**專業高效能**兩種引擎。我們不再問「它支援向量搜尋嗎？」（Postgres、Redis、Mongo 都支援）。我們問的是**「它能否擴展到 1 億以上向量，並達到 P99 延遲低於 100 毫秒且支援完整中繼資料篩選？」**

## 目錄

- [什麼是向量資料庫](#什麼是向量資料庫)
- [向量搜尋基礎](#向量搜尋基礎)
- [索引演算法](#索引演算法)
- [競爭態勢](#競爭態勢)
- [詳細資料庫比較](#詳細資料庫比較)
- [中繼資料篩選](#中繼資料篩選)
- [查詢模式](#查詢模式)
- [生產環境作業](#生產環境作業)
- [託管與自架（總體擁有成本分析）](#託管與自架總體擁有成本分析)
- [選型框架](#選型框架)
- [面試問題](#面試問題)
- [參考資料](#參考資料)

---

## 什麼是向量資料庫

向量資料庫儲存嵌入向量（密集向量），並能對其進行快速相似性搜尋。

```
傳統資料庫：      SELECT * FROM docs WHERE category = 'tech'
向量資料庫：       SELECT * FROM docs ORDER BY similarity(embedding, query_embedding) LIMIT 10
```

### 核心能力

| 能力 | 用途 |
|------------|---------|
| 向量儲存 | 持久化高維度嵌入向量 |
| 相似性搜尋 | 快速找到最近鄰 |
| 中繼資料篩選 | 結合向量搜尋與屬性篩選 |
| CRUD 操作 | 隨資料變化更新嵌入向量 |
| 擴展性 | 處理數百萬到數十億個向量 |

### 為什麼不用通用資料庫？

傳統資料庫可以儲存向量，但缺乏最佳化的搜尋能力：

| 方式 | 搜尋複雜度 | 大規模實際可用 |
|----------|-------------------|-------------------|
| 暴力搜尋（PostgreSQL pgvector） | O(n * d) | 約可達 1M 向量 |
| ANN 索引（專門向量資料庫） | O(log n) 或 O(1) | 可達數十億 |

---

## 向量搜尋基礎

### 精確搜尋與近似搜尋

**精確（暴力搜尋）：**
- 將查詢與每個儲存的向量比較
- 每次查詢 O(n * d)
- 完全準確

**近似最近鄰（ANN）：**
- 使用索引結構來剪枝搜尋空間
- 次線性複雜度
- 召回率略低（通常 95-99%）

### 距離度量

| 度量 | 公式 | 範圍 | 適用場景 |
|--------|---------|-------|----------|
| Cosine | 1 - (a . b) / (norm(a) * norm(b)) | [0, 2] | 文字嵌入向量 |
| Euclidean (L2) | sqrt(sum((a - b)^2)) | [0, inf) | 圖片嵌入向量 |
| Dot product | a . b | (-inf, inf) | 已正規化時 |

**文字嵌入向量：**使用 cosine 相似度（或若已預先正規化則用 dot product）。

### 召回率與延遲的取捨

```
                    ^ 召回率
                    |
               100% | ------------------ 暴力搜尋
                    |         *          調校良好的 ANN
                    |      *
                    |   *
                95% |*                   快速 ANN
                    |
                    +-----+-------+------> 延遲
                       1ms      10ms
```

ANN 索引以部分準確度換取速度。請根據您的需求進行調校。

---

## 索引演算法

### HNSW（分層可導航小世界圖）

生產環境中記憶體內向量搜尋最流行的演算法。

**運作原理：**
1. 建立圖，節點為向量
2. 連接到附近鄰居
3. 多層抽象（分層）
4. 搜尋：從頂層往下導航，貪心最近鄰

```
第二層：   *--------*--------*
           |        |        |
第一層：   *--*--*--*--*--*--*
           |  |  |  |  |  |  |
第零層：   ********************  （所有向量）
```

**優點：**
- 優異的召回率/延遲取捨
- 無需訓練
- 原生支援更新

**缺點：**
- 記憶體密集（圖結構）
- 索引大小：約為向量資料的 1.5-2 倍
- 1 千萬向量、1536 維度需要約 80GB RAM

**關鍵參數：**
- `M`：每節點最大連接數（16-64）
- `ef_construction`：建構時探索範圍（100-500）
- `ef_search`：查詢時探索範圍（50-200）

### DiskANN（SSD 為基礎）

**PB 規模**搜尋的業界標準。

**運作原理：**
- 將圖保留在 SSD（NVMe）上，僅在 RAM 中保留小型索引
- 使用 Vamana 演算法進行高效的磁碟圖遍歷

**優點：**
- 十億規模資料集比 HNSW 便宜 10 倍，延遲增加少於 5ms
- RAM 需求比 HNSW 減少 90-95%

**缺點：**
- 延遲略高於純記憶體 HNSW
- 最適合非即時搜尋應用

**範例：**1 億向量、1536 維度的索引，使用 HNSW 需要近 1TB RAM。使用 DiskANN，RAM 需求減少 90-95%，同時維持次 10ms 查詢時間。

### IVF（倒排檔索引）

將向量分區到叢集，只搜尋相關叢集。

**運作原理：**
1. 使用 k-means 建立質心
2. 將每個向量指派到最近質心
3. 查詢時：找到最近質心，搜尋那些叢集

**優點：**
- 比 HNSW 記憶體需求低
- 可使用量化（IVF-PQ）

**缺點：**
- 需要訓練
- 更新需要重新叢集化或混合方式

**關鍵參數：**
- `nlist`：叢集數量（經驗法則用 sqrt(n)）
- `nprobe`：查詢時要搜尋的叢集數量

### 產品量化（PQ）

壓縮向量以減少記憶體並加速比較。

**運作原理：**
1. 將向量分割為子向量
2. 對每個子向量量化到碼本
3. 儲存編碼而非完整向量

**記憶體減少：**通常 4-32 倍

**取捨：**因量化損失而準確度降低

### 平面索引（暴力搜尋）

無近似，精確搜尋。

**使用時機：**
- 向量少於 10 萬個
- 準確度至關重要
- 延遲預算充足

### 演算法比較

| 演算法 | 記憶體 | 建構時間 | 查詢速度 | 召回率 | 更新 |
|-----------|--------|------------|-------------|--------|---------|
| HNSW | 高 | 中等 | 非常快 | 95-99% | 良好 |
| DiskANN | 低（SSD） | 中等 | 快 | 95-99% | 尚可 |
| IVF | 中 | 快 | 快 | 90-98% | 尚可 |
| IVF-PQ | 低 | 快 | 快 | 85-95% | 尚可 |
| Flat | 低 | 無 | 慢 | 100% | 即時 |

---

## 競爭態勢

### 向量原生（專門）

| 資料庫 | 類型 | 適用場景 | 定價模式 |
|----------|------|----------|---------------|
| **Pinecone** | 託管雲端（無伺服器標準） | 輕鬆入門、擴展、託管 SLA | 按向量小時計費 |
| **Qdrant** | 開源 / 雲端（Rust，高效能） | 自架控制，在常見工作負載上最快的開源（1 千萬向量約 12ms p99） | 按 GB 計費（雲端）或免費 |
| **Weaviate** | 開源 / 雲端 | 原生混合（BM25 + 密集 + 中繼資料）單一查詢，多模態 | 按維度小時計費 |
| **Milvus** | 開源 / 雲端（Zilliz） | 分散式擴展（5 千萬+ 向量），異質節點類型，分層儲存 | 免費（自架）或 Zilliz Cloud |
| **Chroma** | 開源 | 原型設計、本地開發、嵌入式使用 | 免費 |

### 通用型（插件/擴展）

| 資料庫 | 類型 | 適用場景 | 定價模式 |
|----------|------|----------|---------------|
| **pgvector（v0.8+）** | PostgreSQL 擴展 | 小規模，現有 PG（現支援 HNSW + IVFFlat） | 僅計算費用 |
| **Elasticsearch（v9.0）** | 搜尋引擎 | 使用交叉熵融合的混合搜尋 | 授權基礎 |

---

## 詳細資料庫比較

### 功能矩陣

| 功能 | Pinecone | Qdrant | Weaviate | Milvus | pgvector |
|---------|----------|--------|----------|--------|----------|
| **語言** | 專有 | Rust | Go | Go/C++ | C |
| 託管選項 | 有 | 有 | 有 | 有（Zilliz） | 透過雲端 PG |
| 自架 | 否 | 是 | 是 | 是 | 是 |
| **無伺服器** | 是（最佳） | 是 | 是 | 是（Zilliz） | 否 |
| **雲端原生** | 任意 | 任意 | 任意 | 僅 K8s | 任意 |
| 中繼資料篩選 | 良好 | 優秀 | 良好 | 良好 | 透過 SQL |
| **混合搜尋** | 原生 | 原生 | 原生 | 原生 | 多階段（有限） |
| 最大向量數 | 數十億 | 數十億 | 數十億 | 數十億 | 約 1 千萬 |
| HNSW 索引 | 是 | 是 | 是 | 是 | 是 |

---

## 中繼資料篩選

對多租戶和篩選使用場景至關重要。

```python
# Pinecone
results = index.query(
    vector=query_embedding,
    top_k=10,
    filter={"tenant_id": "123", "category": {"$in": ["tech", "science"]}}
)

# Qdrant
results = client.search(
    collection_name="documents",
    query_vector=query_embedding,
    limit=10,
    query_filter=Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value="123")),
            FieldCondition(key="category", match=MatchAny(any=["tech", "science"]))
        ]
    )
)
```

**效能影響：**篩選在搜尋期間進行，而非之後。預先篩選的索引較快但彈性較低。

**為什麼中繼資料篩選通常是瓶頸：**在樸素的向量搜尋中，我們先找到「Top K」最近鄰，**然後**再依中繼資料篩選。如果篩選條件非常嚴格，篩選後可能找到 0 結果。專業資料庫現在使用**帶 HNSW 的預先篩選**，遍歷圖但只考慮滿足布林中繼資料約束的節點。這需要專門的位元遮罩或硬體加速（SIMD）來保持低延遲。

**磁碟原生中繼資料：**像 **Qdrant** 這類現代資料庫將中繼資料卸載到磁碟映射區段，允許複雜篩選（例如全文 + 地理 + 向量）而不會耗盡 RAM。

---

## 查詢模式

### 模式 1：簡單語義搜尋

```python
def semantic_search(query: str, top_k: int = 5) -> list[Document]:
    query_embedding = embed(query)
    results = vector_db.search(query_embedding, top_k=top_k)
    return [Document(id=r.id, text=r.payload["text"], score=r.score) for r in results]
```

### 模式 2：篩選搜尋

```python
def filtered_search(query: str, filters: dict, top_k: int = 5) -> list[Document]:
    query_embedding = embed(query)
    results = vector_db.search(
        query_embedding,
        top_k=top_k,
        filter=filters  # {"tenant_id": "abc", "created_after": "2025-01-01"}
    )
    return results
```

### 模式 3：混合搜尋（密集 + 稀疏）

```python
def hybrid_search(query: str, alpha: float = 0.5, top_k: int = 5) -> list[Document]:
    # 密集（語義）
    dense_embedding = embed(query)
    dense_results = vector_db.search(dense_embedding, top_k=top_k * 2)

    # 稀疏（關鍵字）
    sparse_results = bm25_search(query, top_k=top_k * 2)

    # 使用倒序排名融合合併
    combined = reciprocal_rank_fusion(
        [dense_results, sparse_results],
        weights=[alpha, 1 - alpha]
    )

    return combined[:top_k]
```

某些資料庫（Weaviate、Qdrant、Pinecone）原生支援混合搜尋：

```python
# Weaviate 原生混合
results = client.query.get("Document", ["text"]).with_hybrid(
    query=query,
    alpha=0.5  # 0 = 僅 BM25，1 = 僅向量
).with_limit(5).do()
```

### 模式 4：多向量查詢

用於父子或多面向檢索：

```python
def multi_vector_search(queries: list[str], top_k: int = 5) -> list[Document]:
    all_results = []

    for query in queries:
        embedding = embed(query)
        results = vector_db.search(embedding, top_k=top_k)
        all_results.extend(results)

    # 去重並重新排名
    unique = dedupe_by_id(all_results)
    reranked = rerank(queries[0], unique)  # 使用主要查詢重新排名

    return reranked[:top_k]
```

---

## 生產環境作業

### 容量規劃

```python
def estimate_resources(
    num_vectors: int,
    dimensions: int,
    metadata_size_bytes: int = 500
) -> dict:
    # 向量儲存
    vector_size = dimensions * 4  # float32
    total_vector_storage = num_vectors * vector_size

    # 索引開銷（HNSW 約 1.5 倍）
    index_overhead = total_vector_storage * 1.5

    # 中繼資料
    metadata_storage = num_vectors * metadata_size_bytes

    # 總計
    total_gb = (total_vector_storage + index_overhead + metadata_storage) / 1e9

    # QPS 估算（粗略）
    qps_per_gb = 50  # 高度依賴配置
    estimated_qps = total_gb * qps_per_gb

    return {
        "storage_gb": total_gb,
        "estimated_qps": estimated_qps,
        "recommended_replicas": max(1, int(total_gb / 50))  # 每副本約 50GB
    }
```

### 索引維護

```python
class VectorDBMaintenance:
    def __init__(self, client):
        self.client = client

    def add_documents(self, documents: list[Document]):
        """批量 upsert 文件。"""
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            embeddings = embed_batch([d.text for d in batch])

            self.client.upsert([
                {
                    "id": doc.id,
                    "vector": embedding,
                    "payload": doc.metadata
                }
                for doc, embedding in zip(batch, embeddings)
            ])

    def delete_documents(self, doc_ids: list[str]):
        """按文件 ID 刪除。"""
        self.client.delete(ids=doc_ids)

    def update_metadata(self, doc_id: str, metadata: dict):
        """更新中繼資料而無需重新嵌入。"""
        self.client.set_payload(
            collection_name="documents",
            payload=metadata,
            points=[doc_id]
        )
```

### 高可用性

```
+-------------------------------------------------------------+
|                    負載平衡器                                  |
+----------------------------+--------------------------------+
                             |
            +----------------+----------------+
            v                v                v
     +--------------+ +--------------+ +--------------+
     |  副本 1      | |  副本 2      | |  副本 3      |
     |   （讀取）    | |   （讀取）    | |   （主節點）  |
     +--------------+ +--------------+ +--------------+
                                             |
                                       （複寫）
                                             |
                                       +-----v-----+
                                       |  儲存      |
                                       +-----------+
```

**關鍵模式：**
- 主從式用於寫入
- 讀取副本用於查詢擴展
- 非同步複寫用於高可用性

### 監控

```python
VECTOR_DB_METRICS = [
    "query_latency_p50",
    "query_latency_p99",
    "queries_per_second",
    "index_size_gb",
    "vector_count",
    "filter_latency",
    "upsert_latency",
    "cache_hit_rate"
]

def alert_rules():
    return {
        "query_latency_p99_high": {
            "condition": "query_latency_p99 > 500ms",
            "severity": "warning"
        },
        "query_latency_p99_critical": {
            "condition": "query_latency_p99 > 2000ms",
            "severity": "critical"
        },
        "low_recall": {
            "condition": "bench_recall < 0.90",
            "severity": "warning"
        }
    }
```

---

## 託管與自架（總體擁有成本分析）

### 成本比較

| 面向 | Pinecone（無伺服器） | 自架（Qdrant/Milvus） |
|--------|-----------------------|-----------------------------|
| **營運負擔** | 零 | 高（需要 K8s + SRE） |
| **擴展性** | 即時（可縮至零） | 手動（節點佈建） |
| **成本（小規模）** | $0 - $100/月 | $50/月（最低規格執行個體） |
| **成本（規模化）** | 每 token/向量較高 | 單位成本低 |

### 託管服務定價（僅供參考，請始終至提供商頁面驗證）

| 提供商 | 模式 | 範例：1 千萬向量，1536 維度 |
|----------|-------|--------------------------------|
| Pinecone | Pod 基礎或無伺服器 | 無伺服器約 $70-150/月 |
| Qdrant Cloud | 按 GB | 約 $50/月（20GB） |
| Weaviate Cloud | 按維度 | 約 $100/月 |
| Zilliz（Milvus） | 按 CU | 約 $75/月 |

### 自架成本

```python
def estimate_self_hosted_cost(
    vectors: int,
    dimensions: int,
    cloud: str = "aws"
) -> dict:
    storage_gb = (vectors * dimensions * 4 * 2.5) / 1e9  # 索引 2.5 倍

    # 執行個體大小
    if storage_gb < 50:
        instance = "r6g.large"  # 16 GB RAM，約 $60/月
    elif storage_gb < 200:
        instance = "r6g.xlarge"  # 32 GB RAM，約 $120/月
    else:
        instance = "r6g.2xlarge"  # 64 GB RAM，約 $240/月

    return {
        "storage_gb": storage_gb,
        "instance": instance,
        "monthly_compute": instance_pricing[instance],
        "monthly_storage": storage_gb * 0.10,  # EBS
        "total_monthly": instance_pricing[instance] + storage_gb * 0.10
    }
```

### 決策：託管 vs 自架

| 因素 | 託管 | 自架 |
|--------|---------|-------------|
| 營運負擔 | 低 | 高 |
| 小規模成本 | 較高 | 較低 |
| 大規模成本 | 不穩定 | 通常較低 |
| 控制權 | 較少 | 完整 |
| 合規性 | 取決於供應商 | 完全控制 |
| 供應商鎖定 | 是 | 否（若開源） |

**結論**：從無伺服器開始。只有在擁有超過 5 億向量或有嚴格的**就地/GPU 本地**需求時才自架。

---

## 選型框架

### 決策樹

```
需要 < 10 萬向量？
+-- 是 -> pgvector（若已在用 PostgreSQL）
|          +-- Chroma（原型設計）
|
+-- 否 -> 需要託管服務？
          +-- 是 -> 雲端優先？
          |          +-- 是 -> Pinecone（最簡單）
          |          +-- 否 -> Qdrant Cloud 或 Zilliz
          |
          +-- 否 -> 需要企業功能？
                    +-- 是 -> Kubernetes 上的 Milvus
                    +-- 否 -> Qdrant 或 Weaviate 自架
```

### 評估標準

| 標準 | 權重 | 需提出的問題 |
|-----------|--------|------------------|
| 規模 | 高 | 現在有多少向量？一年後呢？ |
| 延遲 | 高 | P99 要求是多少？ |
| 營運能力 | 高 | 我們能營運這個嗎？ |
| 成本 | 中 | 預算限制？ |
| 功能 | 中 | 混合搜尋？多模態？ |
| 鎖定風險 | 中低 | 偏好開源？ |

### 概念驗證清單

在決定向量資料庫之前：

- [ ] 載入具代表性的資料量
- [ ] 在目標 QPS 下測試查詢延遲
- [ ] 測試中繼資料篩選效能
- [ ] 驗證更新/刪除效能
- [ ] 測試故障復原
- [ ] 評估監控與可觀測性
- [ ] 計算總體擁有成本

---

## 面試問題

### Q：你如何選擇 Pinecone 和自架方案？

**強而有力的答案：**
決策取決於幾個因素：

**選擇 Pinecone 的時機：**
- 團隊缺乏營運有狀態基礎設施的能力
- 需要快速前進（天而非週）
- 規模適中（低於 1 億向量）
- 預算允許託管服務溢價
- 合規性允許雲端廠商依賴

**選擇自架（Qdrant、Milvus）的時機：**
- 擁有 Kubernetes 和營運專業知識
- 規模化成本敏感
- 需要完全控制資料
- 有特定合規要求
- 想避免供應商鎖定

對於大多數新創公司，我會從 Pinecone 或 Qdrant Cloud 開始以保持速度，然後如果在規模上成本變得過高再評估遷移。由於向量資料庫有相似的 API，切換成本適中。

### Q：解釋 HNSW 的運作原理以及何時不應該使用它。

**強而有力的答案：**
HNSW 建立向量的分層圖：

**運作原理：**
1. 將向量作為多層圖中的節點插入
2. 較高層有較少節點，較大跳躍
3. 搜尋：從頂層開始，貪心地導航到最近鄰
4. 逐層下降直到底層（所有向量）

**優點：**
- O(log n) 查詢複雜度
- 無需訓練
- 支援即時更新
- 優異的召回率/延遲取捨

**何時不使用：**
- 非常小的資料集（<1 萬）：暴力搜尋就足夠
- 記憶體極度受限：HNSW 使用向量大小 1.5-2 倍的記憶體來存圖
- 需要精確搜尋：HNSW 是近似的
- 高更新工作負載且延遲嚴格：更新可能導致暫時效能下降

替代方案：
- 記憶體受限時用 IVF-PQ
- 十億規模且需成本效益時用 DiskANN
- 精確搜尋用平面索引
- 極高維度稀疏向量用 LSH

### Q：何時會選擇磁碟索引（如 DiskANN）而非記憶體索引（HNSW）？

**強而有力的答案：**
當索引的記憶體成本超過預算或單一高記憶體節點的容量時，我會使用磁碟索引。例如，1 億向量、1536 維度的索引使用 HNSW 需要近 1TB RAM。使用 DiskANN，我可以將那 1TB 的大部分儲存在 NVMe SSD 上，將 RAM 需求減少 90-95%，同時維持次 10ms 查詢時間。這對於非即時搜尋應用來說代表著巨大的總體擁有成本（TCO）降低。

### Q：為什麼中繼資料篩選通常是向量資料庫的瓶頸？

**強而有力的答案：**
在樸素的向量搜尋中，我們找到「Top K」最近鄰，**然後**再依中繼資料篩選（例如「僅 2024 年的文件」）。如果篩選條件非常嚴格，篩選後可能找到 0 結果。專業資料庫現在使用**帶 HNSW 的預先篩選**，遍歷圖但只考慮滿足布林中繼資料約束的節點。這在計算上很昂貴，因為它打破了 HNSW 的「短路」邏輯，需要專門的位元遮罩或硬體加速（SIMD）來保持低延遲。

### Q：如何在向量資料庫中處理多租戶？

**強而有力的答案：**
三種主要方式：

**1. 中繼資料篩選（最常見）：**
```python
results = db.search(
    vector=query,
    filter={"tenant_id": current_tenant}
)
```
- 優點：簡單，單一索引
- 缺點：所有租戶共享資源，可能有漏洞暴露資料

**2. 每租戶一個集合：**
```python
results = db.collection(f"tenant_{tenant_id}").search(vector=query)
```
- 優點：強隔離，每租戶可擴展
- 缺點：許多集合，營運開銷大

**3. 每租戶命名空間（Pinecone）：**
```python
results = index.query(vector=query, namespace=tenant_id)
```
- 優點：單一索引內隔離
- 缺點：供應商特定

**我會選擇：**
- 大多數情況用中繼資料篩選（簡單、具成本效益）
- 高安全性要求用獨立集合
- 絕不事後篩選（檢索所有，之後篩選）因為有資料洩漏風險

---

## 參考資料

- Malkov and Yashunin. "Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs" (HNSW, 2018)
- Microsoft Research. "Vamana/DiskANN: A Disk-based Index for ANN Search" (2019/2023)
- Pinecone Documentation: https://docs.pinecone.io/
- Pinecone. "The Managed Architecture of Serverless Vector DBs" (2024)
- Qdrant Documentation: https://qdrant.tech/documentation/
- Weaviate Documentation: https://weaviate.io/developers/weaviate
- Milvus Documentation: https://milvus.io/docs
- pgvector: https://github.com/pgvector/pgvector

---

*上一篇：[嵌入模型](03-embedding-models.md) | 下一篇：[混合搜尋](05-hybrid-search.md)*
