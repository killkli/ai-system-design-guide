# 框架選擇指南

過去一年中，AI 框架景觀顯著整合。每個主要 AI 實驗室現在都發布了一個代理 SDK，Microsoft 將 AutoGen 和 Semantic Kernel 合併為統一的 Agent Framework，互操作性協定（MCP、A2A）已成為標配。本指南提供了基於生產需求、團隊專業知識和系統規模的**決策矩陣**。

## 目錄

- [框架景觀](#landscape)
- [決策矩陣](#matrix)
- [建構對比購買對比框架](#build-vs-buy)
- [應避免的反模式](#anti-patterns)
- [Staff 等級建議](#recommendation)
- [面試題目](#interview-questions)

---

## 框架景觀

### 編排和代理框架

| 框架 | 層級 | 主要價值 | 關鍵弱點 |
|-----------|------|---------------|--------------|
| **LangGraph** | L1（核心） | 精確狀態控制、基於圖形 | 複雜性、陡峭學習曲線 |
| **DSPy** | L1（核心） | 可靠性和優化 | 前置成本（訓練） |
| **LlamaIndex**| L2（資料） | 進階檢索（RAG） | 邏輯靈活性 |
| **CrewAI** | L3（應用） | 業務流程速度、企業 RBAC | 隱藏失敗 |
| **MS Agent Framework** | L1（企業） | 統一 .NET + Python，取代 AutoGen + SK | RC 狀態（2026 年 Q2 GA） |

### 代理 SDK（實驗室特定）

| 框架 | 層級 | 主要價值 | 關鍵弱點 |
|-----------|------|---------------|--------------|
| **Claude Agent SDK** | L1（代理） | 內建工具、生產代理迴圈 | 需要 Anthropic API |
| **OpenAI Agents SDK** | L1（代理） | 輕量級移交、防護欄 | 以 OpenAI 為中心 |
| **Google ADK** | L1（代理） | 多語言、原生 A2A + Google Cloud | Google 生態系統偏見 |

### 程式設計代理

| 框架 | 層級 | 主要價值 | 關鍵弱點 |
|-----------|------|---------------|--------------|
| **Claude Code** | L1（程式設計） | 自主 CLI 程式設計代理 | 需要 Anthropic API |
| **Cursor / Windsurf** | L2（IDE） | 緊密 IDE + 代理整合 | 閉源基礎設施 |
| **OpenHands** | L2（程式設計） | 開源自主代理 | 需要自託管 |

> **2026 年 4 月注意**：Semantic Kernel 不再列為獨立框架。它已合併到 Microsoft Agent Framework。現有 SK 使用者應計劃遷移。

---

## 決策矩陣

**使用此邏輯來選擇您的堆疊：**

### 核心編排
1. **這是純 RAG 應用嗎？** → **LlamaIndex**。
2. **需要長期狀態/人在迴路中？** → **LangGraph**。
3. **高可靠性（99%+）和跨模型可攜性至關重要？** → **DSPy**。
4. **您是 C#/.NET 企業嗎？** → **Microsoft Agent Framework**（取代 Semantic Kernel + AutoGen）。
5. **您正在為商業務用戶構建高階自動化？** → **CrewAI + Flows**。

### 代理 SDK（根據您的主要模型提供者選擇）
6. **在 Claude / Anthropic API 上構建代理？** → **Claude Agent SDK**（Python/TS，內建工具用於檔案/程式碼/命令）。
7. **在 OpenAI API 上構建代理？** → **OpenAI Agents SDK**（輕量級移交、防護欄、MCP 支援）。
8. **在 Google Cloud / Gemini 上構建代理？** → **Google ADK**（原生 A2A、Vertex AI 部署、多語言）。
9. **需要跨廠商代理通訊？** → 在上述任何框架之上使用 **A2A 協定**。

### 程式設計代理
10. **您正在做自主檔案系統級程式設計任務？** → **Claude Code**（CLI）或 **Cline**（VS Code）。
11. **需要與任何 LLM 一起工作的開源程式設計代理？** → **OpenHands**（Docker）。
12. **想要最好的 IDE 體驗與 AI？** → **Cursor**（閉源）或 **Windsurf**（Codeium）。

---

## 建構對比購買對比框架

作為 Staff 工程師，您必須抵制**框架膨脹**。

- **使用框架**當它解決一個**非平凡的電腦科學問題**（例如，狀態持久性、貝氏提示優化、向量圖連結）。
- **建構自訂（薄包裝）**當您只是對 LLM 進行簡單呼叫時。框架增加延遲、更新折舊和偵錯開銷，對於單輪代理來說不值得。

---

## 應避免的反模式

1. **框架隧道**：試圖將複雜邏輯流強迫進入不支援它的框架（例如，使用純 RAG 函式庫進行程式設計代理）。
2. **金錘**：僅因為流行而使用 LangChain，而 50 行 Python 腳本會更快、更便宜。
3. **忽視可觀測性**：部署任何框架時沒有 LLMOps 層（LangSmith/Phoenix）。

---

## Staff 等級建議

對於現代、生產級代理系統：
- **編排**：LangGraph（用於狀態和迴圈）或 Microsoft Agent Framework（用於 .NET 商店）。
- **代理 SDK**：與您的模型提供者匹配 — Claude Agent SDK（Anthropic）、Agents SDK（OpenAI）、ADK（Google）。全部支援 MCP 以便工具存取。
- **優化**：DSPy（為不同模型層級編譯提示詞）。
- **檢索**：LlamaIndex（用於多階段 RAG）。
- **可觀測性**：LangSmith（用於追蹤和評估）。
- **跨廠商代理**：A2A 協定用於跨組織邊界的代理對代理協調。
- **自主程式設計**：Claude Code（CLI）或 Cline（VS Code）用於檔案級編輯任務。
- **開源程式設計代理**：OpenHands 用於自託管或 CI 管線整合。

**2026 年洞察**：
1. 代理程式設計工具（Claude Code、Cursor、OpenHands）不是編排框架的替代品 — 它們是一個**新類別**，在檔案系統級別操作，位於 LLM API 之上但在應用程式邏輯之下。
2. 協定層已經成熟：**MCP 用於代理對工具**和**A2A 用於代理對代理**正在成為基礎設施標準，而非可選附加元件。設計您的架構以支援兩者。
3. 每個實驗室發布自己的代理 SDK 會產生**供應商鎖定風險**。透過使用 MCP 進行工具存取（可在 SDK 間移植）和 A2A 進行代理協調（供應商中立）來緩解。

> *已更新 2026 年 5 月。*

---

## 面試題目

### Q：為何我們看到從「提示」到「程式設計」的趨勢（DSPy）？

**強烈回答：**
**工業化**。提示詞工程是「煉金術」：它不一致且無法擴展。透過像 DSPy 這樣的框架對 LLM 進行程式設計，使我們能夠將 AI 視為**軟體工程學科**。我們可以套用 CI/CD、單元測試（指標）和自動化優化。這將 AI 從「不確定性魔術」轉變為更大分散式系統的**可預測元件**，這是任何任務關鍵生產環境的要求。

### Q：如果您必須構建一個可在 OpenAI、Anthropic 和本地 Llama 模型上運作的系統，您會如何架構它？

**強烈回答：**
我會使用 **DSPy** 進行提示層，使用 **LangGraph** 進行編排層。DSPy 的**簽名**允許我將任務定義與模型的特定行為解耦。然後我會使用**通用模型閘道**（如 LiteLLM 或內部代理）來處理不同的 API 格式。對於工具存取，我會使用 **MCP** — 它與模型無關，因此相同的 MCP 伺服器可工作，無論哪個 LLM 後端處於活躍狀態。如果我需要跨團隊代理協調，我會在邊界層使用 **A2A**。這個堆疊確保如果我需要因成本或延遲原因從 GPT-4o 切換到 Claude Sonnet 4，我不必重寫 50 個提示詞；我只是重新編譯或更新配置。

### Q：由於每個 AI 實驗室都發布自己的代理 SDK（Claude Agent SDK、OpenAI Agents SDK、Google ADK），您如何避免供應商鎖定？

**強烈回答：**
關鍵是**將編排層與模型層分開**。我使用像 LangGraph 之類的框架無關編排器或用於核心工作流程邏輯的薄自訂包裝。模型特定的 SDK 在原型製作或當您專注於單一提供者時很有用，但對於生產多廠商系統，我將模型互動保持在抽象後面（LiteLLM 閘道或 DSPy 簽名）。對於工具存取，**MCP** 提供可攜性 — 相同的 MCP 伺服器可與任何 SDK 一起使用。對於代理協調，**A2A** 提供供應商中立代理對代理通訊。實際規則：在葉節點（個人代理實現）使用實驗室特定的 SDK，但保持編排圖形供應商中立。

---

## 參考文獻

- Google Cloud。〈企業生成式 AI 參考架構〉（2025）
- Gartner。〈AI 應用程式框架魔力象限〉（2025）
- Gartner。〈2026 預測：40% 的企業應用將具有 AI 代理〉（2025）
- Thoughtworks。〈技術雷達：代理框架的興起〉（2024 年 11 月/2025）
- Microsoft。〈Agent Framework 概述〉（2026）
- Anthropic。〈Claude Agent SDK〉（2026）
- Google。〈Agent Development Kit〉（2026）
- OpenAI。〈Agents SDK〉（2026）

---

*新章節：[第 10 章：文件處理](../10-document-processing/01-ocr-and-layout.md)*