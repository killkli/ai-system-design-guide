# 推論管道

本章涵蓋 LLM 在推論時如何生成文字、涉及的計算階段，以及生產服務的關鍵指標。

## 目錄

- [生成基礎](#generation-basics)
- [預填充和解碼階段](#prefill-and-decode-phases)
- [採樣策略](#sampling-strategies)
- [停止條件](#stopping-conditions)
- [潛在優化：推測解碼](#speculative-decoding)
- [延遲指標和 TTFT 與 TPS](#latency-metrics)
- [記憶體和計算需求](#memory-and-compute-requirements)
- [連續批次處理和前綴快取](#continuous-batching-and-prefix-caching)
- [多 LoRA 服務](#multi-lora-serving)
- [串流](#streaming)
- [生產考量](#production-considerations)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 生成基礎

LLM 自迴歸生成文字：一次一個 token，使用所有先前的 token 作為上下文。

```
輸入："The quick brown"
步驟 1：生成 "fox" -> "The quick brown fox"
步驟 2：生成 "jumps" -> "The quick brown fox jumps"
步驟 3：生成 "over" -> "The quick brown fox jumps over"
...
```

### 生成循環

```python
def generate(prompt: str, max_tokens: int, model) -> str:
    tokens = tokenize(prompt)
    
    for _ in range(max_tokens):
        # 前向傳遞：獲取下一個 token 的 logits
        logits = model.forward(tokens)
        
        # 從機率分佈中採樣下一個 token
        next_token = sample(logits[-1])
        
        # 檢查停止條件
        if next_token == EOS_TOKEN:
            break
        
        tokens.append(next_token)
    
    return detokenize(tokens)
```

---

## 預填充和解碼階段

推論有兩個具有不同特性的不同階段：

### 預填充階段

平行處理整個輸入提示。

```
輸入："The quick brown fox"（4 個 token）

預填充：
- 同時處理所有 4 個 token
- 計算所有配對之間的注意力
- 為所有位置填充 KV 快取
- 輸出：下一個 token 的 logits
```

**特性：**
- 計算受限（大量矩陣運算）
- 可跨 token 平行化
- 時間隨提示長度縮放
- 每生成一次發生一次

### 解碼階段

一次生成一個 token。

```
解碼步驟 1：
- 輸入：僅新 token 位置
- 關注所有 KV 快取（提示 + 先前生成的）
- 生成一個 token

解碼步驟 2：
- 將新的 K、V 附加到快取
- 輸入：最新 token 位置
- 生成下一個 token

...重複直到完成
```

**特性：**
- 記憶體受限（從 HBM 載入 KV 快取）
- 依序（必須完成每個步驟才能開始下一個）
- 每 token 時間大致恆定
- 重複直到滿足停止條件

### 為什麼這很重要

| 階段 | 瓶頸 | 優化 |
|-------|------------|--------------|
| 預填充 | 計算（GPU 核心） | 閃電注意力、更好的 GPU |
| 解碼 | 記憶體頻寬 | GQA、批次處理、量化 |

**對服務的影響：**
- 長提示增加預填充時間（影響 TTFT）
- 長生成增加解碼時間（影響總延遲）
- 批次處理對解碼效率的幫助比預填充更多

---

## 採樣策略

在計算 logits 後，我們需要選擇下一個 token。不同的策略產生不同的輸出。

### 貪心解碼

始終選擇最高機率 token：

```python
def greedy_sample(logits):
    return torch.argmax(logits)
```

**特性：**
- 確定性
- 對於長生成通常重複
- 適用於事實/結構化輸出

### 溫度採樣

在 softmax 前縮放 logits 以控制隨機性：

```python
def temperature_sample(logits, temperature=1.0):
    scaled_logits = logits / temperature
    probs = torch.softmax(scaled_logits, dim=-1)
    return torch.multinomial(probs, num_samples=1)
```

**溫度效果：**

| 溫度 | 行為 | 用例 |
|-------------|----------|----------|
| 0 | 貪心（確定性） | 事實問答、程式碼 |
| 0.3-0.7 | 低隨機性 | 一般任務 |
| 1.0 | 基線 | 創意寫作 |
| 1.5+ | 高隨機性 | 腦力激盪 |

### Top-K 採樣

只考慮 K 個最高機率 token：

```python
def top_k_sample(logits, k=50):
    values, indices = torch.topk(logits, k)
    probs = torch.softmax(values, dim=-1)
    sampled_idx = torch.multinomial(probs, num_samples=1)
    return indices[sampled_idx]
```

**效果：** 過濾掉可能無意義的低機率 token。

### Top-P（核心）採樣

包括 token 直到累積機率超過 P：

```python
def top_p_sample(logits, p=0.9):
    sorted_probs, sorted_indices = torch.sort(
        torch.softmax(logits, dim=-1), descending=True
    )
    cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
    
    # 找到截止點
    cutoff_idx = torch.searchsorted(cumulative_probs, p)
    
    # 從截斷分佈中採樣
    selected_probs = sorted_probs[:cutoff_idx + 1]
    selected_probs = selected_probs / selected_probs.sum()
    sampled_idx = torch.multinomial(selected_probs, num_samples=1)
    
    return sorted_indices[sampled_idx]
```

**相對於 Top-K 的優勢：** 根據機率分佈動態調整。高置信度預測包含更少的 token；不確定的預測包含更多。

### 常見配置

| 用例 | 溫度 | Top-P | Top-K |
|----------|-------------|-------|-------|
| 程式碼生成 | 0-0.2 | 0.95 | - |
| 事實問答 | 0.1-0.3 | 1.0 | - |
| 一般聊天 | 0.7 | 0.9 | - |
| 創意寫作 | 1.0 | 0.95 | - |
| 腦力激盪 | 1.2 | 1.0 | - |

### 重複懲罰

降低最近生成 token 的機率：

```python
def apply_repetition_penalty(logits, generated_tokens, penalty=1.2):
    for token_id in set(generated_tokens):
        logits[token_id] /= penalty
    return logits
```

**變體：**
- 存在懲罰：懲罰所有出現過的 token
- 頻率懲罰：按出現次數比例懲罰

---

## 停止條件

生成持續直到滿足停止條件：

### EOS Token

模型生成序列結束 token：

```python
if next_token == tokenizer.eos_token_id:
    break
```

### 最大 Token

生成長度的硬限制：

```python
for i in range(max_tokens):
    # 生成...
```

### 停止序列

終止生成的自訂字串：

```python
stop_sequences = ["###", "\n\n", "Human:"]

for seq in stop_sequences:
    if output.endswith(seq):
        output = output[:-len(seq)]
        break
```

---

## 潛在優化：推測解碼

**高頻寬服務的當前標準。**

推測解碼使用較小的「草稿模型」在一個步驟中預測多個未來 token，然後由較大的「目標模型」並行驗證。

```
草稿模型（小）：預測 5 個 token -> "The", "quick", "brown", "fox", "jumps"
目標模型（大）：在一個前向傳遞中驗證所有 5 個 token。
結果：如果目標同意 4 個 token，我們用 1 次大前向傳遞的成本生成了 4 個 token。
```

| 方法 | 方法 | 加速 | 範例 |
|--------|----------|---------|---------|
| 草稿模型 | 小模型（例如 1B）+ 大模型（70B） | 2x-3x | vLLM、TGI |
| **Medusa 頭** | 同一模型上的多個 LM 頭 | 1.5x-2x | Medusa、Eagle |
| 提示查詢 | 使用提示中的子字串作為推測 | 1.2x | RAG / 程式碼完成 |

---

## 延遲指標

### 首個 Token 的時間（TTFT）

從請求到首個生成 token 的時間。

```
TTFT = 網路延遲 + 排隊時間 + 預填充時間
```

**什麼影響 TTFT：**
- 提示長度（預填充是 O(n)）
- 模型大小
- GPU 速度
- 排隊深度

**目標：**
- 互動聊天：< 500ms
- 即時：< 200ms
- 批次：不那麼關鍵

### 每秒 Token（TPS）

首個 token 之後的 token 生成速率。

```
TPS = (總 token - 1) / (總時間 - TTFT)
```

**什麼影響 TPS：**
- 模型大小
- 批次大小
- GPU 記憶體頻寬
- KV 快取大小

**典型值：**
- H100 上的 Llama 70B：每請求 30-50 tokens/秒
- 透過 API 的 GPT-4：20-80 tokens/秒（可變）
- 小模型（7B）：100+ tokens/秒

### 總延遲

```
總延遲 = TTFT + (輸出 token / TPS)
```

**範例：**
- TTFT：200ms
- TPS：50 tokens/秒
- 輸出：100 tokens
- 總延遲：200ms + 2000ms = 2.2s

### 吞吐量

單位時間完成的請求數：

```
吞吐量 = 並發請求 * TPS / 平均輸出 token
```

更大的批次大小增加吞吐量，但可能增加每請求延遲。

---

## 記憶體和計算需求

### 模型權重

```
記憶體 = 參數 * 每參數位元組

FP16 中的 70B 模型：
= 70B * 2 位元組
= 140 GB

INT4 中的 70B 模型：
= 70B * 0.5 位元組
= 35 GB
```

### KV 快取

```
每 token：2 * 層數 * 頭數 * 頭維度 * 位元組
每請求：每 token * 序列長度

Llama 70B（80 層、64 頭、128 維度、FP16）：
= 2 * 80 * 64 * 128 * 2 位元組
= 每 token 2.6 MB

4K 上下文：每請求 10.5 GB
8K 上下文：每請求 21 GB
```

### 總 GPU 記憶體

```
總計 = 模型權重 + KV 快取 * 批次大小 + 激活

範例：Llama 70B 服務
- 權重（INT4）：35 GB
- KV 快取（8K、批次 4）：84 GB
- 激活：~5 GB
- 總計：~124 GB（適合 2x H100 80GB）
```

### 每 Token 的 FLOPs

```
前向傳遞 FLOPs ≈ 2 * 參數

70B 模型：
≈ 140 TFLOPs 每 token

以 40 tokens/秒：
≈ 5.6 PFLOPs 持續
```

---

## 串流

對於互動應用，隨生成串流 token：

### 伺服器端事件（SSE）

```python
# 伺服器
async def generate_stream(prompt: str):
    for token in model.generate_iter(prompt):
        yield f"data: {json.dumps({'token': token})}\n\n"
    yield "data: [DONE]\n\n"

# 用戶端
async for event in sse_client.stream("/generate"):
    token = json.loads(event.data)["token"]
    display(token)
```

### 優勢

| 方面 | 串流 | 非串流 |
|--------|-----------|---------------|
| 感知延遲 | 僅 TTFT | 完整生成時間 |
| 用戶體驗 | 漸進 | 等待，然後完整 |
| 提前終止 | 用戶可以停止 | 必須等待 |
| 記憶體 | 較低 | 較高（緩衝回應） |

### 實現細節

- 每個 token 後刷新
- 優雅處理連接中斷
- 考慮為非常快的生成緩衝
- 有些框架預設緩衝；串流時停用

---

## 生產考量

### 批次處理以提高吞吐量

組合多個請求以最大化 GPU 利用率：

```python
# 無批次處理：GPU 利用不足
for request in requests:
    response = model.generate(request)

# 批次處理：平行處理
batch = collect_requests(timeout=10ms, max_batch=32)
responses = model.generate_batch(batch)
```

### 連續批次處理和前綴快取

**連續批次處理（疊代級排程）：**
與靜態批次處理不同，連續批次處理在批次中的任何請求達到 EOS token 時立即注入新請求。這可以將吞吐量提高多達 20 倍。

**前綴快取（RAD-O）：**
快取常見前綴（例如系統提示、少樣本範例）的 KV 張量。
- **TTFT 減少**：90%
- **機制**：使用前綴的雜湊值在 GPU 記憶體 LRU 快取中查詢 KV 張量。

### 多 LoRA 服務

**場景：** 在一個基礎模型上服務 1000 個不同的微調模型（適配器）。
**挑戰：** 載入 1000 個單獨模型將佔用 TB 的 VRAM。

**解決方案（LoRAX / S-LoRA）：**
1. 在 VRAM 中載入一個基礎模型。
2. 將 LoRA 適配器（MB）儲存在主機 RAM 或 SSD 中。
3. 根據請求 ID 在前向傳遞期間動態交換適配器。
4. **實現**：使用專門的內核（S-LoRA）在同一批次中執行多個不同適配器的矩陣-向量乘法。

### 請求優先級

```python
class RequestQueue:
    def __init__(self):
        self.high_priority = asyncio.Queue()
        self.low_priority = asyncio.Queue()
    
    async def get_next(self):
        if not self.high_priority.empty():
            return await self.high_priority.get()
        return await self.low_priority.get()
```

**優先級標準：**
- 客戶層級
- 請求類型
- 等待時間
- 估計計算成本

### 超時處理

```python
async def generate_with_timeout(prompt: str, timeout: float):
    try:
        result = await asyncio.wait_for(
            model.generate(prompt),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        return {"error": "Generation timeout"}
```

**最佳實踐：**
- 為不同請求類型設置不同的超時
- 提供有意义的超時錯誤消息
- 考慮使用 last token 作為回退
- 記錄超時以進行容量規劃

### 速率限制

```python
class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.rpm = requests_per_minute
        self.window = 60.0  # 秒
        self.requests = deque()
    
    async def acquire(self):
        now = time.time()
        
        # 清理過期請求
        while self.requests and self.requests[0] < now - self.window:
            self.requests.popleft()
        
        if len(self.requests) >= self.rpm:
            sleep_time = self.window - (now - self.requests[0])
            await asyncio.sleep(sleep_time)
        
        self.requests.append(time.time())
```

### 監視和指標

關鍵指標：
- TTFT 和 TPS（延遲）
- 請求錯誤率
- GPU 利用率
- 批次大小分佈
- 佇列深度

建議：
- 使用結構化日誌記錄所有請求
- 追蹤 P50、P95、P99 延遲
- 為異常模式設置警報
- 持續監控成本

---

## 面試問題

### Q：解釋預填充和解碼之間的區別。

**強而有力的回答：**
預填充和 解碼是 LLM 推論的兩個不同階段：

**預填充** 處理整個輸入提示並計算首個 logits。這是高度平行化的——提示中的所有 token 同時處理。時間取決於提示長度，是 O(n)。

**解碼** 一次生成一個輸出 token。每個 token 的生成需要載入 KV 快取並執行注意力操作。這是記憶體受限的且依序執行。

從服務角度來看，預填充延遲（TTFT）主要受 GPU 計算能力影響，而解碼延遲（TPS）主要受 GPU 記憶體頻寬影響。這就是為什麼它們需要分開優化。

### Q：什麼是 KV 快取，它如何影響服務？

**強而有力的回答：**
KV 快取儲存 Transformer 注意力層中鍵和值張量的計算結果。在自迴歸生成期間，每個新 token 需要 attending 到所有先前位置。

沒有 KV 快取，每個新 token 都需要重新計算所有先前位置的 K 和 V，這是 O(n²) 在序列長度上的重複計算。KV 快取通過儲存這些值來避免這種重複，使每個新 token 的計算變為 O(1)。

代價是記憶體。KV 快取隨序列長度線性增長，對於 Llama 70B 在 8K 上下文可達每請求 21 GB。這直接限制了批次大小和並發請求數量。

GQA 和 MQA 等技術通過跨查詢頭共享 K 和 V 來減少這個記憶體開銷。

### Q：推測解碼如何工作？

**強而有力的回答：**
推測解碼使用一個小型「草稿模型」來猜測多個未來 token，然後由大型「目標模型」並行驗證。

工作原理：
1. 草稿模型（前向傳遞）提出多個候選 token
2. 目標模型（前向傳遞）並行驗證所有候選
3. 如果目標同意草稿的 token，它們被接受
4. 如果目標拒絕一個 token，則從該點開始使用目標的預測

好處是：如果目標同意大部分草稿（例如 4/5 個 token），我們用一次大模型前向傳遞生成了多個 token。這可以實現 2-3 倍的加速。

### Q：如何估計 LLM 服務的硬體需求？

**強而有力的回答：**
估計硬體需求時需要考慮：

1. **模型權重記憶體**：這是基本需求。70B 模型在 FP16 需要 140 GB，在 INT4 需要 35 GB。

2. **KV 快取記憶體**：這取決於並發請求數和上下文長度。每 token 約 2.6 MB，8K 上下文每請求 21 GB。

3. **激活記憶體**：前向傳遞期間的中間結果。通常較小（幾 GB）但不可忽視。

4. **批次大小**：在記憶體固定的情况下，更大的批次意味著更低的延遲但需要更多記憶體。

實用計算：
```
總記憶體需求 ≈ 模型權重 + (KV快取 × 批次大小 × 並發請求) + 激活
```

對於 Llama 70B INT4 服務 4 個並發 8K 上下文請求：
35 GB（權重）+ 84 GB（KV快取）+ 5 GB（激活）≈ 124 GB，需要 2x H100 80GB GPU。

---

## 參考文獻

- Hugging Face Generation Documentation
- vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention
- Continuous Batching and Prefix Caching in Production LLM Serving

---

*上一章：[嵌入和向量空間](05-embeddings-and-vector-spaces.md)*
