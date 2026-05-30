# 嵌入和向量空間

嵌入是文字的密集向量表示，捕捉語義含義。它們是 RAG 系統、語義搜尋和許多 AI 應用的基礎。

## 目錄

- [什麼是嵌入](#what-are-embeddings)
- [嵌入模型架構](#embedding-model-architectures)
- [訓練目標](#training-objectives)
- [距離度量](#distance-metrics)
- [嵌入模型比較](#embedding-model-comparison)
- [Matryoshka 和自適應維度](#matryoshka-and-adaptive-dimensions)
- [晚期互動 vs 晚期分塊](#late-interaction-vs-late-chunking)
- [二元和標量量化](#binary-and-scalar-quantization)
- [實用考量（批次處理、快取）](#practical-considerations-batching-caching)
- [嵌入漂移和版本控制](#embedding-drift-and-versioning)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 什麼是嵌入

嵌入將離散文字（單詞、句子、文件）映射到連續向量空間，其中語義相似性對應於幾何接近度。

**關鍵特性：**
- 相似含義彼此接近
- 關係可以編碼為向量運算（king - man + woman = queen）
- 通過近似最近鄰居演算法實現高效相似性搜尋

**心理模型：**
將嵌入視為非常高維空間中的座標。維度（512 到 4096）提供表達能力。每個維度捕捉含義的某個方面，儘管個別維度是不可解釋的。

---

## 嵌入模型架構

### 單詞嵌入（歷史）

早期方法嵌入單個單詞：

| 模型 | 年份 | 方法 | 限制 |
|-------|------|----------|------------|
| Word2Vec | 2013 | Skip-gram、CBOW | 靜態：「bank」在所有語境中相同 |
| GloVe | 2014 | 共現矩陣 | 靜態 |
| FastText | 2017 | 子詞嵌入 | 靜態，但處理 OOV |

**關鍵限制：** 無論語境如何，相同單詞獲得相同的嵌入。

### 上下文嵌入

基於 Transformer 的模型產生依賴語境的嵌入：

```python
# 靜態嵌入（Word2Vec）
embed("bank") = [0.1, 0.3, ...]  # 總是相同的向量

# 上下文嵌入（BERT）
embed("river bank") = [0.1, 0.3, ...]   # 地理意義
embed("bank account") = [0.5, 0.2, ...]  # 金融意義
```

### 句子/文件嵌入

對於檢索，我們需要嵌入整個文字：

| 方法 | 說明 | 優點 | 缺點 |
|----------|--------|------|------|
| 平均池化 | 平均 token 嵌入 | 簡單 | 丟失資訊 |
| CLS token | 使用 [CLS] token 嵌入 | BERT 標準 | 可能無法捕捉完整文字 |
| 最後 token | 使用最後 token | 適用於解碼器模型 | 位置偏差 |
| 訓練的池化 | 學習池化權重 | 更好的質量 | 需要訓練 |

現代嵌入模型專門為句子/文件嵌入而訓練，而不僅僅是從語言模型改編。

### 雙編碼器架構

標準檢索嵌入架構：

```
文件 -> 編碼器 -> 文件嵌入
查詢 -> 編碼器 -> 查詢嵌入

相似度 = cosine(doc_embedding, query_embedding)
```

**特性：**
- 文件可以預先計算和索引
- 查詢嵌入在查詢時計算
- 每文件 O(1) 相似度計算（使用 ANN）

### 交叉編碼器架構

共同處理查詢和文件的替代方案：

```
[查詢, 文件] -> 編碼器 -> 相關性分數
```

**特性：**
- 更準確（一起看到兩者）
- 無法預先計算：n 個文件需要 O(n) 推理
- 用於重新排序，而非檢索

---

## 訓練目標

### 對比學習

大多數現代嵌入模型使用對比學習：

```python
# 簡化的對比損失
def contrastive_loss(anchor, positive, negatives):
    pos_sim = cosine_similarity(anchor, positive)
    neg_sims = [cosine_similarity(anchor, neg) for neg in negatives]
    
    # 推近正樣本，推遠負樣本
    loss = -log(exp(pos_sim / tau) / 
                (exp(pos_sim / tau) + sum(exp(neg_sim / tau) for neg_sim in neg_sims)))
    return loss
```

**關鍵因素：**
- **正樣本對：** 語義相似的文字（平行句子、查詢-文件對）
- **困難負樣本：** 相似但不相關的文字（BM25 檢索的非相關項）
- **批次內負樣本：** 其他批次項目作為負樣本（高效）

### 訓練資料來源

| 來源 | 正樣本對 | 品質 | 規模 |
|--------|---------------|---------|-------|
| 平行句子 | 翻譯對 | 高 | 中等 |
| 查詢-文件 | 搜尋日誌 | 高 | 中等 |
| 標題-正文 | 文件結構 | 中等 | 大 |
| 改寫 | NLI 資料集 | 高 | 小 |
| 生成 | LLM 創建對 | 可變 | 大 |

### 指令調整嵌入

最近模型接受任務指令：

```python
# 指令調整的（例如 E5、BGE）
query_embedding = embed("Represent this query for retrieval: What is RAG?")
doc_embedding = embed("Represent this document for retrieval: RAG combines...")
```

這通過指定預期用途來提高性能。

---

## 距離度量

### 餘弦相似度

對於文字嵌入最常用：

```python
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

**特性：**
- 範圍：[-1, 1]（對於正規化向量，[0, 1]如果是正的）
- 測量角度，而非大小
- 對向量長度不變

**何時使用：** 文字嵌入的預設選擇。

### 點積

```python
def dot_product(a, b):
    return np.dot(a, b)
```

**特性：**
- 大小很重要
- 無界範圍
- 對於正規化向量等於餘弦

**何時使用：** 當嵌入已經正規化時，或者當大小有意義時。

### 歐幾里得距離

```python
def euclidean_distance(a, b):
    return np.linalg.norm(a - b)
```

**特性：**
- 測量絕對差異
- 受大小影響
- 對於正規化向量：sqrt(2 - 2 * cosine)

**何時使用：** 很少用於文字；更常用於圖像嵌入。

### 度量選擇

| 度量 | 向量資料庫 | 常見用途 |
|--------|------------------|------------|
| 餘弦 | Pinecone、Qdrant、Weaviate | 文字嵌入 |
| 點積 | 所有主要 DB | 正規化嵌入 |
| 歐幾里得 | 所有主要 DB | 圖像、多模態 |

---

## 嵌入模型比較

### 當前頂級模型（2025 年 12 月）

| 模型 | 維度 | 最大 Token | MTEB 檢索 | 每 1M Token 成本 |
|-------|------------|------------|----------------|------------------|
| OpenAI text-embedding-4 | 3072 | 16k | 68.2 | $0.10 |
| Voyage-4 | 1024 | 128k | 70.1 | $0.05 |
| Cohere embed-v3.5 | 1024 | 512 | 67.5 | $0.10 |
| Google text-embedding-005 | 768 | 8k | 67.2 | $0.02 |

*MTEB 分數是近似的，因基準測試子集而異。始終驗證當前值。英語排行榜目前由 Gemini Embedding 001（68.32）領先；多語言排行榜由 Qwen3-Embedding-8B（70.58）和 Llama-Embed-Nemotron-8B 領先。*

### 開源模型

| 模型 | 維度 | 最大 Token | MTEB 檢索 | 備註 |
|-------|------------|------------|----------------|-------|
| BGE-large-en-v1.5 | 1024 | 512 | 63.9 | 強大的開源模型 |
| E5-large-v2 | 1024 | 512 | 62.4 | 指令調整 |
| GTE-large | 1024 | 512 | 63.1 | 阿里巴巴 |
| Nomic-embed-text-v1.5 | 768 | 8192 | 62.3 | 長上下文、開源 |

### 選擇標準

| 因素 | 考量 |
|--------|----------------|
| 品質（MTEB） | 越高越好，但任務特定評估更重要 |
| 維度 | 越高 = 越有表達力但更多儲存/計算 |
| 最大 token | 必須容納您的文件大小 |
| 成本 | API 與自託管的權衡 |
| 延遲 | 嵌入生成時間 |
| 多語言 | 如果服務非英語內容 |

---

## Matryoshka 和自適應維度

### 理念

Matryoshka 表示學習（MRL）訓練嵌入，使得完整嵌入的前綴也是有意義的：

```python
full_embedding = model.encode(text)  # 1024 維度

# 這些都是具有遞減質量的有效嵌入
dim_512 = full_embedding[:512]  
dim_256 = full_embedding[:256]
dim_128 = full_embedding[:128]
dim_64 = full_embedding[:64]
```

### 為什麼重要

| 用例 | 維度 | 權衡 |
|----------|-----------|----------|
| 完整檢索 | 1024-3072 | 峰值準確度 |
| **兩階段檢索**| 128 -> 1024 | **生產標準**：用 128-d 檢索 1000 個，用 1024-d 優化前 100 個。 |
| 成本敏感 | 256 | 12 倍儲存節省，<2% MRR 損失 |
| 邊緣/移動 | 64 | 最大速度，處理簡單意圖 |

### 支持 Matryoshka 的模型

- OpenAI text-embedding-3-*（原生）
- Nomic-embed-text-v1.5
- 幾個微調模型

### 使用 Matryoshka 嵌入

```python
from openai import OpenAI
client = OpenAI()

# 請求較小的維度
response = client.embeddings.create(
    model="text-embedding-3-large",
    input="Your text here",
    dimensions=256  # 請求 256 而非完整的 3072
)
```

---

### 晚期分塊（2025 年轉變）

**傳統分塊：** `文件 -> 分塊 -> 個別嵌入區塊`
- **問題**：區塊 2 丟失來自區塊 1 的上下文。

**晚期分塊（由 Jina AI/Voyage 引入）：** `完整文件 -> 模型編碼器 -> Token 級嵌入 -> 在區塊邊界池化`
- **優勢**：每個區塊的嵌入包含來自**整個文件**的資訊，因為 Transformer 的自注意力在池化之前應用於完整序列。
- **要求**：支持長上下文的模型（至少 8k+ token）。

---

## 二元和標量量化

為處理數十億個向量，**二元**和**標量（Int8）**量化現在是標準。

| 類型 | 資料大小 | 記憶體節省 | 質量損失 | 支持者 |
|------|-----------|----------------|--------------|--------------|
| Float32 | 4 位元組/維度 | 基線 | 0% | 全部 |
| Int8 | 1 位元組/維度 | 4x | <1% | Cohere、BGE |
| **二元** | **1 位元組/維度** | **32x** | ~5-10% | Cohere v3、v4 |

**二元量化模式：**
1. 使用二元嵌入檢索前 1000 個（極快）。
2. 使用 Float32 或交叉編碼器對前 50 個重新排序（峰值準確度）。

### 何時使用 ColBERT

- 檢索精度至關重要
- 可以負擔儲存開銷
- 查詢延遲預算 > 50ms

### 實現

```python
# 使用 RAGatouille
from ragatouille import RAGPretrainedModel

model = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")

# 索引文件
model.index(
    collection=documents,
    index_name="my_index"
)

# 搜尋
results = model.search(query="What is RAG?", k=10)
```

---

## 實用考量

### 批次處理

```python
# 低效：每個文件一次 API 調用
embeddings = [embed(doc) for doc in documents]

# 高效：批次 API 調用
batch_size = 100
embeddings = []
for i in range(0, len(documents), batch_size):
    batch = documents[i:i + batch_size]
    batch_embeddings = embed_batch(batch)
    embeddings.extend(batch_embeddings)
```

### 用於嵌入的分塊

長文件必須在嵌入前分塊：

```python
def embed_document(document: str, max_tokens: int = 512) -> list[np.array]:
    chunks = chunk_document(document, max_tokens=max_tokens)
    embeddings = []
    for chunk in chunks:
        embedding = embed(chunk)
        embeddings.append(embedding)
    return embeddings
```

**考量：**
- 區塊大小應小於模型最大 token
- 重疊有助於在區塊邊界保留上下文
- 儲存區塊到文件的映射以便檢索

### 正規化

許多系統期望正規化嵌入：

```python
def normalize(embedding):
    norm = np.linalg.norm(embedding)
    return embedding / norm

# 正規化向量的餘弦相似度 = 點積
similarity = np.dot(normalize(a), normalize(b))
```

大多數向量資料庫和嵌入 API 處理正規化，但請驗證。

### 快取

嵌入計算是昂貴的。積極快取：

```python
import hashlib

def get_embedding(text: str, cache: dict) -> np.array:
    key = hashlib.sha256(text.encode()).hexdigest()
    
    if key in cache:
        return cache[key]
    
    embedding = compute_embedding(text)
    cache[key] = embedding
    return embedding
```

---

## 嵌入漂移和版本控制

### 問題

嵌入在以下情況下不可比較：
- 不同模型
- 相同模型的不同版本
- 有時不同的 API 調用（有些 API 有非確定性）

### 後果

如果您更新嵌入模型：
- 所有現有嵌入變得不相容
- 必須重新嵌入整個語料庫
- 遷移期間搜尋結果將不一致

### 緩解策略

**1. 對嵌入進行版本控制：**
```python
embedding_metadata = {
    "model": "text-embedding-3-large",
    "model_version": "2024-01",
    "dimensions": 3072,
    "created_at": "2025-12-16"
}
```

**2. 規劃重新嵌入：**
- 估計完整重新嵌入的成本和時間
- 建置可以在背景運行的管道
- 在切換前測試新嵌入

**3. 藍綠部署：**
```
索引 A：當前嵌入
索引 B：新嵌入（建置中）

查詢 -> 兩個索引 -> 合併或切換
```

**4. 追蹤嵌入質量：**
- 持續監控檢索指標
- 檢測嵌入分佈中的漂移
- 對質量下降發出警報

---

## 面試問題

### Q：嵌入模型如何學習語義相似性？

**強而有力的回答：**
嵌入模型使用對比學習進行訓練。目標是使語義相似文字的嵌入彼此接近，使不相似的文字彼此遠離。

訓練過程：
1. 正樣本對：應該相似的文字（查詢-文件對、改寫、翻譯）
2. 負樣本對：應該不相似的文字（通常來自同一批次或 BM25 的困難負樣本）
3. 損失函數：推近正樣本對，推遠負樣本對

模型學習將文字放置在高維空間中，其中距離與語義相似性相關。這使得檢索成為可能：嵌入查詢，在文件嵌入空間中找到最近鄰居。

現代模型如 E5 和 BGE 也是指令調整的，您可以使用任務指令作為前綴來專門化嵌入。

### Q：什麼時候使用 ColBERT 而不是雙編碼器？

**強而有力的回答：**
ColBERT 使用晚期互動：不是每個文件一個嵌入，而是保留每 token 嵌入。在查詢時，它計算 token 級相似度。

在以下情況選擇 ColBERT：
- 檢索精度至關重要（法律、醫療、高風險）
- 可以負擔每文件 10-100 倍的儲存開銷
- 查詢延遲預算為 50ms+（比雙編碼器稍慢）
- 您的查詢受益於詞彙匹配（技術術語）

在以下情況選擇雙編碼器：
- 儲存受限
- 需要 <20ms 延遲
- 雙編碼器的檢索精度足夠
- 頻繁重新索引（ColBERT 重新索引昂貴）

實際上，常見模式是：雙編碼器用於第一階段檢索（前 100 個），然後使用交叉編碼器或 ColBERT 進行重新排序。

### Q：更新模型時如何處理嵌入漂移？

**強而有力的回答：**
嵌入漂移是指當您切換到新的嵌入模型或版本時，舊嵌入和新嵌入不再可比較的問題。

策略：

1. **版本控制**：始終追蹤嵌入使用的模型和版本。使用中繼資料標記每個嵌入。

2. **藍綠部署**：在建置新索引的同時保持舊索引運行。通過查詢兩個索引並比較結果來驗證新索引。

3. **漸進式遷移**：不要一次切換所有內容。先對一小部分請求測試新嵌入，監控品質指標。

4. **重新嵌入計劃**：遲早需要重新嵌入。提前規劃並預算時間和成本。

5. **混合方法**：在過渡期間，同時查詢舊索引和新索引，並合併結果。

6. **監控**：部署後，持續監控檢索品質指標，以捕捉任何回歸。

---

## 參考文獻

- Reimers and Gurevych. "Sentence-BERT: A Sentence Embedding Model using Siamese BERT-Networks" (2019)
- Karpukhin et al. "Dense Passage Retrieval for Open-Domain Question Answering" (2020)
- Gao et al. "Text Embeddings by Contrastive Learning" (2021)
- Li et al. "Midpoint": "Late Chunking: Chunked Vectors Can Retrieve Meaning" (2024)

---

*上一章：[Transformer 架構](04-transformer-architecture.md) | 下一章：[推論管道](06-inference-pipeline.md)*
