# 上下文工程

上下文工程是以最有效的 Token 填補 LLM 有限「工作記憶體」的科學。隨著上下文視窗現在達到 100 萬+ Token（Claude Sonnet 4.6、Gemini 3.1 Pro、GPT-5.5），加上模型獲得延伸思考能力，重點已從「容納資料」轉向「排名相關性」和「管理計算預算」。

## 目錄

- [長上下文範式（100 萬+ Token）](#long-context)
- [延伸思考與預算 Token](#extended-thinking)
- [中間迷失](#lost-in-the-middle)
- [上下文預算管理與 Token 感知](#budgeting)
- [提示詞快取經濟學](#prompt-caching)
- [上下文壓縮（RAD-L）](#compression)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## 長上下文範式（100 萬+ Token）

Gemini 3.1 Pro（100 萬）、Claude Sonnet（100 萬）、Claude Opus（100 萬）和 GPT-5.5（100 萬）等模型有著大規模上下文視窗。

**洞察**：「上下文是新 RAG。」
對於少於 100,000 份文件的資料集，將整個資料集放入上下文視窗通常比使用外部向量資料庫更準確、更快速。這稱為**「上下文內 RAG」**。

---

## 延伸思考與預算 Token

多個前沿模型現在提供可控的內部推理，然後才生成回應：

### Claude（Sonnet、Opus）：延伸思考

```python
response = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # 最大內部推理 Token
    },
    messages=[{"role": "user", "content": "將此程式碼庫重構為非同步..."}]
)

# 回應有兩個區塊：
# 1. thinking 區塊（除錯可見，不顯示給使用者）
# 2. text 區塊（實際答案）
for block in response.content:
    if block.type == "thinking":
        print("[思考中]", block.thinking)
    elif block.type == "text":
        print("[答案]", block.text)
```

**關鍵參數：**
- `budget_tokens`：1,024 → 100,000。越高 = 準確率越好，成本越高。
- 思考 Token 按標準費率計費。10K 思考預算 = 每次請求 +$0.15。
- 支援串流——思考區塊在文字之前串流。

### o3（OpenAI）——推理努力

```python
response = client.chat.completions.create(
    model="o3",
    reasoning_effort="medium",  # "low" | "medium" | "high"
    messages=[{"role": "user", "content": "證明或反駁 P=NP。"}]
)
# 推理 Token 是不可見的——o3 不暴露其內部鏈
```

**努力層級與成本（概略）：**

| 努力 | 速度 | 成本倍數 | 最適場景 |
|------|------|----------|----------|
| low | 快速 | 1x | 簡單邏輯、快速查詢 |
| medium | 中等 | 3-5x | 程式設計、分析 |
| high | 慢 | 8-20x | 博士級問題、ARC-AGI |

### 何時啟用思考 / 推理

| 條件 | 建議 |
|------|------|
| 複雜多步驟程式碼重構 | ✅ 啟用（預算：8K-20K） |
| 簡單問答 / 提取 | ❌ 停用——增加成本和延遲 |
| STEM / 數學問題 | ✅ 啟用（o3-mini medium） |
| 高容量聊天機器人 | ❌ 停用——使用標準模式 |
| 安全關鍵決策 | ✅ 啟用——額外推理捕捉邊緣案例 |

**生產模式**：使用複雜度分類器來控制延伸思考。若查詢複雜度分數 < 0.5，完全跳過思考模式（在推理密集型工作負載上節省 60-80%）。

```python
def smart_generate(query: str) -> str:
    complexity = classifier.predict(query)  # 0-1 分數

    if complexity > 0.7:
        # 為困難問題啟用延伸思考
        return claude_with_thinking(query, budget_tokens=8000)
    else:
        # 為簡單任務使用標準快速模式
        return claude_standard(query)
```

---

## 中間迷失

2023 年，模型對提示詞中間資訊的準確率下降。
**現狀**：前沿模型（Claude Sonnet、Claude Opus、Gemini 3.1 Pro、GPT-5.5）表現顯著更好，但**注意力梯度**仍然存在。
- **最佳實踐**：將關鍵指令和黃金標準範例放在提示詞的**最開頭**和**最結尾**。中間 = 原始資料/知識區塊。
- **使用區塊排序**：重新排序檢索文件，使最相關的在開頭和結尾。

---

## 上下文預算管理與 Token 感知

每個 Token 都花錢並增加 TTFT（首次生成 Token 時間）。

| 元件 | 預算（Token） | 原因 |
|------|-------------|------|
| **系統提示詞** | 500 - 1,000 | 核心邏輯和人格。 |
| **歷史** | 2,000 - 5,000 | 對話「狀態」。 |
| **資料/搜尋** | 10k - 1M | 取決於任務深度。 |
| **輸出保留** | 1,000 - 4,000 | 必須為推理預留空間。 |

---

## 提示詞快取經濟學

幾乎所有主要提供商（OpenAI、DeepSeek、Anthropic、Google）都支持**前綴快取**。

- **交叉點**：若您將 100k Token 上下文（例如程式碼庫）重複用於超過 2 次請求，快取折扣實際上使其比 RAG 更便宜。
- **快取命中**：$0.05 / 1M Token。
- **快取未命中**：$5.00 / 1M Token。

**架構選擇**：設計您的系統，使「系統提示詞 + 基礎知識」保持靜態，以維持 100% 快取命中率。

---

## 上下文壓縮（RAD-L）

對於極長上下文（1,000 萬+），我們使用**推理感知刪除（RAD-L）**。
- **原理**：一個小型輔助模型（0.1B）在文字傳送到大型前沿模型之前，掃描並移除「填充」詞、常見語言模式和無關區塊。
- **效益**：在準確率下降 <1% 的情況下，將提示詞大小減少 20-50%。

---

## 面試題目

### Q：什麼時候選擇長上下文而非 RAG？

**理想回答：**
當高保真檢索和跨文件推理至關重要時，我選擇長上下文。RAG 受「檢索差距」之苦——若您的向量搜尋錯過相關區塊，模型就永遠看不到它。長上下文（高達 200 萬 Token）提供 100% 召回率。具體來說，我會將其用於程式碼庫分析、法律文件審查和多文件財務審計。對於動態網路規模資料或超過任何上下文視窗的十億文件資料集，我會堅持使用 RAG。

### Q：如何處理與百萬 Token 提示詞相關的高 TTFT？

**理想回答：**
主要解決方案是**上下文快取**。透過在 GPU 叢集上快取重型文件，模型不必為每輪「重讀」（前置處理）整個 100 萬 Token。快取提示詞的 TTFT 與 1k Token 提示詞几乎相同。此外，對於非快取請求，我會使用**串流前置處理**，模型在仍處理大量上下文後半部分的同時，生成初始摘要或「想法」。

---

## 參考文獻

- Liu et al. "Lost in the Middle" (2023/2024 update)
- Anthropic. "Extended Thinking: Technical Guide" (2025) — https://docs.anthropic.com/
- OpenAI. "o3 and o3-mini System Card" (2025)
- Google. "Gemini 2.0 Flash: Technical Report" (2024)

---

*下一篇：[結構化生成](06-structured-generation.md)*
