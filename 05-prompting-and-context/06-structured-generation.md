# 結構化生成

結構化生成是強制 LLM 以機器可讀格式（JSON、YAML、CSV）100% 可靠地產生輸出的過程。這一領域已從「基於提示詞的請求」演進為「引擎級約束」。

## 目錄

- [JSON 模式革命](#json-mode)
- [函式呼叫與工具使用](#function-calling)
- [約束解碼（CFG 與 Regex）](#constrained-decoding)
- [多階段提取模式](#multi-stage)
- [驗證與格式錯誤](#validation)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## JSON 模式革命

歷史上，取得 JSON 是「只返回 JSON，不要其他文字」的艱苦掙扎。
**標準方法**：使用原生的 `response_format: { type: "json_schema" }`（OpenAI/Gemini）或工具輸出結構描述（Anthropic）。

- **優勢**：100% 語法有效性。模型實際上無法輸出不是有效 JSON 的字串。
- **幕後**：服務引擎在每個步驟遮罩詞彙表，確保下一步只能選擇有效 JSON 字元（例如 `{`、`"`、`:`、`[`）。

---

## 函式呼叫與工具使用

函式呼叫是 LLM「選擇」函式並填充其引數的結構化生成。

```json
// 工具呼叫範例
{
  "name": "get_stock_price",
  "arguments": { "symbol": "AAPL", "interval": "1d" }
}
```

**專業細節**：**平行函式呼叫**現在是標準。模型可以決定同時呼叫 5 個不同工具（例如，檢查帳戶餘額、檢查信用評分、檢查貸款利率）並聚合結果。

---

## 約束解碼（CFG 與 Regex）

對於自託管模型（Llama-cpp、通過 Outlines 的 vLLM），我們使用**上下文自由文法（CFG）**或**正則表達式**。

```python
# Outlines 模式
model = outlines.models.transformers("meta-llama/Llama-4-8B")
generator = outlines.generate.regex(model, r"(\d{3})-\d{3}-\d{4}")
# 結果：模型只能輸出電話號碼。
```

---

## 多階段提取模式

對於複雜資料提取（例如，從病歷中提取 50 個欄位），不要一次完成。
- **階段 1（文字對文字）**：以自然語言提取「混亂但完整」的事實集合。
- **階段 2（文字對 JSON）**：使用較小、更便宜的模型將這些自然語言事實轉換為嚴格的 JSON 結構描述。
- **效益**：減少「壓力下的幻覺」——當被迫同時推理和遵循嚴格語法時，大模型很掙扎。

---

## 驗證與格式錯誤

即使有「JSON 模式」，JSON **邏輯**內部可能錯誤（例如，欄位缺失或日期格式錯誤）。

**恢復模式：**
1. 根據 **Pydantic/Zod** 驗證輸出。
2. 若失敗，將**追蹤錯誤**發回模型：
   「錯誤：欄位 'age' 必須是整數，得到 'twenty'。修正並重新生成。」
3. 大多數模型在第一次重試時修正錯誤。

---

## 面試題目

### Q：為什麼「JSON 模式」比基於提示詞的 JSON 請求更可靠？

**理想回答：**
基於提示詞的請求依賴模型的*意願*遵循指示；而「JSON 模式」（或約束解碼）依賴服務引擎的*無能力*做其他事情。通過在推理層級應用「Logit Bias」或「文法遮罩」，引擎將下一個 Token 的選擇限制為僅那些根據結構描述有效的 Token。這消除了「前言」（例如「當然，以下是您的 JSON...」），並確保您不會因高溫度或隨機性而得到格式錯誤的字串。

### Q：一次要求 LLM 提供過多結構化欄位有什麼風險？

**理想回答：**
這是**結構描述複雜度**與**資訊完整性**之間的權衡。隨著結構描述增長（例如 20+ 層次欄位），模型的注意力被維持 JSON 結構（括號、鍵、引號）所消耗，而不是驗證資料的準確性。這經常導致「遺漏幻覺」，模型跳過欄位或用佔位符資料填充。緩解方法是使用「鏈式密度」提取或將提取拆分為多個平行子任務。

---

## 參考文獻

- OpenAI. "Structured Outputs Documentation" (August 2024 update)
- Outlines Project. "Context-Free Grammar Guided Generation" (2024)
- Willard et al. "Efficient Guided Generation for LLMs" (2023)

---

*下一篇：[提示詞優化（DSPy）](07-prompt-optimization-dspy.md)*
