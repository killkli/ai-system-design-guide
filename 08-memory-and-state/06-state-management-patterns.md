# 狀態管理模式

AI 系統中的狀態管理已從簡單的「工作階段」演進至**有狀態代理圖（Stateful Agent Graphs）**。管理代理「心智」的流動與持久化與 LLM 同樣重要：這是 LangGraph 成為 LangChain 構建代理的預設控制流程執行期的主要原因之一。

## 目錄

- [狀態物件](#state-object)
- [狀態機 vs. DAG 編排](#orchestration)
- [檢查點與恢復](#checkpointing)
- [平行狀態與分叉/合併](#parallel)
- [時間旅行（狀態重寫）](#time-travel)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 狀態物件

「狀態」是代理工作階段的**單一事實來源（Single Source of Truth）**。
```python
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: list[str]
    current_task: str
    tool_results: dict[str, Any]
    user_context: dict[str, Any]
    iteration_count: int
```
**最佳實踐**：狀態應盡可能**嚴格型別化**且**僅附加（Append-Only）**，以防止長期執行迴圈中的資料遺失。

---

## 狀態機（LangGraph）

業界已收斂至**循環圖（Cyclic Graphs）**（狀態機）。
- **節點**：接收狀態並回傳更新的函式。
- **邊**：根據狀態值決定下一個節點的條件邏輯（例如 `if state['error'] -> goto 'recovery_node'`）。

---

## 檢查點與恢復

在生產環境中，代理可以執行數分鐘或數小時。
- **持久化層**：每個狀態更新都會儲存至資料庫（Postgres/Redis）。
- **復原力**：若伺服器當機，編排器會擷取最後的 `checkpoint_id` 並從中斷處精確恢復。
- **使用者體驗**：這支援**非同步代理**，使用者收到「我正在處理中」訊息，並在狀態「完成」後 10 分鐘收到通知。

---

## 平行狀態（分叉/合併）

對於複雜任務，我們**分叉**狀態。
1. **扇出**：將狀態傳送至 3 個子代理（例如研究者 A、B 和 C）。
2. **扇入（合併）**：一個「管理」代理接收所有三個代理的輸出，並將它們合併回主要狀態物件。

---

## 時間旅行（狀態重寫）

如 HITL 章節所述，狀態管理支援**人類介入（Human Intervention）**。
- 開發人員可以瀏覽工作階段歷史，找到「錯誤轉折」，在該特定時間戳編輯狀態物件，然後**從該點重新執行**圖。

---

## 面試問題

### Q：為什麼使用「基於圖」的狀態機（LangGraph）而非簡單的「While 迴圈」來處理代理？

**理想回答：**
While 迴圈是**不透明且脆弱的**。你無法輕易視覺化邏輯，錯誤處理會變成一團巢狀 if 陳述式。基于图的方法是**可觀測且模組化的**。你可以視覺化整個流程（如 Mermaid 圖），對個別節點進行單元測試，並透過新增新邊簡單地實現「回溯」或「平行執行」等複雜功能。它也使**狀態持久化**變得 trivial，因為框架會處理節點之間的儲存/載入。

### Q：如何在長期執行的代理工作階段中防止「狀態膨脹」？

**理想回答：**
我們使用**狀態修剪**和**訊息摘要**。並非在整個圖中攜帶整個 `tool_results` 字典，而是在子任務完成後將其修剪。對於 `messages` 列表，我們使用專門的「摘要器節點」，每 10 回合執行一次以將歷史壓縮成簡潔的上下文區塊，確保不會超出 token 限制，同時保持狀態物件的靈敏度。

---

## 參考文獻
- LangChain. "LangGraph: Multi-Agent Workflows" (2024/2025)
- Temporal.io. "Stateful AI Agents at Scale" (2025)
- AWS Bedrock. "Managing Long-Running Agent Sessions" (2025)

---

*下一篇：[第九章：框架與工具](../09-frameworks-and-tools/01-langchain-deep-dive.md)*
