# LangGraph 編排

LangGraph 是構建有狀態、多代理系統的**實際標準**。它在 2025 年底達到 v1.0，並於 2026 年初在 GitHub 星數上超越 CrewAI，這得益於企業對其基於圖形執行環境的採用。與簡單的鏈不同，LangGraph 允許**迴圈**、**狀態持久性**和**人在迴路中**介入。

## 目錄

- [圖形哲學](#philosophy)
- [循環對比非循環工作流程](#cyclic)
- [LangGraph 中的狀態管理](#state)
- [持久性和檢查點](#persistence)
- [多代理編排模式](#multi-agent)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## 圖形哲學

2023 年，代理是「黑盒子」。
今天，代理是**圖形**。
圖形由以下組成：
- **節點**：Python 函式（LLM、工具或資料處理）。
- **邊**：節點之間的路徑。
- **條件邊**：基於**狀態**決定路徑的邏輯。

---

## 循環對比非循環

標準 LangChain 是**非循環的**（順序執行）。
LangGraph 是**循環的**。
- **迴圈的力量**：代理可以嘗試工具，看到錯誤，然後**循環回**「思考」節點再試一次。這是 **ReAct（Reasoning and Acting，推理與行動）模式**的基礎。

---

## 狀態管理

**狀態 Schema** 是圖形的「心智」。
```python
class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: list[str]
    is_secure: bool
```
**細節**：使用 `Annotated` 搭配 `add_messages` 允許圖形**附加**到歷史而不是覆寫它，保留完整的推理軌跡。

---

## 持久性和檢查點

目前的 LangGraph 使用**基於執行緒的持久性**。
- **概念**：每個會話都有一個 `thread_id`。
- **優勢**：如果使用者在 2 天後回來，代理會記住它在多步驟工作流程中的確切位置。
- **時間回溯**：開發人員可以「重新執行」特定執行緒從先前的狀態以偵錯失敗。

---

## 多代理模式

| 模式 | 描述 | 案例研究 |
|---------|-------------|------------|
| **Supervisor** | 一個「管理者」指導專業工作者。 | 研究團隊 |
| **Peer-to-Peer**| 代理直接相互移交任務。 | 客戶支援 |
| **Hierarchical**| 圖形中的圖形（巢狀圖形）。 | 企業工程 |

---

## 面試題目

### Q：為何使用 LangGraph 而非 OpenAI 的「Assistant API」？

**強烈回答：**
**控制性和可攜性**。Assistant API 是一個黑盒子：你無法看到確切的提示詞，也無法控制邏輯閘道。LangGraph 是一個**白盒子框架**。我可以使用任何模型（OpenAI、Claude、Llama 3.3），精確控制何時呼叫工具，並在步驟之間注入自訂驗證邏輯。更重要的是，LangGraph 是**開源的**，可以本地執行/本地部署，這對許多企業安全需求至關重要。

### Q：如何處理具有 20+ 節點的圖形中的「狀態過載」？

**強烈回答：**
我們使用**狀態窄化**。不是將整個全域狀態傳遞給每個節點，而是為子圖定義專門的子狀態。我們也使用 **Trim Runnables** 來在訊息歷史進入 LLM 之前修剪它，確保我們不會浪費 token，同時將「真實」保存在持久性層中。

---

## 參考文獻

- LangChain 團隊。〈LangGraph：規模化的多代理工作流程〉（2025）
- Anthropic。〈使用狀態機建立彈性代理〉（2025）
- OpenSource AI。〈迴圈與代理的未來〉（2024 技術報告）

---

*下一篇：[LangSmith 可觀測性](03-langsmith-observability.md)*