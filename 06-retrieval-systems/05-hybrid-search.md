# 混合檢索

混合檢索結合了密集（語意）檢索與稀疏（關鍵字）檢索，以獲得兩者的優勢。這是生產環境 RAG 的基準方案：Elasticsearch 的 `rrf` 檢索器、OpenSearch 混合搜尋、Weaviate、Qdrant 和 Azure AI Search 都提供原生混合管道。

## 目錄

- [為何需要混合檢索](#為何需要混合檢索)
- [密集檢索與稀疏檢索](#密集檢索與稀疏檢索)
- [混合檢索架構](#混合檢索架構)
- [融合方法](#融合方法)
- [學習式稀疏嵌入 (SPLADE)](#學習式稀疏嵌入-splade)
- [實作模式](#實作模式)
- [調校與優化](#調校與優化)
- [生產環境考量](#生產環境考量)
- [面試問題](#面試問題)
- [參考資料](#參考資料)

---

## 為何需要混合檢索

密集檢索和稀疏檢索都不是普遍更好的方案。兩者各有擅長的查詢類型。

### 查詢類型分析

| 查詢類型 | 範例 | 較佳的檢索方式 |
|------------|---------|------------------|
| 概念性 |「transformers 如何學習？」 | 密集 |
| 特定關鍵字 |「GPT-4 API 速率限制」 | 稀疏 |
| 命名實體 |「John Smith 對 BERT 的研究」 | 稀疏 |
| 縮寫/代碼 |「HTTP 429 是什麼意思？」 | 稀疏 |
| 改寫過的表述 |「如何讓 AI 更快」與「LLM 優化」 | 密集 |
| 混合型 |「GPT-4o API 的費用是多少？」 | 混合 |

**細微之處**：純密集檢索在技術文件中會失敗，因為特定的版本號和函數名稱承載了 90% 的資訊價值。

### 語意鴻溝問題

密集檢索可能會錯過精確匹配：

```
查詢：「Configure NVIDIA_VISIBLE_DEVICES」
文件：「Set the NVIDIA_VISIBLE_DEVICES environment variable...」

密集搜尋可能會錯過此結果，因為：
-「NVIDIA_VISIBLE_DEVICES」可能被錯誤地分詞
- 語意嵌入無法捕捉精確的字串匹配
- 訓練資料中可能沒有這個特定術語
```

稀疏檢索（BM25）因為精確的詞彙匹配，能立即找到這個結果。

---

## 密集檢索與稀疏檢索

### 密集（語意）檢索

使用神經嵌入來匹配語意。

```python
def dense_search(query: str, top_k: int = 10) -> list[Result]:
    query_embedding = embedding_model.encode(query)
    results = vector_db.search(query_embedding, top_k=top_k)
    return results
```

**優勢：**
- 理解改寫和同義詞
- 捕捉概念相似性
- 可跨語言運作（使用多語言模型）

**劣勢：**
- 可能錯過精確的關鍵字匹配
- 難以處理實體、代碼、縮寫
- 需要嵌入模型

### 稀疏（關鍵字）檢索

使用詞頻和統計方法（BM25、TF-IDF）。

```python
def sparse_search(query: str, top_k: int = 10) -> list[Result]:
    tokens = tokenize(query)
    results = bm25_index.search(tokens, top_k=top_k)
    return results
```

**優勢：**
- 精確匹配表現極佳
- 能處理罕見詞彙、代碼、實體
- 快速且可解釋
- 不需要訓練

**劣勢：**
- 錯過語意相似性
- 不理解同義詞
- 對詞彙表 mismatch 敏感

### 正面比較

| 面向 | 密集 | 稀疏 | 混合 |
|--------|-------|--------|--------|
| 語意匹配 | 最佳 | 差 | 最佳 |
| 精確匹配 | 差 | 最佳 | 最佳 |
| 罕見詞彙 | 差 | 最佳 | 非常好 |
| 零樣本領域 | 非常好 | 最佳 | 最佳 |
| 延遲 | 中等 | 快速 | 中等 |
| 實作難度 | 中等 | 簡單 | 複雜 |

---

## 混合檢索架構

### 架構 1：並行檢索與融合

```
                    +------------------+
                    |      查詢         |
                    +--------+---------+
                             |
              +--------------+--------------+
              v                             v
    +-------------------+         +-------------------+
    |   密集檢索        |         |   稀疏檢索        |
    |   (向量資料庫)     |         |   (BM25/ES)       |
    +---------+---------+         +---------+---------+
              |                             |
              +--------------+--------------+
                             v
                    +-------------------+
                    |      融合          |
                    |   (RRF, 加權)      |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |    最終結果        |
                    +-------------------+
```

**優點：** 清楚分離，可各自使用同類最佳方案（例如 Pinecone + Algolia），可獨立調校
**缺點：** 需要維護兩套系統，延遲較高（必須等待較慢的引擎）

### 架構 2：原生混合（單一系統）

有些向量資料庫原生支援混合搜尋：

```python
# Weaviate
results = client.query.get("Document", ["text"]).with_hybrid(
    query="Configure NVIDIA_VISIBLE_DEVICES",
    alpha=0.5  # 0 = 只用稀疏, 1 = 只用密集
).do()

# Qdrant（使用稀疏向量）
results = client.search(
    collection_name="docs",
    query_vector=NamedVector(name="dense", vector=dense_embedding),
    query_sparse_vector=NamedSparseVector(name="sparse", vector=sparse_vector),
)
```

**優點：** 單一系統，作業更簡單，延遲較低
**缺點：** 融合客製化有限，在擴展關鍵字與向量基礎設施方面的彈性較低

### 架構 3：分階段檢索

```
查詢 --> 稀疏（快速廣泛）--> 前 1000 筆
                    |
                    v
          密集重新排序 --> 前 100 筆
                    |
                    v
           交叉編碼器 --> 前 10 筆
```

**優點：** 有效率，每個階段都會精煉
**缺點：** 較複雜，早期階段的錯誤風險

---

## 融合方法

### 相互排名融合 (RRF)

RRF 是結合兩個不同搜尋引擎結果的黃金標準。它不看*分數*（因為各引擎的分數無法比較），而是看**排名**。

```python
def reciprocal_rank_fusion(
    rankings: list[list[str]],  # 文件 ID 清單的清單
    k: int = 60
) -> list[tuple[str, float]]:
    scores = defaultdict(float)

    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] += 1 / (k + rank + 1)

    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_docs
```

**特性：**
- 基於位置，忽略原始分數
- 對分數規模差異具有穩健性 — 防止單一引擎因為數字分數較高就「主導」結果
- k 參數控制排名敏感度（k 越高 = 對位置越不敏感）
- 簡單實作，除了 k 之外不需要調校

**典型 k 值：** 60（原始論文）、實務上為 10-100

### 加權分數融合

結合正規化後的分數：

```python
def weighted_fusion(
    dense_results: list[Result],
    sparse_results: list[Result],
    alpha: float = 0.5  # 密集的權重
) -> list[Result]:
    # 將分數正規化到 [0, 1]
    dense_normalized = normalize_scores(dense_results)
    sparse_normalized = normalize_scores(sparse_results)

    # 結合
    combined = {}
    for r in dense_normalized:
        combined[r.id] = alpha * r.score
    for r in sparse_normalized:
        combined[r.id] = combined.get(r.id, 0) + (1 - alpha) * r.score

    sorted_docs = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    return sorted_docs

def normalize_scores(results: list[Result]) -> list[Result]:
    if not results:
        return []
    min_score = min(r.score for r in results)
    max_score = max(r.score for r in results)
    range_score = max_score - min_score + 1e-6

    return [
        Result(id=r.id, score=(r.score - min_score) / range_score)
        for r in results
    ]
```

**特性：**
- 使用實際分數（比排名更多的資訊）
- 需要分數正規化
- Alpha 控制密集與稀疏的平衡

### 相對分數融合

考慮分數分布：

```python
def relative_score_fusion(
    dense_results: list[Result],
    sparse_results: list[Result]
) -> list[Result]:
    # 使用 z-score 正規化
    dense_normalized = z_score_normalize(dense_results)
    sparse_normalized = z_score_normalize(sparse_results)

    # 結合
    combined = {}
    for r in dense_normalized:
        combined[r.id] = r.score
    for r in sparse_normalized:
        combined[r.id] = combined.get(r.id, 0) + r.score

    return sorted(combined.items(), key=lambda x: x[1], reverse=True)

def z_score_normalize(results: list[Result]) -> list[Result]:
    scores = [r.score for r in results]
    mean = sum(scores) / len(scores)
    std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5 + 1e-6

    return [Result(id=r.id, score=(r.score - mean) / std) for r in results]
```

### 融合方法比較

| 方法 | 使用分數 | 查詢自適應 | 複雜度 |
|--------|-------------|----------------|------------|
| RRF | 否（僅排名） | 否 | 低 |
| 加權 | 是 | 否 | 低 |
| 相對分數 | 是 | 部分 | 中 |
| 學習式 | 是 | 是 | 高 |

---

## 學習式稀疏嵌入 (SPLADE)

生產環境堆疊已從 BM25（簡單詞頻）演進到**學習式稀疏嵌入**，作為混合檢索中稀疏檢索的部分。

**技術：** 像 **SPLADE v3** 這樣的模型會預測字典中每個詞彙的「重要性權重」。

**為什麼？**：SPLADE 可以「擴展」查詢。如果你搜尋「CPU」，它可能會自動對「processor」這個詞彙添加小的權重，即使「processor」不在你的查詢中。它將稀疏檢索的精確匹配能力與密集檢索的概念能力結合在單一儲存格式中。

### SPLADE 實作

```python
from transformers import AutoModelForMaskedLM, AutoTokenizer

class SpladeEncoder:
    def __init__(self, model_name="naver/splade-cocondenser-ensembledistil"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(model_name)

    def encode(self, text: str) -> dict[str, float]:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True)
        outputs = self.model(**inputs)

        # 取得稀疏權重
        weights = torch.max(
            torch.log(1 + torch.relu(outputs.logits)) * inputs["attention_mask"].unsqueeze(-1),
            dim=1
        ).values.squeeze()

        # 轉換為稀疏字典
        non_zero = weights.nonzero().squeeze().tolist()
        sparse_vec = {
            self.tokenizer.decode([idx]): weights[idx].item()
            for idx in non_zero
            if weights[idx] > 0
        }

        return sparse_vec
```

**何時使用 SPLADE 而非 BM25 + 密集混合：** SPLADE 產生的稀疏向量可以儲存在現代向量資料庫（如 Milvus 或 Qdrant）中，與密集向量並列，使混合檢索可以在單次檢索中完成，而不需要单独的 Elasticsearch 或 BM25 索引。如果你的資料集有極其罕見、非語言的詞彙（如唯一的序號），而神經模型在訓練時可能沒見過，請繼續使用 BM25。

---

## 實作模式

### 模式 1：Elasticsearch + 向量資料庫

```python
class HybridSearcher:
    def __init__(self, es_client, vector_db, embedding_model):
        self.es = es_client
        self.vector_db = vector_db
        self.embedding_model = embedding_model

    def search(self, query: str, top_k: int = 10, alpha: float = 0.5) -> list[Result]:
        # 並行檢索
        dense_future = self.dense_search(query, top_k * 3)
        sparse_future = self.sparse_search(query, top_k * 3)

        dense_results = dense_future.result()
        sparse_results = sparse_future.result()

        # 融合
        combined = reciprocal_rank_fusion([
            [r.id for r in dense_results],
            [r.id for r in sparse_results]
        ])

        return combined[:top_k]

    async def dense_search(self, query: str, top_k: int) -> list[Result]:
        embedding = self.embedding_model.encode(query)
        return self.vector_db.search(embedding, top_k=top_k)

    async def sparse_search(self, query: str, top_k: int) -> list[Result]:
        response = self.es.search(
            index="documents",
            body={
                "query": {"match": {"content": query}},
                "size": top_k
            }
        )
        return [
            Result(id=hit["_id"], score=hit["_score"])
            for hit in response["hits"]["hits"]
        ]
```

### 模式 2：Weaviate 原生混合

```python
import weaviate

def hybrid_search_weaviate(
    client: weaviate.Client,
    query: str,
    alpha: float = 0.5,
    top_k: int = 10
) -> list[dict]:
    result = client.query.get(
        "Document",
        ["text", "title", "source"]
    ).with_hybrid(
        query=query,
        alpha=alpha,  # 0 = 僅 BM25, 1 = 僅向量
        fusion_type=weaviate.HybridFusion.RELATIVE_SCORE
    ).with_limit(top_k).do()

    return result["data"]["Get"]["Document"]
```

---

## 調校與優化

### Alpha 調校

Alpha 參數平衡密集與稀疏：

```python
def find_optimal_alpha(
    test_queries: list[tuple[str, list[str]]],  # (查詢, 相關文件 ID)
    alpha_range: list[float] = [0.0, 0.3, 0.5, 0.7, 1.0]
) -> float:
    best_alpha = 0.5
    best_ndcg = 0

    for alpha in alpha_range:
        ndcg_scores = []
        for query, relevant in test_queries:
            results = hybrid_search(query, alpha=alpha)
            ndcg = compute_ndcg(results, relevant)
            ndcg_scores.append(ndcg)

        avg_ndcg = sum(ndcg_scores) / len(ndcg_scores)
        if avg_ndcg > best_ndcg:
            best_ndcg = avg_ndcg
            best_alpha = alpha

    return best_alpha
```

**最佳實務 / 典型發現：**
- 技術文件和程式碼：alpha 0.3-0.4（偏重關鍵字）
- 一般文字：alpha 0.5（平衡）
- 聊天和創意探索：alpha 0.7-0.9（偏重語意）

### 查詢自適應 Alpha

為每個查詢預測最佳 Alpha：

```python
def predict_alpha(query: str) -> float:
    # 基於啟發式
    has_quotes = '"' in query
    has_code = any(c in query for c in ['_', '()', '{}', '[]'])
    has_numbers = any(c.isdigit() for c in query)

    # 精確匹配查詢偏重稀疏
    if has_quotes or has_code:
        return 0.3
    if has_numbers:
        return 0.4

    # 自然語言偏重語意
    if len(query.split()) > 5:
        return 0.7

    return 0.5  # 預設平衡
```

### 檢索深度

融合前要抓取多少結果：

```python
# 經驗法則：從每個來源抓取 3-5 倍
def hybrid_search(query: str, final_k: int = 10):
    fetch_k = final_k * 4

    dense_results = dense_search(query, top_k=fetch_k)
    sparse_results = sparse_search(query, top_k=fetch_k)

    fused = rrf([dense_results, sparse_results])
    return fused[:final_k]
```

---

## 生產環境考量

### 延遲預算

```
典型混合檢索延遲分解：

密集嵌入：              30-50ms
密集檢索：             30-50ms
稀疏檢索：             20-40ms  （與密集並行）
融合：                  1-5ms
總計：                 60-100ms
```

**優化方式：**
- 密集和稀疏並行執行
- 預先計算常見查詢的嵌入
- 兩者都使用近似搜尋
- 快取重複查詢的融合結果

### 快取策略

```python
class HybridSearchCache:
    def __init__(self, ttl_seconds: int = 300):
        self.cache = TTLCache(ttl=ttl_seconds)

    def search(self, query: str, **kwargs) -> list[Result]:
        cache_key = self._make_key(query, kwargs)

        if cache_key in self.cache:
            return self.cache[cache_key]

        results = self._do_search(query, **kwargs)
        self.cache[cache_key] = results
        return results

    def _make_key(self, query: str, kwargs: dict) -> str:
        return hashlib.sha256(
            f"{query}:{sorted(kwargs.items())}".encode()
        ).hexdigest()
```

### 降級策略

```python
def hybrid_search_with_fallback(query: str, top_k: int = 10) -> list[Result]:
    try:
        return hybrid_search(query, top_k=top_k)
    except DenseSearchError:
        # 降級到僅稀疏
        return sparse_search(query, top_k=top_k)
    except SparseSearchError:
        # 降級到僅密集
        return dense_search(query, top_k=top_k)
```

---

## 面試問題

### Q：什麼時候會選擇混合檢索而非純密集檢索？

**理想回答：**
在以下情況會使用混合檢索：

1. **查詢包含特定術語：** 產品代碼、API 名稱、錯誤碼。密集檢索可能錯過精確匹配。

2. **領域有專業詞彙：** 技術文件、法律、醫療。稀疏檢索能捕捉特定術語。

3. **零樣本檢索：** 沒有微調嵌入的新領域。稀疏檢索提供穩健的基準。

4. **品質至關重要：** 混合檢索很少比任一方案單獨使用時表現更差，儘管有複雜度的代價。

**我會堅持使用純密集檢索的情況：**
- 查詢純粹是概念性/語意的
- 延遲預算非常緊張
- 架構簡單是優先考量
- 嵌入模型已針對領域充分調校

這個決定是基於實證的。我會在實際查詢分布上進行 A/B 測試混合檢索與密集檢索。

### Q：為什麼相互排名融合 (RRF) 比「簡單分數相加」更安全？

**理想回答：**
簡單分數相加是危險的，因為向量分數（例如餘弦相似度：0.0 到 1.0）和關鍵字分數（例如 BM25：0 到無窮大）使用完全不同的尺度。一個幸運的關鍵字匹配所產生極高的 BM25 分數，可能會「淹沒」10 個高度相關的語意匹配。RRF 忽略絕對分數，只關心相對順序（排名）。這使其在數學上對不同檢索引擎中的異常值和「分數漂移」具有穩健性。

### Q：什麼時候會選擇 SPLADE 而非標準 BM25 + 密集混合方案？

**理想回答：**
當我想簡化基礎設施時會選擇 SPLADE。SPLADE 產生的稀疏向量可以儲存在許多現代向量資料庫（如 Milvus 或 Qdrant）中，與密集向量並列。這使得資料庫能夠在單次檢索中執行「混合檢索」，而不需要单独的 Elasticsearch 或 BM25 索引。然而，如果我的資料集有極其罕見、非語言的詞彙（如唯一的序號），而神經模型在訓練時可能沒見過，我會繼續使用 BM25。

### Q：如何平衡混合檢索中的密集與稀疏？

**理想回答：**
Alpha 參數控制平衡（通常為密集的權重）：

**調校方法：**
1. 從 alpha=0.5（相等權重）開始
2. 建立帶有查詢和相關性標籤的評估集
3. 在 [0.1, 0.3, 0.5, 0.7, 0.9] 中網格搜索 alpha
4. 在每個設定下測量 NDCG 或 MRR
5. 選擇最大化評估指標的 alpha

**查詢自適應調校：**
- 偵測查詢類型（關鍵字密集、概念性、混合）
- 每個查詢調整 alpha
- 可以使用簡單的啟發式或學習分類器

**經驗法則：**
- 技術/程式碼查詢：alpha 0.3-0.4
- 一般文字：alpha 0.5
- 對話式：alpha 0.7-0.8

---

## 參考資料

- Cormack et al. "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods" (2009)
- Formal et al. "SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking" (2021/2025)
- Weaviate Hybrid Search: https://weaviate.io/developers/weaviate/search/hybrid
- Qdrant Hybrid Search: https://qdrant.tech/documentation/concepts/hybrid-queries/

---

*上一篇：[向量資料庫](04-vector-databases.md) | 下一篇：[重新排序策略](06-reranking-strategies.md)*
