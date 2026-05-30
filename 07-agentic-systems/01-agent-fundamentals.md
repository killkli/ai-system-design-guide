# 智慧代理基礎（Agent Fundamentals）

代理（Agent）是指由大型語言模型（LLM）驅動、超越「聊天」進入「自主問題解決」的系統。其定義已從簡單的 ReAct（推理與行動）迴圈演進為**封閉迴圈推理系統**，採用內建的「系統二（System 2）」思維——例如 Claude 的延伸思考（Extended Thinking）、GPT 的推理（Reasoning）模式、DeepSeek-R2、Gemini 3.1 Pro Deep Think。

## 目錄

- [代理公式](#代理公式)
- [系統一（LLM）vs. 系統二（推理模型）](#系統一llmvs-系統二推理模型)
- [代理等級（自主光譜）](#代理等級自主光譜)
- [核心元件](#核心元件)
- [代理生命週期](#代理生命週期)
- [面試問題](#面試問題)
- [參考文獻](#參考文獻)

---

## 代理公式

現代代理常以下列公式描述：
`代理 = 推理模型（Reasoning Model）+ 工具使用（Tool Use）+ 持久記憶（Persistent Memory）+ 環境回饋（Environment Feedback）`

**細微差別**：2023 年，代理是聊天模型的「包裝層」。今日，代理日益**整合化**。前沿模型（Claude、GPT 推理模式、DeepSeek-R2）的「思考」過程已內建於預訓練中，使代理迴圈更加穩定，不易「停滯」。

---

## 系統一 vs. 系統二思維

建構代理時，需選擇合適的「思維模式」：

| 模式 | 認知類型 | 類比 | 目前技術堆疊 |
|------|----------|------|-------------|
| **系統一（System 1）** | 快速、直覺、反應 | 反射動作 | Claude Haiku 4.5 / Sonnet 4.6 / GPT-5.5-mini / Gemini 3.1 Flash |
| **系統二（System 2）** | 緩慢、邏輯、規劃 | 深思熟慮 | Claude Opus / GPT 推理模式 / DeepSeek-R2 / Gemini 3.1 Pro Deep Think |

**設計模式**：使用系統一模型處理「快速 UI」與「路由」。使用系統二模型處理「決策關卡」與「複雜規劃」。

---

## 代理等級（Agency Levels）

並非每個自主系統都是「代理」。我們依**代理等級（Agency Levels）**來分類：

1. **L0：腳本鏈（Script Chain）**：固定序列（例如標準 LangChain）。
2. **L1：工具增強（Tool-Augmented）**：模型可選擇工具但不做規劃。
3. **L2：ReAct 代理（ReAct Agent）**：簡單的「思考→行動→觀察」迴圈。
4. **L3：自主規劃代理（Self-Planning Agent）**：將目標分解為子任務圖。
5. **L4：環境代理（Environment Agent）**：在背景執行，只在必要時介入。

---

## 核心元件

### 1. 推理模型（Reasoning Model，執行者）
代理的大腦，相當於 CPU，負責決定「成功路徑」。

### 2. 工具（Tool，四肢）
介面（API、瀏覽器、資料庫），讓代理能影響外部世界。
> [!NOTE]
> **模型上下文協定（Model Context Protocol, MCP）**，目前已成為工具互操作性的產業標準，獲得 Anthropic、OpenAI、Google、Microsoft 與 AWS 的採用。治理權於 2025 年 12 月移轉至 Linux 基金會的 Agentic AI Foundation。

### 3. 記憶（Memory，經驗）
- **短期記憶（Short-term）**：上下文視窗（Context Window，KV Cache）。
- **長期記憶（Long-term）**：向量資料庫（Vector Database）或持久狀態（例如 Mem0）。

---

## 代理生命週期

1. **攝入（Ingestion）**：接收使用者目標。
2. **分解（Decomposition）**：將目標拆解為子步驟。
3. **執行（Execution）**：呼叫工具並處理結果。
4. **反思（Reflection）**：評估觀察結果是否使代理更接近目標。
5. **完成（Completion）**：為使用者綜合最終證明。

---

## 面試問題

### Q：為什麼「推理模型」（Reasoning Model）（如 Claude 或 GPT 推理模式）比標準 LLM 更適合代理？

**理想回答：**
標準 LLM（系統一）根據模式匹配預測*下一個 token*。當工具呼叫發生錯誤時，它們常會幻想出一個修復方案而非承認失敗。推理模型在推理過程中使用**思維鏈（Chain-of-Thought, CoT）**。它們在輸出回應前，會在多個隱藏步驟中「思考」。對代理而言，這意味著更高的**路徑可靠性（Path Reliability）**——模型不太可能陷入無限迴圈或對同一個失敗動作重試兩次，因為它已在內部模擬過該失敗。

### Q：如何防止長期任務中的「代理漂移」（Agentic Drift）？

**理想回答：**
代理漂移發生在子步驟將代理帶離原始目標太遠、以致失去上下文時。標準解決方案是**目標錨定（Goal Anchoring）**：將「原始目標」作為釘選系統訊息包含在內，並使用**次級觀察模型（Secondary Observation Model）**（一個較小、較便宜模型）為每個代理動作評分，對照原始目標。若分數低於閾值，代理會被迫「從根部重新規劃」。

---

## 參考文獻

- Kahneman, D. 《思考，快與慢》（應用於 AI，2025）
- OpenAI. 《學習使用 LLM 推理》（2024）
- DeepSeek. 《R1：推理的冷啟動資料》（2025）

---

*下一篇：[推理迴圈：ReAct 及其超越](02-reasoning-loops-react-and-beyond.md)*
