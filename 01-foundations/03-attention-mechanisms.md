# 注意力機制

注意力是使 Transformer 成為可能的核心創新。本章涵蓋對系統設計和面試至關重要的數學基礎、變體和優化。

## 目錄

- [注意力基礎](#attention-fundamentals)
- [縮放點積注意力](#scaled-dot-product-attention)
- [多頭注意力](#multi-head-attention)
- [注意力模式](#attention-patterns)
- [高效注意力變體](#efficient-attention-variants)
- [閃電注意力（v2 和 v3）](#flash-attention-v2--v3)
- [多頭潛在注意力（MLA）](#multi-head-latent-attention-mla)
- [KV 快取優化與上下文快取](#kv-cache-optimizations--context-caching)
- [實際影響](#practical-implications)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 注意力基礎

### 核心概念

注意力允許序列中的每個位置從所有其他位置收集資訊。與遞迴（逐步傳遞資訊）不同，注意力創建直接連接。

**給分散式系統工程師的心理模型：**
- RNN：沿鏈進行的消息傳遞
- 注意力：發布/訂閱，每個節點可以查詢所有其他節點

### 查詢、鍵、值框架

注意力使用輸入的三個投影：

| 組成部分 | 角色 | 类比 |
|-----------|------|---------|
| 查詢（Q） | 我在尋找什麼？ | 搜尋查詢 |
| 鍵（K） | 我包含什麼？ | 文件索引 |
| 值（V） | 我貢獻什麼？ | 文件內容 |

```python
# 輸入：x of shape [batch, seq_len, d_model]

Q = x @ W_q  # [batch, seq_len, d_k]
K = x @ W_k  # [batch, seq_len, d_k]
V = x @ W_v  # [batch, seq_len, d_v]
```

---

## 縮放點積注意力

基本注意力操作：

```python
def scaled_dot_product_attention(Q, K, V, mask=None):
    d_k = Q.shape[-1]
    
    # 計算注意力分數
    scores = Q @ K.transpose(-2, -1)  # [batch, seq_len, seq_len]
    scores = scores / math.sqrt(d_k)  # 縮放
    
    # 應用遮罩（用於因果注意力）
    if mask is not None:
        scores = scores.masked_fill(mask == 0, float('-inf'))
    
    # 轉換為機率
    attention_weights = F.softmax(scores, dim=-1)
    
    # 值的加權和
    output = attention_weights @ V
    
    return output, attention_weights
```

### 為什麼要按 d_k 的平方根縮放？

**面試最愛**：這個問題測試數值直覺。

如果不縮放，點積會隨維度增大：
- 對於維度 d 的隨機單位向量 q 和 k
- E[q . k] = 0，但 Var[q . k] = d
- 標準差 = sqrt(d)

當 d 很大（512 或更大）時，點積可能非常大或非常小。對大值進行的 Softmax 趨近 one-hot，導致梯度消失。

```python
# 示範
import numpy as np

d = 512
q = np.random.randn(d)
k = np.random.randn(d)

unscaled = np.dot(q, k)      # 大小 ~ sqrt(512) ~ 22
scaled = unscaled / np.sqrt(d)  # 大小 ~ 1
```

### 因果遮罩

對於自迴歸生成，每個位置只能關注前面的位置：

```python
def create_causal_mask(seq_len):
    # 下三角形矩陣
    mask = torch.tril(torch.ones(seq_len, seq_len))
    return mask

# seq_len=4 的範例：
# [[1, 0, 0, 0],
#  [1, 1, 0, 0],
#  [1, 1, 1, 0],
#  [1, 1, 1, 1]]
```

遮罩為 0 的位置得到負無窮的分數，在 softmax 後變為 0。

---

## 多頭注意力

不是一個注意力函數，而是使用多個「頭」關注不同方面：

```python
class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, num_heads):
        super().__init__()
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.W_o = nn.Linear(d_model, d_model)
    
    def forward(self, x, mask=None):
        batch_size, seq_len, d_model = x.shape
        
        # 投影到 Q、K、V
        Q = self.W_q(x)  # [batch, seq_len, d_model]
        K = self.W_k(x)
        V = self.W_v(x)
        
        # 重塑為多個頭
        Q = Q.view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        K = K.view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        V = V.view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        # 現在：[batch, num_heads, seq_len, d_k]
        
        # 每個頭的注意力
        attn_output, _ = scaled_dot_product_attention(Q, K, V, mask)
        
        # 串接頭
        attn_output = attn_output.transpose(1, 2).contiguous()
        attn_output = attn_output.view(batch_size, seq_len, d_model)
        
        # 最終投影
        output = self.W_o(attn_output)
        return output
```

**為什麼多個頭？**
1. 不同的頭學習不同的模式（語法、語義、共指）
2. 提供表示多樣性（集成效果）
3. 支援跨頭的平行計算

### 頭數模式

| 模型 | d_model | 頭數 | 每頭 d_k |
|-------|---------|-------|--------------|
| BERT-base | 768 | 12 | 64 |
| GPT-2 | 768 | 12 | 64 |
| GPT-3 175B | 12288 | 96 | 128 |
| Llama 2 70B | 8192 | 64 | 128 |

d_k 為 64 或 128 在各種模型大小中非常一致。

---

## 注意力模式

### 注意力學到了什麼

不同的頭專門處理不同的模式：

| 模式類型 | 捕捉內容 | 範例 |
|--------------|------------------|---------|
| 位置性 | 相鄰 token | 下一個/上一個單詞 |
| 語法性 | 語法關係 | 主詞-動詞 |
| 語義性 | 意義關係 | 共指 |
| 分隔符 | 標點符號、結構 | 區段邊界 |
| 罕見性 | 不常見的模式 | 罕見單詞複製 |

### 視覺化注意力

注意力權重可以視覺化為熱圖，顯示哪些位置關注哪些位置：

```
查詢位置（行）vs 鍵位置（列）

"The cat sat on the mat"

         The  cat  sat  on   the  mat
The     [□    ○    ○    ○    ○    ○ ]
cat     [●    □    ○    ○    ○    ○ ]
sat     [○    ●    □    ○    ○    ○ ]
on      [○    ○    ●    □    ○    ○ ]
the     [○    ○    ○    ○    □    ○ ]
mat     [○    ●    ○    ●    ●    □ ]

● = 高注意力，○ = 低注意力
```

"mat" 強烈關注 "cat"（語義）、"on"（語法）和 "the"（限定詞）。

---

## 高效注意力變體

標準注意力的序列長度複雜度為 O(n²)。許多變體降低了這個複雜度：

### 稀疏注意力

只關注位置的子集而非全部：

| 變體 | 模式 | 複雜度 | 範例 |
|---------|---------|------------|---------|
| 局部 | 每個位置周圍的視窗 | O(n * w) | Longformer |
| 跨越式 | 每 k 個位置 | O(n²/k) | Sparse Transformer |
| 全域 | 特殊 token 關注所有地方 | O(n * g) | Longformer、BigBird |
| 區塊 | 區塊對角注意力 | O(n * b) | BigBird |

**Longformer 模式：**
```
局部視窗 + 全域 token

[G] [L] [L] [L] [L] [G] [L] [L] [L] [L]

G：全域 token（關注所有/被所有關注）
L：局部 token（在視窗內關注）
```

### 線性注意力

用可線性化的替代方案替換 softmax：

```python
# 標準注意力（二次）
attention = softmax(Q @ K.T) @ V

# 線性注意力近似
attention = (Q @ (K.T @ V))  # 結合性技巧
```

**變體：**
- Performer：隨機特徵近似
- Linear Transformer：elu(Q) @ (elu(K).T @ V)

**權衡：** 更快但質量下降，特別是對於需要精確注意力的任務。

### 複雜度比較

| 方法 | 時間 | 空間 | 質量 | 備註 |
|--------|------|-------|---------|-------|
| 標準 | O(n²) | O(n²) | 最佳 | 基線 |
| 稀疏（Longformer） | O(n) | O(n) | 接近最佳 | 適用於長文檔 |
| 線性（Performer） | O(n) | O(n) | 下降 | 最適合很長的 |
| 閃電注意力 | O(n²) | O(n) | 最佳 | 兩全其美 |

---

## 閃電注意力

閃電注意力是最先進的實現，在計算精確注意力的同時實現 O(n) 記憶體。

### 它解決的問題

標準注意力需要實現 n x n 注意力矩陣：
- 對於 8K 上下文：每層每頭 64M 浮點數 = 256 MB
- 對於 100K 上下文：每層每頭 100 億浮點數 = 40 GB

這個記憶體需求限制了批次大小和上下文長度。

### 它如何工作

閃電注意力使用平鋪和重計算來避免儲存完整注意力矩陣：

```
標準：Q、K -> 注意力矩陣（n x n）-> 輸出
閃電：Q、K -> 區塊（block_size x block_size）-> 增量輸出
```

**關鍵思想：**
1. 處理適合 SRAM 的區塊中的注意力
2. 不要在 HBM 中實現完整注意力矩陣
3. 在反向傳遞期間重計算注意力（比從 HBM 載入更快）

### 性能影響

### FlashAttention-2（工作分區）
通過改進跨頭和序列長度的平行化進行 A100/H100 優化。

### FlashAttention-3（FP8 和 H100 優化）
**H100/B200 叢集的當前標準：**
- **非同步執行**：使用 H100 上的 TMA（張量記憶體加速器）重疊 GEMM（矩陣乘法）和 softmax 操作。
- **FP8 支持**：原生支持 FP8 精度，通過隨機捨入在保持注意力精度的同時將吞吐量提高一倍。
- **加速**：比 FlashAttention-2 長上下文預填充快約 1.5-2.0 倍。

---

## 多頭潛在注意力（MLA）

由 DeepSeek（V2/V3）引入，**MLA 是 GQA 應對極致 KV 快取壓力的現代替代方案**。

不僅僅是分組頭，MLA 將鍵和值向量壓縮到**低維潛在空間**，然後再儲存到快取中。

```
查詢（向上投影）───────┐
                       ▼
鍵、值（向下投影）──▶ [低維潛在快取] ─▶ [輸出]
                       ▲
                       └── 投影矩陣
```

| 指標 | MHA | GQA | MLA（2025 年 12 月） |
|--------|-----|-----|----------------|
| KV 快取大小 | 100% | 12.5% | **~5%** |
| 質量 | 基線 | 接近基線 | **優於 GQA** |
| 延遲 | 基線 | 更快 | **最快（減少 I/O）** |

**為什麼 MLA 獲勝**：它使用「解耦旋轉位置嵌入」，允許壓縮的潛在 KV 被重複使用而無需解碼，在長上下文生成期間節省大量記憶體頻寬。

---

## KV 快取優化與上下文快取

### 上下文快取（系統級）
API 提供者（OpenAI、Gemini、Anthropic）現在提供**上下文快取**。
- **如何工作**：預先計算並儲存長「前綴」（例如 10 萬 token 法律書籍）的 KV 張量。
- **優勢**：將 TTFT（首個 Token 的時間）減少 90%，重複前綴的成本降低 50-90%。

### 滑動視窗注意力（SWA）
用於 Mistral/Gemma 模型，將注意力深度限制在固定視窗（例如 4096 個 token），防止 KV 快取無限增長。

### 多查詢注意力（MQA）

在所有查詢頭之間共享單一的 K 和 V：

```python
# 標準 MHA
Q: [batch, num_heads, seq, d_k]  # 32 個頭
K: [batch, num_heads, seq, d_k]  # 32 個單獨的 K
V: [batch, num_heads, seq, d_k]  # 32 個單獨的 V

# MQA
Q: [batch, num_heads, seq, d_k]  # 32 個頭
K: [batch, 1, seq, d_k]          # 1 個共享的 K
V: [batch, 1, seq, d_k]          # 1 個共享的 V
```

**效果：** KV 快取大小減少 32 倍，有些許質量損失。

### 分組查詢注意力（GQA）

在查詢頭組之間共享 K 和 V：

```python
# GQA，8 個 KV 頭用於 64 個查詢頭（8:1 比例）
Q: [batch, 64, seq, d_k]  # 64 個查詢頭
K: [batch, 8, seq, d_k]   # 8 個 KV 頭
V: [batch, 8, seq, d_k]   # 8 個 KV 頭

# 每個 KV 頭服務 8 個查詢頭
```

**效果：** 以最小的質量損失減少 8 倍 KV 快取。

**使用 GQA 的模型：**
- Llama 2 70B：64 個查詢頭的 8 個 KV 頭
- Mistral 7B：32 個查詢頭的 8 個 KV 頭
- Gemma：各種配置

### 比較

| 注意力 | KV 快取 | 質量 | 模型 |
|-----------|----------|---------|--------|
| MHA | 完整 | 最佳 | GPT-3 |
| GQA | 1/8 典型 | 接近最佳 | Llama 2、Mistral |
| MQA | 1/n_heads | 下降 | PaLM、Falcon |

---

## 實際影響

### 對系統設計而言

1. **批次大小與上下文權衡：**
   - 總 GPU 記憶體 = 模型 + KV 快取 * 批次大小
   - 更長的上下文意味著更小的批次
   - GQA 模型可以服務更多並發請求

2. **延遲預算分配：**
   - 注意力是 O(n²) 計算，Flash 是 O(n)
   - 預填充（處理提示）隨提示長度擴展
   - 解碼（生成）隨生成 + 提示長度擴展

3. **記憶體頻寬瓶頸：**
   - 生成通常是記憶體受限
   - 每個 token 載入 KV 快取佔主導
   - 更大的批次攤銷這個成本

### 預填充與解碼

| 階段 | 計算模式 | 瓶頸 |
|-------|-----------------|------------|
| 預填充 | 處理所有輸入 token | 計算（GPU 核心） |
| 解碼 | 一次生成一個 token | 記憶體（頻寬） |

這就是為什麼 TTFT（首個 Token 的時間）和 TPS（每秒 Token 數）分開測量的原因。

### 上下文長度擴展

| 上下文 | 注意力計算 | KV 快取（Llama 70B） |
|---------|-------------------|---------------------|
| 4K | 基線 | 10.7 GB |
| 8K | 4x | 21.5 GB |
| 32K | 64x | 86 GB |
| 128K | 1024x | 344 GB |

長上下文需要：
- 閃電注意力（記憶體高效）
- GQA 或 MQA（更小的 KV 快取）
- 可能需要模型平行化

---

## 面試問題

### Q：解釋注意力機制以及為什麼它是二次方複雜度。

**強而有力的回答：**
注意力計算所有位置之間的成對交互。對於 n 個位置：

1. Q @ K^T 產生 n x n 分數矩陣
2. 每個注意力分數是查詢和鍵的點積
3. 總計：n² 個點積

這對序列長度是二次方的。對於 8K token，那是每層每頭 6400 萬個成對分數。對於 128K token，那是 160 億個。

二次方縮放限制了上下文長度。解決方案包括：
- 閃電注意力：O(n²) 計算但 O(n) 記憶體
- 稀疏注意力：通過關注子集實現 O(n)
- 線性注意力：O(n) 近似

### Q：什麼是 KV 快取，為什麼它對服務至關重要？

**強而有力的回答：**
在自迴歸生成期間，我們一次生成一個 token。如果不緩存，每個新 token 都需要重新計算所有先前位置的 K 和 V。

KV 快取儲存先前位置的 K 和 V 張量。每個新 token：
1. 只計算新位置的 Q、K、V
2. 將新 K、V 附加到快取
3. 關注完整快取的 K、V

這將每個 token 的複雜度從 O(n) 降至 O(1) 用於投影計算。

代價是記憶體：KV 快取隨序列長度線性擴展。對於 8K 上下文的 Llama 70B，那是每請求約 21 GB。這直接限制了批次大小和吞吐量。

GQA 和 MQA 通過跨查詢頭共享 K、V 來減少這個問題。

### Q：比較 MHA、GQA 和 MQA。

**強而有力的回答：**

| 變體 | K,V 頭數 | KV 快取 | 質量 | 用例 |
|---------|-----------|----------|---------|----------|
| MHA | 等於 Q 頭數 | 完整 | 最佳 | 訓練、品質關鍵 |
| GQA | 少於 Q 頭數 | 減少 | 接近 MHA | 生產服務 |
| MQA | 1 | 最小 | 下降 | 記憶體受限 |

MHA：每個查詢頭有自己的 K 和 V。最高質量但最大的 KV 快取。

GQA：查詢頭組共享 K 和 V。Llama 2 使用 64 個查詢頭的 8 個 KV 頭（8:1 比例）。8 倍更小的快取，最小質量損失。

MQA：所有查詢頭共享一個 K 和 V。最大的記憶體節省，但可測量的質量下降。由 PaLM 使用。

對於服務，GQA 是最好的權衡。它支援更大的批次大小（更高吞吐量），質量幾乎與 MHA 相同。

### Q：閃電注意力如何實現 O(n) 記憶體？

**強而有力的回答：**
標準注意力在 GPU 記憶體中實現完整的 n x n 注意力矩陣。閃電注意力通過以下方式避免這個問題：

1. **平鋪：** 處理適合晶片上 SRAM 的 Q 和 K 區塊
2. **線上 softmax：** 增量計算 softmax，無需儲存所有分數
3. **重計算：** 在反向傳遞期間重新計算注意力，而不是載入保存的值

關鍵洞察是 GPU SRAM（每 SM 20 MB）比 HBM（80 GB）快 10 倍。通過在 SRAM 中做更多算術運算和更少的 HBM 讀取/寫入，閃電注意力既更快又使用更少記憶體。

結果是精確注意力（不是近似），具有 O(n) 記憶體和 2-4 倍加速。

---

## 參考文獻

- Vaswani et al. "Attention Is All You Need" (2017)
- Dao et al. "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness" (2022)
- Dao et al. "FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning" (2023)
- Shah et al. "FlashAttention-3: Fast and Accurate Attention with FP8 and H100" (2024)
- DeepSeek-V2 Technical Report (2024)

---

*上一章：[分詞深入探討](02-tokenization-deep-dive.md) | 下一章：[Transformer 架構](04-transformer-architecture.md)*
