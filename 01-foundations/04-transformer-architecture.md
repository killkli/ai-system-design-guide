# Transformer 架構

本章提供完整 Transformer 架構的全面視圖，將前幾章的組成部分整合為統一的理解。

## 目錄

- [架構概觀](#architecture-overview)
- [輸入處理](#input-processing)
- [Transformer 區塊](#the-transformer-block)
- [輸出處理](#output-processing)
- [現代架構變體（混合 MoE、MLA）](#mixture-of-experts-moe--hybrid-architectures)
- [綁定與非綁定嵌入](#untied-vs-tied-embeddings)
- [縮放特性](#scaling-properties)
- [架構比較表](#architecture-comparison-table)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 架構概觀

僅解碼器 Transformer（GPT、Claude、Llama 使用的架構）由以下組成：

```
┌─────────────────────────────────────────────────────────────────┐
│                     Token 嵌入                                   │
│              + 位置嵌入（或 RoPE）                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│    ┌─────────────────────────────────────────────────────┐      │
│    │                  Transformer 區塊                     │      │
│    │  ┌─────────────────────────────────────────────┐    │      │
│    │  │              RMSNorm/LayerNorm               │    │      │
│    │  └───────────────────┬─────────────────────────┘    │      │
│    │                      ▼                              │      │
│    │  ┌─────────────────────────────────────────────┐    │      │
│    │  │         遮罩多頭注意力                        │    │      │
│    │  │            （帶 KV 快取）                     │    │      │
│    │  └───────────────────┬─────────────────────────┘    │      │
│    │                      │                              │      │
│    │                  + 殘差連接                          │      │
│    │                      │                              │      │
│    │  ┌─────────────────────────────────────────────┐    │      │
│    │  │              RMSNorm/LayerNorm               │    │      │
│    │  └───────────────────┬─────────────────────────┘    │      │
│    │                      ▼                              │      │
│    │  ┌─────────────────────────────────────────────┐    │      │
│    │  │             前饋網路                          │    │      │
│    │  │               （SwiGLU/GELU）               │    │      │
│    │  └───────────────────┬─────────────────────────┘    │      │
│    │                      │                              │      │
│    │                  + 殘差連接                          │      │
│    └──────────────────────┴──────────────────────────────┘      │
│                           │                                     │
│                    重複 × N 層                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      輸出 RMSNorm                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   語言模型頭                                    │
│              （線性：hidden_dim → vocab_size）                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
                         Logits
```

---

## 輸入處理

### Token 嵌入

將 token ID 轉換為密集向量：

```python
class TokenEmbedding(nn.Module):
    def __init__(self, vocab_size, d_model):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
    
    def forward(self, token_ids):
        return self.embedding(token_ids)
```

**維度：**
- 輸入：[batch_size, seq_len] token ID
- 輸出：[batch_size, seq_len, d_model] 嵌入

### 位置資訊

位置通過以下方式之一整合：

**1. 旋轉位置嵌入（RoPE）：**
在注意力內應用，不添加到嵌入：
```python
def apply_rope(q, k, positions):
    # 根據位置旋轉 q 和 k 向量
    freqs = compute_frequencies(positions)
    q_rotated = rotate_embeddings(q, freqs)
    k_rotated = rotate_embeddings(k, freqs)
    return q_rotated, k_rotated
```

**2. 學習的位置嵌入：**
直接添加到 token 嵌入：
```python
position_embeddings = nn.Embedding(max_seq_len, d_model)
x = token_embeddings + position_embeddings(positions)
```

**現代模型（Llama、Mistral、GPT-4）使用 RoPE** 以獲得更好的長度泛化。

---

## Transformer 區塊

### Pre-Norm 結構

現代 Transformer 使用預正規化：

```python
class TransformerBlock(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.attn_norm = RMSNorm(config.d_model)
        self.attn = GroupedQueryAttention(
            d_model=config.d_model,
            n_heads=config.n_heads,
            n_kv_heads=config.n_kv_heads
        )
        self.ff_norm = RMSNorm(config.d_model)
        self.ff = SwiGLUFFN(
            d_model=config.d_model,
            d_ff=config.d_ff
        )
    
    def forward(self, x, mask=None, kv_cache=None):
        # 帶殘差的注意力
        h = x + self.attn(self.attn_norm(x), mask, kv_cache)
        
        # 帶殘差的 FFN
        out = h + self.ff(self.ff_norm(h))
        
        return out
```

### 注意力元件

```python
class GroupedQueryAttention(nn.Module):
    def __init__(self, d_model, n_heads, n_kv_heads):
        super().__init__()
        self.n_heads = n_heads
        self.n_kv_heads = n_kv_heads
        self.head_dim = d_model // n_heads
        
        self.q_proj = nn.Linear(d_model, n_heads * self.head_dim)
        self.k_proj = nn.Linear(d_model, n_kv_heads * self.head_dim)
        self.v_proj = nn.Linear(d_model, n_kv_heads * self.head_dim)
        self.o_proj = nn.Linear(n_heads * self.head_dim, d_model)
    
    def forward(self, x, mask, kv_cache):
        B, T, D = x.shape
        
        # 投影
        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim)
        k = self.k_proj(x).view(B, T, self.n_kv_heads, self.head_dim)
        v = self.v_proj(x).view(B, T, self.n_kv_heads, self.head_dim)
        
        # 應用 RoPE
        q, k = apply_rope(q, k, positions)
        
        # 更新 KV 快取
        if kv_cache is not None:
            k = torch.cat([kv_cache.k, k], dim=1)
            v = torch.cat([kv_cache.v, v], dim=1)
            kv_cache.update(k, v)
        
        # 重複 KV 頭以實現 GQA
        k = k.repeat_interleave(self.n_heads // self.n_kv_heads, dim=2)
        v = v.repeat_interleave(self.n_heads // self.n_kv_heads, dim=2)
        
        # 注意力（實際使用 Flash Attention）
        attn_out = flash_attention(q, k, v, mask)
        
        # 輸出投影
        out = self.o_proj(attn_out.view(B, T, -1))
        return out
```

### 前饋網路

```python
class SwiGLUFFN(nn.Module):
    def __init__(self, d_model, d_ff):
        super().__init__()
        # SwiGLU 有 3 個投影而非 2 個
        self.gate_proj = nn.Linear(d_model, d_ff, bias=False)
        self.up_proj = nn.Linear(d_model, d_ff, bias=False)
        self.down_proj = nn.Linear(d_ff, d_model, bias=False)
    
    def forward(self, x):
        gate = F.silu(self.gate_proj(x))  # SiLU = Swish
        up = self.up_proj(x)
        return self.down_proj(gate * up)
```

**FFN 隱藏維度** 對於 SwiGLU 通常是模型維度的 2.7 倍（標準 FFN 與 GELU 為 4 倍）。

### RMSNorm

```python
class RMSNorm(nn.Module):
    def __init__(self, d_model, eps=1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(d_model))
        self.eps = eps
    
    def forward(self, x):
        rms = torch.sqrt(torch.mean(x ** 2, dim=-1, keepdim=True) + self.eps)
        return self.weight * (x / rms)
```

比 LayerNorm 更簡單更快，因為跳過了均值中心化。

---

## 輸出處理

### 最終正規化

在最後一個 Transformer 區塊後應用 RMSNorm：

```python
hidden_states = self.output_norm(hidden_states)
```

### 語言模型頭

投影到詞彙表大小：

```python
class LMHead(nn.Module):
    def __init__(self, d_model, vocab_size):
        super().__init__()
        self.linear = nn.Linear(d_model, vocab_size, bias=False)
    
    def forward(self, x):
        return self.linear(x)  # 返回 logits
```

## 綁定與非綁定嵌入

**標準模式（GPT-3、Llama 2）：** 權重綁定
- 輸出頭與輸入嵌入共享權重。
- **優點**：節省記憶體（vocab_size * hidden_dim）。
- **缺點**：強迫輸入和輸出潛在空間相同，這可能不是最優的。

**2025 年前沿模式（Llama 3/4、GPT-5.2）：** 非綁定嵌入
- 輸出頭有自己的權重。
- **為什麼？**：更大的詞彙表（128k+）使嵌入表成為模型的重要組成部分。非綁定允許輸出頭專注於「預測邏輯」，而輸入嵌入專注於「語義理解」。
- **系統影響**：增加參數數量，但通常會提高多語言和程式碼任務的困惑度。

### 獲取預測

```python
# 生成期間
logits = lm_head(hidden_states[:, -1, :])  # 僅最後位置
next_token = sample(logits)

# 訓練期間
logits = lm_head(hidden_states)  # 所有位置
loss = cross_entropy(logits, targets)
```

---

## 現代架構變體

### Llama 2/3 架構

| 元件 | 實現 |
|-----------|----------------|
| 注意力 | 分組查詢注意力（GQA） |
| 位置 | 旋轉位置嵌入（RoPE） |
| 正規化 | RMSNorm（pre-norm） |
| 啟動 | SwiGLU |
| 偏置 | 線性層無偏置 |

### Mistral 架構

與 Llama 相同但添加了：
- **滑動視窗注意力：** 每層只關注 4K token
- 仍然通過堆疊實現有效的 32K+ 上下文

### 混合專家（MoE）和混合架構

最先進的模型通常使用**混合 MoE/密集**區塊：
- **週期性密集層：** 每隔幾個 MoE 層添加一個密集層，以確保「全局」知識在所有專家之間共享。
- **專家平行性：** 將不同的專家分發到不同的 GPU。這使得**節點間頻寬**（NVLink/InfiniBand）成為主要架構瓶頸。

<<<<<<< Updated upstream
### Multi-head Latent Attention (MLA) Integration
The standard attention block in [DeepSeek-V3 / V4](03-attention-mechanisms.md#multi-head-latent-attention-mla) and equivalent modern architectures replaces the standard Q/K/V projections with low-rank latent compressions.
- **Architectural Shift**: The "KV Cache" is now a compressed latent representation, changing the memory/compute ratio of the entire transformer block.
=======
### 多頭潛在注意力（MLA）整合
標準注意力區塊在 [DeepSeek-V3 / V4](file:///Users/om/play/ai-system-design-guide/01-foundations/03-attention-mechanisms.md#multi-head-latent-attention-mla) 及等效現代架構中，用低秩潛在壓縮替換了標準 Q/K/V 投影。
- **架構轉變**：「KV 快取」現在是一個壓縮的潛在表示，改變了整個 Transformer 區塊的記憶體/計算比率。
>>>>>>> Stashed changes

### 選擇比較

| 選擇 | 舊方法 | 現代方法 | 優勢 |
|--------|--------------|-----------------|---------|
| 正規化 | Post-LN | Pre-LN / RMSNorm | 訓練穩定性、速度 |
| 位置 | 正弦/學習的 | RoPE | 更好的泛化 |
| 啟動 | GELU | SwiGLU | 質量（基準測試 +1%） |
| 注意力 | MHA | GQA | 8 倍更小的 KV 快取 |
| 偏置 | 有偏置 | 無偏置 | 更少參數，相似質量 |

---

## 縮放特性

### 參數數量

| 元件 | 參數 |
|-----------|------------|
| Token 嵌入 | vocab_size * d_model |
| 每層 Q/K/V | 3 * d_model * d_model（MHA） |
| 每層 O 投影 | d_model * d_model |
| 每層 FFN | 3 * d_model * d_ff（SwiGLU） |
| LM 頭 | d_model * vocab_size（通常綁定） |

**僅解碼器的近似：**
```
總計 ≈ 12 * n_layers * d_model^2（對於 d_ff = 4 * d_model，MHA）
```

### 計算需求

**訓練：** 每 token FLOPs ≈ 6 * 參數（正向 + 反向）

**推論：** 每 token FLOPs ≈ 2 * 參數（僅正向）

### 縮放定律

Chinchilla 縮放定律建議最佳分配：

```
D（資料 token）≈ 20 * N（參數）
```

對於 70B 模型，在約 1.4T token 上訓練以達到計算最優訓練。

**但是：** 許多現代模型相對於 Chinchilla 進行過度訓練以獲得更好的推論效率。Llama 在 2T+ token 上訓練。

---

## 架構比較表

| 模型 | 參數 | 層數 | d_model | 頭數 | KV 頭 | FFN | 上下文 |
|-------|--------|--------|---------|-------|----------|-----|---------|
| GPT-3 | 175B | 96 | 12288 | 96 | 96 | GELU | 2K |
| Llama 2 70B | 70B | 80 | 8192 | 64 | 8 | SwiGLU | 4K |
| Llama 3 405B| 405B | 126 | 16384 | 128 | 16 | SwiGLU | 128K |
| DeepSeek V3 | 671B | 128 | 7168 | 128 | MLA | MoE | 128K |
| Llama 4（規格）| 1T+ | 140+ | 18432 | 192 | 24 | MoE/H | 1M+ |

*Mistral 使用滑動視窗注意力以實現有效的長上下文。

---

## 面試問題

### Q：帶我走過 Transformer 的前向傳遞。

**強而有力的回答：**
對於生成文字的僅解碼器模型：

1. **分詞：** 將輸入文字轉換為 token ID

2. **嵌入：** 從嵌入表中查詢 token 嵌入

3. **對於每個 Transformer 層：**
   - 對輸入應用 RMSNorm
   - 計算 Q、K、V 投影
   - 對 Q 和 K 應用 RoPE 以獲取位置
   - 對於生成：將新的 K、V 附加到 KV 快取
   - 計算注意力（遮罩的，所以每個位置只看到前面的）
   - 投影注意力輸出並添加殘差
   - 應用 RMSNorm
   - 通過 SwiGLU 前饋網路傳遞
   - 添加殘差

4. **輸出正規化：** 應用最終 RMSNorm

5. **LM 頭：** 投影到詞彙表大小以獲取 logits

6. **採樣：** 使用 temperature/top-p 從 logits 中選擇下一個 token

對於生成，重複步驟 3-6 對每個新 token，重複使用先前位置的 KV 快取。

### Q：pre-norm 和 post-norm 有什麼區別？

**強而有力的回答：**
區別在於相對於子層（注意力、FFN）應用層正規化的位置：

**Post-norm（原始 Transformer）：**
```
x = LayerNorm(x + Sublayer(x))
```
在添加殘差後正規化。

**Pre-norm（現代 Transformer）：**
```
x = x + Sublayer(LayerNorm(x))
```
在子層之前正規化。

首選 Pre-norm 因為：
1. 梯度通過殘差連接更直接地流動
2. 訓練更穩定，特別是對於深度模型
3. 對初始化和學習率不太敏感
4. 不需要學習率預熱

代價是在某些基準測試中最終性能略低，但對於大型模型來說訓練穩定性是值得的。

### Q：解釋 GQA 及其對服務的重要性。

**強而有力的回答：**
分組查詢注意力（GQA）在查詢頭組之間共享鍵和值頭。

標準多頭注意力：64 個查詢頭，64 個 KV 頭（1:1）
GQA：64 個查詢頭，8 個 KV 頭（8:1）

實現：每個 KV 頭通過重複為 8 個查詢頭服務。

**為什麼重要：**
KV 快取在生成期間儲存所有位置的 K 和 V。對於 8K 上下文的 Llama 70B：
- MHA：每 token 2.6 MB * 8K = 每請求 21 GB
- GQA（8:1）：每請求約 2.6 GB

8 倍減少使得：
- 更大的批次大小（更多並發用戶）
- 更長的上下文
- 更低的 GPU 記憶體需求

質量影響：最小。研究表明 GQA 達到 MHA 質量的 99% 以上。

### Q：GPT-2 和 Llama 2 之間有什麼變化？

**強而有力的回答：**
關鍵架構改進：

| 元件 | GPT-2 | Llama 2 |
|-------|-------|---------|
| 正規化 | Post-LayerNorm | Pre-RMSNorm |
| 位置 | 學習的絕對位置 | RoPE（旋轉） |
| 啟動 | GELU | SwiGLU |
| 注意力 | MHA | GQA（70B） |
| 偏置 | 存在 | 移除 |

影響：
- RMSNorm：更快且同樣有效
- RoPE：更好的長度泛化
- SwiGLU：~1% 質量改進
- GQA：服務 8 倍更小的 KV 快取
- 無偏置：更少參數，無質量損失

這些改進使得訓練更大的模型更穩定，服務更高效。

---

## 參考文獻

- Vaswani et al. "Attention Is All You Need" (2017)
- Touvron et al. "Llama: Open and Efficient Foundation Language Models" (2023)
- Touvron et al. "Llama 2: Open Foundation and Fine-Tuned Chat Models" (2023)
- Zhang and Sennrich. "Root Mean Square Layer Normalization" (2019)
- Shazeer. "GLU Variants Improve Transformer" (2020)
- Su et al. "RoFormer: Enhanced Transformer with Rotary Position Embedding" (2021)
- Jiang et al. "Mistral 7B" (2023)

---

*上一章：[注意力機制](03-attention-mechanisms.md) | 下一章：[嵌入和向量空間](05-embeddings-and-vector-spaces.md)*
