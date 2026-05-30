# 重排序策略

重排序是檢索的第二階段，使用高精度模型對一小組候選文件（Top 50-100）進行重新評分。它是「高效搜尋」與「完美接地」之間的橋樑：第一階段檢索優化召回率，重排序優化精度。現今生產環境中有三種主流重排序器（BGE-Reranker-v2-m3、Cohere Rerank 3、Voyage rerank-2），選擇取決於成本模型、延遲尾端、語言覆蓋範圍，以及是否需要可自托管的權重。

## 目錄

- [為何需要重排序](#為何需要重排序)
- [重排序架構](#重排序架構)
- [重排序模型](#重排序模型)
- [實作模式](#實作模式)
- [何時該重排序](#何時該重排序)
- [基於 LLM 的重排序](#基於-llm-的重排序)
- [SLM 蒸餾](#slm-蒸餾)
- [生產環境考量](#生產環境考量)
- [面試問題](#面試問題)
- [參考文獻](#參考文獻)

---

## 為何需要重排序

### 品質差距

| 階段 | 模型 | 速度 | 品質 |
|------|------|------|------|
| 嵌入檢索 | 雙編碼器 | 快速（毫秒） | 良好 |
| 重排序 | 跨編碼器 | 慢（10-100 毫秒） | 更好 |

**差距存在的原因：**
- 雙編碼器獨立嵌入查詢和文件
- 跨編碼器 joint 處理查詢和文件
- Joint 處理能捕捉雙編碼器錯過的交互

### 範例

```
查詢：「如何設定 CUDA 記憶體」

文件 1：「使用 CUDA_VISIBLE_DEVICES 設定 GPU 記憶體...」
文件 2：「CUDA 應用程式中的記憶體管理...」
文件 3：「為機器學習設定 RAM 配置...」

雙編碼器分數（餘弦相似度）：
- 文件 1：0.72
- 文件 2：0.75  <-- 排名第一（錯誤）
- 文件 3：0.71

跨編碼器分數（相關性）：
- 文件 1：0.91  <-- 排名第一（正確）
- 文件 2：0.67
- 文件 3：0.42
```

跨編碼器看出查詢中的「CUDA 記憶體」與文件 1 中的「GPU 記憶體...CUDA」相關。

---

## 重排序架構

### 雙編碼器與跨編碼器比較

**雙編碼器（第一階段）：**
```
查詢 --> 編碼器 --> 查詢嵌入 -+
                                +-> 相似度
文件 --> 編碼器 --> 文件嵌入 -+
```
- 每個文件 O(1)（嵌入已預先計算）
- 無法看到查詢-文件交互

**跨編碼器（重排序）：**
```
[查詢, 文件] --> 編碼器 --> 相關性分數
```
- 每個查詢 O(n)（處理每個候選文件）
- 可見完整查詢-文件上下文
- 使用**注意力機制**來比較查詢中特定詞彙如何改變文件中詞彙的意義（晚期交互）

### 兩階段管線

生產環境檢索使用兩階段漏斗：

```
+----------------------------------------------------------------+
|  階段 1：檢索（雙編碼器）                                        |
|                                                                 |
|  查詢 --> 嵌入 --> Top-K 候選文件（K=100）                        |
|  規模：搜尋 10 億份文件。成本：低（毫秒）。                       |
+----------------------------+-----------------------------------+
|                             |
|                             v
+----------------------------------------------------------------+
|  階段 2：重排序（跨編碼器）                                       |
|                                                                 |
|  對每個候選文件：                                                 |
|    分數 = 重排序器([查詢, 候選文件])                              |
|  規模：搜尋 Top 100 文件。成本：高（10-100 毫秒）。               |
|                                                                 |
|  根據重排序器分數回傳 Top-N（N=5-10）                            |
+----------------------------------------------------------------+
```

### 多階段管線

對於非常大的語料庫：

```
階段 1：稀疏檢索（BM25）      -> Top 1000
階段 2：密集檢索（雙編碼器） -> Top 100
階段 3：跨編碼器              -> Top 10
```

每個階段以速度換取準確度。

---

## 重排序模型

### 跨編碼器模型

| 模型 | 參數大小 | 語言 | 品質 |
|------|----------|------|------|
| ms-marco-MiniLM-L-6 | 22M | 英文 | 良好 |
| bge-reranker-base | 278M | 英文 | 非常好 |
| **bge-reranker-v2-m3** | 568M | 多語言 | 優秀 |
| Cohere Rerank v3 | API | 多語言 | 優秀 |
| Jina Reranker v2 | 多種 | 多語言（8k+ tokens） | 非常好 |

**「迷失在中間」的修復**：重排序器訓練時會將相關資訊置於區塊中的任何位置都能正確評分，確保「中間」資料在送往最終 LLM 前被正確評分。

### 使用跨編碼器

```python
from sentence_transformers import CrossEncoder

# 載入模型
reranker = CrossEncoder('BAAI/bge-reranker-base')

def rerank(query: str, documents: list[str], top_k: int = 5) -> list[tuple[str, float]]:
    # 建立配對
    pairs = [[query, doc] for doc in documents]

    # 對所有配對評分
    scores = reranker.predict(pairs)

    # 按分數排序
    scored_docs = sorted(
        zip(documents, scores),
        key=lambda x: x[1],
        reverse=True
    )

    return scored_docs[:top_k]
```

### Cohere Rerank

```python
import cohere

co = cohere.Client(api_key="...")

def cohere_rerank(
    query: str,
    documents: list[str],
    top_k: int = 5
) -> list[dict]:
    response = co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=documents,
        top_n=top_k,
        return_documents=True
    )

    return [
        {
            "text": result.document.text,
            "score": result.relevance_score,
            "index": result.index
        }
        for result in response.results
    ]
```

### 模型選擇指南

| 使用情境 | 建議模型 | 備註 |
|----------|----------|------|
| 英文、自托管 | bge-reranker-base | 良好的平衡 |
| 多語言 | bge-reranker-v2-m3 | 最佳開源選擇 |
| 低延遲 | MiniLM-L-6 | 快 4 倍 |
| 最高品質 | Cohere Rerank v3 | API，規模化成本高 |
| 大批次 | Jina Reranker | 良好的吞吐量 |
| 長查詢（8k+） | Jina Reranker v2 | 處理長上下文 |

---

## 實作模式

### 模式 1：基本重排序

```python
class RerankedRetriever:
    def __init__(
        self,
        vector_db,
        embedding_model,
        reranker,
        retrieval_k: int = 50,
        rerank_k: int = 5
    ):
        self.vector_db = vector_db
        self.embedding_model = embedding_model
        self.reranker = reranker
        self.retrieval_k = retrieval_k
        self.rerank_k = rerank_k

    def search(self, query: str) -> list[Document]:
        # 階段 1：檢索候選文件
        query_embedding = self.embedding_model.encode(query)
        candidates = self.vector_db.search(
            query_embedding,
            top_k=self.retrieval_k
        )

        # 階段 2：重排序
        pairs = [[query, c.text] for c in candidates]
        scores = self.reranker.predict(pairs)

        # 合併並排序
        for candidate, score in zip(candidates, scores):
            candidate.rerank_score = score

        reranked = sorted(candidates, key=lambda x: x.rerank_score, reverse=True)
        return reranked[:self.rerank_k]
```

### 模式 2：批次重排序

```python
def batch_rerank(
    queries: list[str],
    candidates_per_query: list[list[str]],
    reranker,
    batch_size: int = 32
) -> list[list[tuple[str, float]]]:
    # 攤平所有配對
    all_pairs = []
    pair_mapping = []  # (query_idx, doc_idx)

    for q_idx, (query, candidates) in enumerate(zip(queries, candidates_per_query)):
        for d_idx, doc in enumerate(candidates):
            all_pairs.append([query, doc])
            pair_mapping.append((q_idx, d_idx))

    # 批次評分
    all_scores = []
    for i in range(0, len(all_pairs), batch_size):
        batch = all_pairs[i:i + batch_size]
        scores = reranker.predict(batch)
        all_scores.extend(scores)

    # 重建每個查詢的結果
    results = [[] for _ in queries]
    for (q_idx, d_idx), score in zip(pair_mapping, all_scores):
        results[q_idx].append((candidates_per_query[q_idx][d_idx], score))

    # 對每個查詢的結果排序
    for i in range(len(results)):
        results[i].sort(key=lambda x: x[1], reverse=True)

    return results
```

### 模式 3：非同步重排序

```python
import asyncio

class AsyncReranker:
    def __init__(self, reranker, max_concurrent: int = 5):
        self.reranker = reranker
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def rerank_async(
        self,
        query: str,
        documents: list[str]
    ) -> list[tuple[str, float]]:
        async with self.semaphore:
            # 在執行緒池中執行重排序
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None,
                lambda: self.reranker.predict([[query, doc] for doc in documents])
            )
            return sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
```

---

## 何時該重排序

### 成本效益分析

| 因素 | 不重排序 | 重排序 |
|------|----------|--------|
| 延遲 | 50-100 毫秒 | 150-300 毫秒 |
| 品質（NDCG） | 0.65 | 0.78 |
| 複雜度 | 簡單 | 中等 |
| 成本 | 基準線 | +API 成本或 +運算成本 |

### 決策框架

**始終重排序的情況：**
- 品質至關重要（面對客戶、高風險）
- 檢索到的候選文件分數相似
- 查詢複雜或多部分
- 預算允許延遲增加

**跳過重排序的情況：**
- 延遲預算非常緊張（總計 <100 毫秒）
- 檢索到的候選文件排名明確
- 簡單查詢（單一術語查找）
- 規模化成本受限

### 推論時間權衡

| 階段 | 檢索（K） | 重排序（N） | 延遲 | 品質 |
|------|-----------|-------------|------|------|
| **天真** | 5 | 0 | 50 毫秒 | 低 |
| **標準** | 50 | 5 | 150 毫秒 | 高 |
| **企業級** | 200 | 20 | 500 毫秒 | 最高 |

**核心原則**：如果你的預算是 200 毫秒，就花 50 毫秒在檢索上、150 毫秒在重排序上。對 Top 50 結果進行重排序比從向量資料庫檢索更多區塊具有更高的投資回報率。

### 最佳候選文件數量

在重排序前要檢索多少候選文件：

```python
def optimize_candidate_count(test_set, retriever, reranker):
    """找到重排序的最佳 retrieval_k。"""
    results = {}

    for retrieval_k in [10, 20, 50, 100, 200]:
        ndcg_scores = []
        latencies = []

        for query, relevant_docs in test_set:
            start = time.time()

            # 檢索
            candidates = retriever.search(query, top_k=retrieval_k)

            # 重排序到 Top 5
            reranked = reranker.rerank(query, candidates, top_k=5)

            latency = time.time() - start
            latencies.append(latency)

            ndcg = compute_ndcg(reranked, relevant_docs)
            ndcg_scores.append(ndcg)

        results[retrieval_k] = {
            "ndcg": mean(ndcg_scores),
            "latency_p99": percentile(latencies, 99)
        }

    return results

# 典型發現：
# K=20:  NDCG 0.72, 延遲 120 毫秒
# K=50:  NDCG 0.76, 延遲 180 毫秒  <-- 通常是最佳點
# K=100: NDCG 0.77, 延遲 280 毫秒  <-- 邊際效益遞減
```

---

## 基於 LLM 的重排序

### 使用 LLM 作為重排序器

LLM 可以評分相關性，但代價昂貴：

```python
def llm_rerank(
    query: str,
    documents: list[str],
    model: str = "gpt-4o-mini"
) -> list[tuple[str, float]]:
    prompt = f"""為每份文件評分其與查詢的相關性。
查詢：{query}

文件：
{format_documents(documents)}

對於每份文件，輸出 0-10 的相關性分數。
格式：DOC_NUM: SCORE
"""

    response = llm.generate(prompt)
    scores = parse_scores(response)

    return sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
```

**優點：**
- 可處理複雜的相關性判斷
- 理解細微差別和上下文
- 無需維護單獨的模型

**缺點：**
- 規模化成本高（比跨編碼器貴 10-100 倍）
- 速度較慢（1-3 秒 vs 100 毫秒）
- 非確定性

### Listwise 與 Pointwise LLM 重排序

**Pointwise：** 獨立評分每份文件
```
對於文件：[文件文字]
查詢：[查詢]
評分相關性 0-10：_
```

**Listwise：** 一起排名所有文件
```
查詢：[查詢]
按相關性對這些文件排名：
A：[文件 1]
B：[文件 2]
C：[文件 3]
輸出順序：_
```

**Listwise 通常更好**，因為 LLM 可以直接比較文件。前沿模型（如 o1-mini 或 Sonnet 3.7）在這方面非常出色，但會增加 1-2 秒的延遲。只有在高風險企業搜尋（法律、醫療）中使用。

### 適用於大量文件的滑動視窗

```python
def sliding_window_rerank(
    query: str,
    documents: list[str],
    window_size: int = 10,
    step: int = 5
) -> list[str]:
    """使用滑動視窗對大量文件進行 LLM 重排序。"""
    ranked = list(range(len(documents)))

    for start in range(0, len(documents), step):
        window = ranked[start:start + window_size]

        # LLM 對這個視窗進行排名
        window_docs = [documents[i] for i in window]
        window_order = llm_listwise_rank(query, window_docs)

        # 更新排名
        for new_pos, old_idx in enumerate(window_order):
            ranked[start + new_pos] = window[old_idx]

    return [documents[i] for i in ranked]
```

---

## SLM 蒸餾

為了解決基於 LLM 重排序的延遲問題，我們現在使用**蒸餾小型語言模型（SLM）**。

- **流程**：取一個巨型模型（例如 GPT-5.2），讓它對 100 萬對進行重排序，然後用這些標籤「蒸餾」一個 0.1B 參數的小模型。
- **結果**：獲得巨型模型重排序品質的 95%，但具有標準 CPU 查詢的延遲（< 10 毫秒）。
- **生產模式**：通常使用跨編碼器，在低信心分數的重排序分數上使用 LLM 作為備用。

---

## 生產環境考量

### 延遲優化

```python
class OptimizedReranker:
    def __init__(self, model_name: str, device: str = "cuda"):
        self.model = CrossEncoder(model_name, device=device)
        # 啟用優化
        self.model.model.half()  # FP16

    def rerank(self, query: str, documents: list[str]) -> list[tuple[str, float]]:
        with torch.inference_mode():
            pairs = [[query, doc] for doc in documents]
            scores = self.model.predict(
                pairs,
                batch_size=32,
                show_progress_bar=False
            )
        return sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
```

**優化技術：**
- FP16 推論：2 倍加速
- 批次處理：攤平開銷
- ONNX 匯出：1.5-2 倍加速
- TensorRT：2-3 倍加速（NVIDIA）
- 模型蒸餾：4 倍加速（有品質權衡）

### 快取重排序結果

```python
class CachedReranker:
    def __init__(self, reranker, cache_ttl: int = 3600):
        self.reranker = reranker
        self.cache = TTLCache(maxsize=10000, ttl=cache_ttl)

    def rerank(self, query: str, documents: list[str]) -> list[tuple[str, float]]:
        # 快取金鑰包含查詢和文件雜湊值
        key = self._make_key(query, documents)

        if key in self.cache:
            return self.cache[key]

        result = self.reranker.rerank(query, documents)
        self.cache[key] = result
        return result

    def _make_key(self, query: str, documents: list[str]) -> str:
        doc_hash = hashlib.sha256(
            "".join(sorted(documents)).encode()
        ).hexdigest()[:16]
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"{query_hash}:{doc_hash}"
```

### 備用策略

```python
def rerank_with_fallback(
    query: str,
    candidates: list[Document],
    primary_reranker,
    timeout: float = 2.0
) -> list[Document]:
    try:
        # 嘗試在超時前重排序
        result = timeout_call(
            primary_reranker.rerank,
            args=(query, candidates),
            timeout=timeout
        )
        return result
    except TimeoutError:
        # 備用：回傳原始順序
        logger.warning("重排序超時，使用原始順序")
        return candidates
    except Exception as e:
        logger.error(f"重排序錯誤：{e}")
        return candidates
```

---

## 面試問題

### Q：為什麼跨編碼器从根本上比雙編碼器更準確？

**強而有力的回答：**
雙編碼器在知道任何查詢之前就為文件創建了一個單一、靜態的向量表示。這會丟失文字不同部分之間的特定關係。跨編碼器將查詢和文件作為單一輸入配對處理，並使用**注意力機制**來比較它們。它可以看到查詢中特定詞彙如何改變文件中詞彙的意義（晚期交互），這使得比兩個固定向量簡單數學相似性更細緻的相關性評分成為可能。

**實際應用：** 第一階段檢索用雙編碼器（速度），重排序用跨編碼器（品質）。這是兩全其美的。

### Q：你如何決定要重排序多少候選文件？

**強而有力的回答：**
品質和延遲之間的權衡：

**因素：**
- 每份文件的重排序器延遲
- 總延遲預算
- 品質改進曲線（通常邊際效益遞減）
- 第一階段檢索品質

**流程：**
1. 對每份文件進行重排序器延遲基準測試
2. 計算延遲預算內的最大候選文件數
3. 在不同 K 值下測試品質
4. 找到拐點（品質 vs 延遲）

**典型發現：**
- K=20-50 通常是最優的
- 超過 K=100，品質提升極小
- 根據第一階段檢索品質調整

對於 200 毫秒的重排序預算，每份文件 4 毫秒，我會重排序大約 50 個候選文件。

### Q：何時會使用基於 LLM 的重排序？

**強而有力的回答：**
LLM 重排序在以下情況有意義：

1. **複雜的相關性判斷：** 查詢需要理解細微差別、上下文或多跳推理
2. **低量：** 無法合理化訓練/托管跨編碼器
3. **需要最高品質：** 法律、醫療、安全關鍵
4. **已在管線中使用 LLM：** 邊際成本較低

**注意事項：**
- 規模化成本高（比跨編碼器貴 10-100 倍）
- 速度較慢（1-3 秒 vs 100 毫秒）
- 非確定性
- 可能需要仔細的提示工程

**生產模式：** 通常使用跨編碼器，在低信心分數的重排序分數上使用 LLM 作為備用。

### Q：如何處理極長查詢的重排序（例如整個段落）？

**強而有力的回答：**
長查詢對通常有 512 或 1024 token 限制的跨編碼器來說是「Token 預算」問題。常見的修復方法是**滑動視窗重排序**或**查詢摘要**。或者，使用像 **Jina-Reranker-v2** 這樣處理 8k+ tokens 的專業模型。常見的還有「第一遍重排序」使用快速的短上下文模型，然後對 Top 5 候選文件進行「第二遍重排序」使用高上下文 LLM。

---

## 參考文獻

- Nogueira and Cho. 「使用 BERT 進行段落重排序」（2019）
- Nogueira et al. 「使用 BERT 的多階段文件排名」（2019/2025 更新）
- BAAI BGE Reranker：https://huggingface.co/BAAI/bge-reranker-base
- Cohere Rerank：https://docs.cohere.com/docs/rerank
- Sun et al. 「ChatGPT 擅長搜尋嗎？研究大型語言模型作為排名代理」（2023）

---

*上一篇：[混合搜尋](05-hybrid-search.md) | 下一篇：[GraphRAG](07-graph-rag.md)*
