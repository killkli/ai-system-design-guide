# 分詞深入探討

分詞是將文字轉換為模型可以處理的離散單元（token）的過程。它直接影響模型能力、成本和性能。

## 目錄

- [為什麼分詞很重要](#why-tokenization-matters)
- [分詞演算法](#tokenization-algorithms)
- [詞彙表設計權衡](#vocabulary-design-tradeoffs)
- [特殊 token](#special-tokens)
- [多語言分詞](#multilingual-tokenization)
- [用於成本估計的 token 計數](#token-counting-for-cost-estimation)
- [常見分詞問題](#common-tokenization-issues)
- [實用分詞模式](#practical-tokenization-patterns)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 為什麼分詞很重要

### 對系統設計而言

1. **成本**：LLM API 按 token 收費。分詞效率直接影響成本。
2. **上下文限制**：token 數量（而非單詞數量）決定了上下文容納的內容。
3. **能力**：某些任務（字元計數、字謎）因分詞而變得困難。
4. **一致性**：相同文字在不同模型中分詞方式不同。

### 對理解 LLM 行為而言

**經典面試問題**：為什麼 GPT 很難計算「strawberry」中字母的數量？

因為「strawberry」被分詞為多個子詞。模型從未看到單個字元；它看到的是子詞單元。計算字母需要推理 token 的內部結構。

---

## 分詞演算法

### 位元組對編碼（BPE）

最常見的演算法。由 GPT 系列、Llama、Claude 使用。

**訓練演算法：**
1. 從單一位元組的詞彙表開始（256 個 token）
2. 計算訓練語料庫中所有相鄰 token 配對
3. 將最常見的配對合併為一個新 token
4. 重複直到達到詞彙表大小

**範例：**
```
語料庫："low lower lowest"
初始：['l', 'o', 'w', ' ', 'l', 'o', 'w', 'e', 'r', ' ', 'l', 'o', 'w', 'e', 's', 't']

步驟 1：最常見的配對是 ('l', 'o')。合併為 'lo'。
['lo', 'w', ' ', 'lo', 'w', 'e', 'r', ' ', 'lo', 'w', 'e', 's', 't']

步驟 2：最常見的配對是 ('lo', 'w')。合併為 'low'。
['low', ' ', 'low', 'e', 'r', ' ', 'low', 'e', 's', 't']

步驟 3：最常見的配對是 ('low', 'e')。合併為 'lowe'。
['low', ' ', 'lowe', 'r', ' ', 'lowe', 's', 't']

繼續直到達到詞彙表大小目標...
```

**特性：**
- 給定訓練詞彙表，分詞是確定性的
- 常見詞傾向於是單一 token
- 罕見詞拆分為子詞

### WordPiece

由 BERT 系列模型使用。

**與 BPE 的主要區別：**
- BPE：基於頻率合併
- WordPiece：基於似然改進合併

```
Score = freq(AB) / (freq(A) * freq(B))
```

這傾向於比隨機共現更有意義的合併。

**視覺標記：** WordPiece 使用 ## 前綴表示延續 token：
```
"embedding" 變為 ["em", "##bed", "##ding"]
```

### Unigram（SentencePiece）

由 T5、ALBERT、部分多語言模型使用。

**訓練演算法：**
1. 從大型候選詞彙表開始
2. 計算移除每個 token 的損失
3. 移除增加損失最少的 token
4. 重複直到達到詞彙表大小

**主要區別：** 使用機率而非頻率工作。可以從次優的早期合併中恢復。

### 比較

| 演算法 | 合併標準 | 分詞 | 使用者 |
|-----------|-----------------|--------------|---------|
| BPE | 頻率 | 確定性 | GPT、Llama、Claude |
| WordPiece | 似然 | 確定性 | BERT、DistilBERT |
| Unigram | 機率 | 機率性 | T5、mT5、XLNet |

---

## 詞彙表設計權衡

### 詞彙表大小

| 大小 | 範例 | 優點 | 缺點 |
|------|---------|------|------|
| 小（10K） | 一些早期模型 | 更小的嵌入 | 長 token 序列 |
| 中（32K） | Llama 2 | 良好的平衡 | 多語言效率低 |
| 大（128K） | Llama 3/4、Claude Sonnet 4.6、Mistral Medium 3.5 | **當前標準。** 高壓縮率。 | 更大的嵌入表 |
| 超大（200K+） | GPT-5.5 (o200k)、Claude Opus 4.7 | 原生多模態和多語言效率 | LM Head 的記憶體壓力 |

**詞彙擴展深入探討：**
- **Llama 3/4（128k）**：通過從 32k 移到 128k，Meta 將英語壓縮率提高了約 15%，印地語等多語言提高了 3-4 倍。
- **GPT-4o/5.2（o200k_base）**：Tiktoken 的最新編碼為程式碼和多語言文字提供了卓越的壓縮率，通過使用更少的 token 表達相同含義間接降低 API 成本。

### 字元 vs 子詞 vs 單詞

| 粒度 | 範例 | "running" 的 token | 權衡 |
|-------------|---------|---------------------|-----------|
| 字元 | ByT5 | ['r','u','n','n','i','n','g'] | 處理任何文字但序列很長 |
| 子詞 | GPT | ['running'] 或 ['run','ning'] | 良好的平衡 |
| 單詞 | 早期 NLP | ['running'] | 序列短但無法處理 OOV |

現代 LLM 普遍使用子詞分詞以平衡詞彙表大小和序列長度。

### 位元組級 BPE

GPT-2 引入了位元組級 BPE：
- 基礎詞彙表是 256 個位元組，而非字元
- 無需 UNK token 即可表示任何文字
- Unicode 作為位元組序列自然處理

```python
# 字元級：需要明確處理字元
text = "cafe"  # 未知字元可能變為 [UNK]

# 位元組級：適用於任何文字（無需 UNK）
text = "cafe"  # 變為位元組，然後 BPE 在位元組上操作
```

---

## 特殊 Token

特殊 token 處理正常文字之外的結構資訊：

| Token | 用途 | 範例 |
|-------|---------|---------|
| BOS | 序列開始 | 標誌生成開始 |
| EOS | 序列結束 | 標誌完成 |
| PAD | 填充 | 將批次填充到相同長度 |
| UNK | 未知 token | OOV 的後備（使用位元組 BPE 很少見） |
| SEP | 分隔符 | 分隔區段（BERT 風格） |

### 聊天模板

現代聊天模型使用特殊 token 進行對話結構：

**Llama 2 格式：**
```
[INST] <<SYS>>
You are a helpful assistant.
<</SYS>>

User message here [/INST] Assistant response here
```

**ChatML（OpenAI 風格）：**
```
<|im_start|>system
You are a helpful assistant.<|im_end|>
<|im_start|>user
Hello!<|im_end|>
<|im_start|>assistant
Hi there!<|im_end|>
```

**為什麼這很重要：**
- 錯誤的格式會導致糟糕的結果
- 特殊 token 不在預訓練資料中
- 像 transformers 之類的函式庫使用 chat_template 進行自動格式化

---

## 多語言分詞

### 挑戰

主要在英語上訓練的分詞器對其他語言的效率較低：

| 語言 | "Hello" 的 token | 等效問候語的 token |
|----------|-------------------|-------------------------------|
| 英語 | 1 ("Hello") | - |
| 中文 | - | 等效需要 2-3+ |
| 日語 | - | 等效需要 3-5+ |
| 韓語 | - | 等效需要 2-4+ |

**成本影響：** 非英語用戶每語義單元支付 2-3 倍的費用。

### 解決方案

1. **多語言訓練語料庫：** 在平衡的多語言資料上訓練分詞器
2. **更大的詞彙表：** 為非英語 token 提供更多空間
3. **特定語言的分詞器：** 每種語言家族使用单独的分詞器

**具有良好多語言支持的模型：**
- mT5、XLM-R：在 100+ 種語言上訓練
- GPT-4、Claude 3.5：大詞彙表具有多語言覆蓋
- Gemini：從一開始就為多語言設計

| 模型 | 中文 | 日語 | 韓語 | 印地語 |
|-------|---------|----------|--------|--------|
| GPT-2 | 2.5x | 3.0x | 2.8x | 6.0x |
| GPT-4 (cl100k) | 1.4x | 1.6x | 1.5x | 3.2x |
| GPT-5.2 (o200k) | 1.1x | 1.2x | 1.1x | 1.4x |
| Llama 3/4 (128k)| 1.2x | 1.3x | 1.2x | 1.5x |

---

## 多模態分詞（像素到 token）

現代原生多模態模型不僅「看到」圖像；它們對圖像進行分詞。

### 圖像分詞（視覺 Transformer）

圖像被分割成區塊（例如 14x14 像素）。每個區塊通過視覺編碼器（如 SigLIP）產生單一視覺 token。
- **固定 Token 成本**：大多數模型在特定解析度下每張圖像使用固定數量的 token（例如每張圖像 256 或 729 個 token）。
- **動態解析度**：一些模型（Gemini 3）根據圖像縱橫比和細節級別使用可變數量的 token。

### 音訊/視訊分詞
- **音訊**：使用 EnCodec 等編解碼器壓縮為離散單元，然後表示為音訊 token 序列。
- **視訊**：作為影格序列處理（時間分詞）。1 秒視訊 @ 1FPS 的成本可能與 1 張高解析度圖像相當。

---

## 用於成本估計的 Token 計數

### 快速估計規則

對於英語文字：
- **單詞到 token：** 每單詞約 1.3 個 token
- **字元到 token：** 每 token 約 4 個字元
- **頁面到 token：** 每頁約 500-800 個 token

```python
def estimate_tokens(text: str) -> int:
    # 英語粗略估計
    word_count = len(text.split())
    return int(word_count * 1.3)
```

### 準確計數

使用特定於模型的 tokenizer：

```python
import tiktoken

# 對於 OpenAI 模型
encoding = tiktoken.encoding_for_model("gpt-4")
tokens = encoding.encode("Your text here")
token_count = len(tokens)

# 對於 Llama/Anthropic，使用 transformers
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b")
tokens = tokenizer.encode("Your text here")
token_count = len(tokens)
```

### 成本計算

```python
def calculate_cost(input_text: str, output_text: str, model: str) -> float:
    pricing = {
        "gpt-4o": {"input": 2.50, "output": 10.00},  # 每 1M token
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    }
    
    encoding = tiktoken.encoding_for_model(model)
    input_tokens = len(encoding.encode(input_text))
    output_tokens = len(encoding.encode(output_text))
    
    cost = (
        (input_tokens / 1_000_000) * pricing[model]["input"] +
        (output_tokens / 1_000_000) * pricing[model]["output"]
    )
    return cost
```

---

## 常見分詞問題

### 問題 1：Token 邊界對齊不當

**問題：** 文字操作可能與 token 邊界不一致。

```python
text = "Hello world"
# Token：["Hello", " world"]  # 注意：空格是第二個 token 的一部分

# 在字元 6（"Hello "）處截斷會分割一個 token
```

**解決方案：** 管理上下文時始終在 token 邊界處截斷。

### 問題 2：分詞不一致

**問題：** 相同文字根據上下文分詞方式不同。

```python
# GPT tokenizer 範例
"New York"     # 可能為 ["New", " York"]
"NewYork"      # 可能為 ["New", "York"]
" New York"    # 可能為 [" New", " York"]
```

**影響：** Token 數量可能根據周圍文字而變化。始終對完整上下文進行分詞。

### 問題 3：程式碼和結構化資料

**問題：** 程式碼和 JSON 通常分詞效率低。

```python
# Python 程式碼通常分詞效果不佳
"def calculate_average(numbers):"
# 變為多個 token：["def", " calculate", "_", "average", "(", "numbers", "):", ...]

# JSON 鍵單獨分詞
'{"firstName": "John"}'
# 結構需要許多 token
```

**緩解：**
- 有些模型有針對程式碼優化的分詞器
- 考慮在發送前壓縮 JSON
- 可用時使用結構化輸出模式

### 問題 4：空白處理

**問題：** 分詞器處理空白的方式不同。

```python
# 前導空格通常變為單獨的 token
" Hello"  # [" ", "Hello"] 或 [" Hello"]

# 多個空格可能合併或保持分開
"Hello  world"  # 行為因分詞器而異
```

**最佳實踐：** 分詞前標準化空白。

---

## 實用分詞模式

### 模式 1：上下文視窗管理

```python
def fit_to_context(
    system_prompt: str,
    user_message: str,
    history: list[str],
    max_tokens: int = 8000,
    reserve_for_output: int = 2000
) -> str:
    encoding = tiktoken.encoding_for_model("gpt-4")
    
    available = max_tokens - reserve_for_output
    
    # 系統提示始終包含
    tokens_used = len(encoding.encode(system_prompt))
    available -= tokens_used
    
    # 用戶消息始終包含
    tokens_used = len(encoding.encode(user_message))
    available -= tokens_used
    
    # 從最新的開始添加歷史，必要時刪除最舊的
    included_history = []
    for msg in reversed(history):
        msg_tokens = len(encoding.encode(msg))
        if msg_tokens <= available:
            included_history.insert(0, msg)
            available -= msg_tokens
        else:
            break
    
    return format_prompt(system_prompt, included_history, user_message)
```

### 模式 2：在 Token 邊界處分塊

```python
def chunk_at_token_boundaries(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> list[str]:
    encoding = tiktoken.encoding_for_model("gpt-4")
    tokens = encoding.encode(text)
    
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
        start = end - overlap
    
    return chunks
```

### 模式 3：Token 預算分配

```python
class TokenBudget:
    def __init__(self, total: int):
        self.total = total
        self.allocated = {}
    
    def allocate(self, component: str, tokens: int) -> bool:
        used = sum(self.allocated.values())
        if used + tokens > self.total:
            return False
        self.allocated[component] = tokens
        return True
    
    def remaining(self) -> int:
        return self.total - sum(self.allocated.values())

# 使用方式
budget = TokenBudget(total=8000)
budget.allocate("system_prompt", 500)
budget.allocate("retrieved_context", 2000)
budget.allocate("user_message", 200)
budget.allocate("output_reserve", 2000)
# 剩餘：3300 token 用於對話歷史
```

---

## 面試問題

### Q：為什麼 GPT-4 在簡單的字元計數上有困難？

**強而有力的回答：**
分詞將文字轉換為子詞單元，而非字元。當被問到「strawberry 中有多少個 'r'？」時，模型看到的是像 ["str", "aw", "berry"] 這樣的 token，而不是單個字母。

模型必須推理它無法直接觀察的 token 的內部結構。這需要記憶或計算 token 的字元組成，這是一種突現能力，並非總是可靠的。

解決方案是提示模型先逐字元拼出單詞，然後計數。這迫使創建字元級 token。

### Q：如何估計成本規劃的 token 數量？

**強而有力的回答：**
粗略估計：對於英語文字，將單詞數乘以 1.3。

準確計數：使用特定於模型的 tokenizer。
- OpenAI：tiktoken 函式庫
- 其他：transformers AutoTokenizer

重要考慮因素：
- 非英語文字使用 1.5-3 倍的 token
- 程式碼和結構化資料分詞效率低
- 始終為輸出 token 預算額外空間（通常定價更高）
- 包含系統提示和格式化 token

對於生產成本估計，我會對真實請求進行抽樣並測量實際 token 使用情況，然後應用安全邊際。

### Q：在模型之間切換分詞器時會發生什麼？

**強而有力的回答：**
每個模型家族都有自己的分詞器。你無法跨模型重複使用 token，因為：

1. **詞彙表不同：** Token ID 代表不同的字串
2. **合併規則不同：** 相同文字拆分方式不同
3. **特殊 token 不同：** 聊天格式各異

實際影響：
- 始終使用正確的分詞器進行 token 計數
- 快取的嵌入是特定於模型的
- 提示模板需要每個模型調整
- 微調模型繼承其基礎分詞器

### Q：如何處理 RAG 分塊的分詞？

**強而有力的回答：**
對於 RAG（檢索增強生成）中的分塊：

1. **選擇正確的 chunk size**：足夠大以包含有意義的上下文，但又足夠小以放入模型的上下文視窗。通常 256-512 token 是一個好的起點。

2. **在 token 邊界處分割**：不要在單詞或句子中間截斷。使用 tokenizer 找到自然的邊界。

3. **保留元資料**：追蹤每個 chunk 來自哪個文件、chunk 的位置等。這有助於在檢索後重新組織上下文。

4. **考慮重疊**：在 chunk 之間添加一些重疊（通常 10-20%）以確保不會丟失跨邊界的重要資訊。

5. **測試不同的策略**：對於您的特定用例，語義分塊（基於內容含義）可能比固定大小分塊效果更好。

### Q：解釋 BPE 演算法。

**強而有力的回答：**
BPE（位元組對編碼）是一種常用的子詞分詞演算法：

1. 從所有單個位元組（256 個 token）的詞彙表開始
2. 計算訓練語料中所有相鄰 token 配對的頻率
3. 找到最常見的配對並將其合併為一個新 token
4. 重複直到達到目標詞彙表大小

例如，如果「lo」在「low」「lower」「lowest」中反覆出現，它可能會被合併為一個單一 token。這允許常見單詞用更少的 token 表示，同時仍然能夠處理看不見的單詞（通過將它們拆分為已知的子詞）。

### Q：為什麼非英語語言在 LLM 中通常更昂貴？

**強而有力的回答：**
有兩個主要原因：

1. **分詞效率低**：主要在英語上訓練的分詞器對其他語言的處理效果不佳。一個英語單詞可能只需要 1 個 token，而同等的中文或日語內容可能需要 2-5 個 token。

2. **訓練資料不平衡**：大多數模型的訓練資料英語佔比過高，導致其他語言的表示品質較差。

這意味著非英語用戶在 API 調用中支付更多費用，但收到的表示品質可能較低，這是一個正在積極改進的領域（見 GPT-4o 和 Claude 3.5 等模型的多語言進步）。

---

## 參考文獻

- Sennrich et al. "Neural Machine Translation of Rare Words with Subword Units" (2016)
- Kudo and Richardson. "SentencePiece: A simple and language independent subword tokenizer and detokenizer for Neural Text Processing" (2018)
- OpenAI Tokenizer Documentation
- Anthropic Tokenizer Documentation

---

*上一章：[LLM 內部原理](01-llm-internals.md) | 下一章：[注意力機制](03-attention-mechanisms.md)*
