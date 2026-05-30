# Microsoft Agent Framework、CrewAI 和代理 SDK 景觀

在過去一年中，多代理框架景觀顯著整合。Microsoft **讓 AutoGen 退役**並將其與 Semantic Kernel 合併為統一的 **Microsoft Agent Framework**（2026 年 2 月 RC 1.0；GA 目標 2026 年 Q2）。CrewAI 成熟到 v1.13 並具有企業級功能，報告稱 60%+ 的財富 500 強公司使用它。同時，每個主要 AI 實驗室都發布了自己的代理 SDK：Anthropic 的 Claude Agent SDK、OpenAI 的 Agents SDK 和 Google 的 ADK。

## 目錄

- [CrewAI：管理者視角](#crewai)
- [Microsoft Agent Framework（AutoGen 的後續版本）](#microsoft-agent-framework)
- [代理 SDK 景觀](#agent-sdk-landscape)
- [Swarms 和點對點通訊](#swarms)
- [框架比較矩陣](#comparison)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## CrewAI：管理者視角

CrewAI 圍繞**流程**概念構建。
- **基於角色的代理**：您定義一個「研究者」、「作者」和「管理者」。
- **任務**：具有特定輸出的明確目標。
- **流程編排**：順序、階層或共識（基於共識）。

### CrewAI Flows

CrewAI **Flows** 在經典 Crew 模式之上新增了**狀態機層**：

```python
from crewai.flow.flow import Flow, listen, start

class ContentFlow(Flow):
    @start()
    def research_topic(self):
        # 返回研究輸出
        return research_crew.kickoff({"topic": self.state["topic"]})
    
    @listen(research_topic)
    def write_article(self, research):
        # 研究完成後觸發
        return writing_crew.kickoff({"research": research})
    
    @listen(write_article)
    def publish(self, article):
        # 最後一步
        return publisher.publish(article)
```

### CrewAI v1.13 重點

CrewAI v1.13 標誌著向企業生產就緒的轉折點：

- **企業 SSO**：企業部署的單一登入完整文件化
- **RBAC 改進**：具有完整許可權參考矩陣的的角色型存取控制
- **GPT-5 相容性**：針對 OpenAI 的 GPT-5 和較新的放棄 `stop` 參數支援的 o 系列模型的修復
- **A2A 任務執行**：以結構化、確定性方式進行代理間動態任務委派
- **NVIDIA NemoClaw 整合**：企業安全部署的基礎設施層級策略執行
- **RuntimeState RootModel**：複雜工作流程的統一狀態序列化

**使用案例**：CrewAI + Flows 是**業務流程自動化**（內容管線、資料分析工作流程，結構定義良好）的最佳框架。CrewAI 報告支援約 20 億次代理執行。

> *已驗證 2026 年 5 月。來源：docs.crewai.com/en/changelog*

---

## Microsoft Agent Framework（AutoGen 的後續版本）

### 合併：AutoGen + Semantic Kernel = Agent Framework

Microsoft 在 2025 年底讓 AutoGen 作為獨立產品退役，並將其與 Semantic Kernel 合併為統一的 **Microsoft Agent Framework**。候選版本 1.0 於 2026 年 2 月發布，GA 目標為 2026 年 Q2。

**合併內容：**
- **來自 AutoGen**：單代理和多代理對話模式（群組聊天、輪流、移交）的簡單抽象
- **來自 Semantic Kernel**：企業級會話管理、型別安全、過濾器、遙測和廣泛的模型/嵌入支援

### 遷移路徑

AutoGen 繼續接收錯誤修正和安全修補，但**新功能僅進入 Agent Framework**。Microsoft 提供了官方遷移指南。如果開始新專案，直接使用 Agent Framework。

### 關鍵能力

```python
# Microsoft Agent Framework：基於圖形的工作流程
from agent_framework import Agent, Workflow, HandoffStep

planner = Agent("Planner", model="gpt-5.5", system_message="分解任務。")
executor = Agent("Executor", model="gpt-5.5-mini", system_message="執行子任務。")

workflow = Workflow(
    steps=[
        HandoffStep(from_agent=planner, to_agent=executor),
    ],
    state_management="session",  # 內建會話持久性
)
```

**框架重點：**
- **統一 .NET 和 Python**：跨兩種語言的相同程式設計模型
- **基於圖形的工作流程**：具有明確控制的順序、並發、移交和群組聊天模式
- **狀態管理**：對長期和人在迴路中場景的強大基於會話的持久性
- **MCP 支援**：用於工具存取的原生 Model Context Protocol 整合
- **多提供者**：支援 OpenAI、Azure OpenAI、Anthropic、Google 和本地模型

> *已驗證 2026 年 5 月。來源：learn.microsoft.com/en-us/agent-framework*

---

## 代理 SDK 景觀

每個主要 AI 實驗室現在都發布了自己的代理框架。截至 2026 年 5 月的景觀：

### Claude Agent SDK（Anthropic）

Claude Agent SDK（從 Claude Code SDK 重新命名）提供與為 Claude Code 提供支援的相同工具、代理迴圈和上下文管理，作為 Python 和 TypeScript 中的函式庫提供。

- **內建工具**：檔案讀取、命令執行、程式碼編輯 — 代理無需自訂工具實現即可立即工作
- **Supervisor 模式**：具有委派的階層代理樹
- **部署**：支援 AWS Bedrock、Google Vertex AI 和 Azure
- **截至 2026 年 5 月**：Python v0.1.48+、TypeScript v0.2.71+

### OpenAI Agents SDK

OpenAI 的輕量級框架，使用原生 Python/TypeScript 構造進行多代理工作流程：

- **基於移交**：代理使用 `Handoff(TargetAgent)` 相互委派 — 無需中央監督者
- **防護欄**：內建輸入驗證和安全檢查
- **MCP 整合**：原生 MCP 伺服器工具支援
- **即時代理**：使用 gpt-realtime-1.5 的語音代理支援

### Google Agent Development Kit（ADK）

Google 的框架針對 Google 生態系統進行了優化，但模型無關：

- **多語言**：Python、TypeScript、Java、Go（截至 2026 年 5 月全部為 1.0+）
- **A2A 原生**：用於跨廠商編排的內建代理對代理協定支援
- **Vertex AI 整合**：部署到 Agent Engine Runtime 以進行託管託管
- **基於圖形**：代理工作流程建模為有向圖

> *已驗證 2026 年 5 月。*

---

## Swarms 和 P2P

兩個框架（以及更廣泛的 SDK 景觀）都採用了 **Swarm 模式**。
- **移交**：不是中央監督者，代理「移交」對話到最相關的專家。
- **範例**：「銷售代理」意識到使用者正在問技術問題，並將執行緒移交給「支援代理」。

---

## 框架比較矩陣

| 功能 | CrewAI | MS Agent Framework | LangGraph | Claude Agent SDK | OpenAI Agents SDK | Google ADK |
|---------|--------|-------------------|-----------|-----------------|-------------------|------------|
| **核心抽象** | Task/Process/Flow | Workflow/Agent | State/Graph | Supervisor/Tools | Handoff/Agent | Agent Graph |
| **架構** | 宣告式 + 狀態機 | 圖形工作流程 | 命令式 DAG | 階層樹 | Swarm 移交 | 有向圖 |
| **易用性** | 高 | 中 | 低 | 中 | 高 | 中 |
| **控制** | 低-中 | 中-高 | 高 | 中 | 低-中 | 中-高 |
| **最適合** | 業務自動化 | 企業 .NET/Python | 複雜編排 | 程式設計/工具代理 | 快速多代理 | Google Cloud AI |
| **多語言** | Python | .NET + Python | Python | Python + TS | Python + TS | Python, TS, Java, Go |
| **MCP 支援** | 是 | 是 | 透過工具 | 原生 | 是 | 是 |
| **A2A 支援** | 透過擴展 | 計劃中 | 透過工具 | 否（直接） | 否（直接） | 原生 |

---

## 面試題目

### Q：何時會選擇 CrewAI 而非 LangGraph？

**強烈回答：**
**速度對比精確度**。當我需要非常快速地建立一個代理團隊來處理標準流程（如內容生成或資料分析）時，我使用 **CrewAI**。它為「規劃」和「合作」提供了現成的高階抽象。當我需要**細粒度控制**每個狀態轉換、多輪人在迴路觸發或不符合「角色扮演團隊」隱喻的複雜錯誤恢復邏輯時，我切換到 **LangGraph**。

### Q：Microsoft 讓 AutoGen 退役以支持 Agent Framework。這如何影響現有 AutoGen 部署？

**強烈回答：**
AutoGen 繼續接收錯誤修正和安全修補，因此現有部署不會立即壞掉。然而，**所有新功能開發**都在 Agent Framework 中。遷移路徑有完整文件：AutoGen 的 `AssistantAgent` 對應到 Agent Framework 的 `Agent` 類別，`GroupChat` 對應到新的 `Workflow` 模式，而 Semantic Kernel 的企業功能（會話管理、遙測、過濾器）現在原生可用。遷移的關鍵好處是**統一的 .NET 和 Python 支持**以及**基於圖形的工作流程**，可對多代理執行路徑提供明確控制。對於新專案，直接從 Agent Framework 開始。

### Q：如何防止「無限迴圈」，即代理繼續相互對話而不解決任務？

**強烈回答：**
我們使用**終止條件**和**最大對話輪數**。我們還實現了一個「批評者代理」，其唯一工作是檢測對話是否停滯。如果批評者檢測到循環性，它會觸發使用者代理進行中斷，或將群組聊天管理器強制切換到不同的推理路徑。我們還監控 **Token 速度**：如果一對代理在 2 分鐘內使用 100K token 而沒有進展，我們自動終止會話。在 2026 年，像 Microsoft Agent Framework 和 LangGraph 之類的框架提供了內建的工作流程超時和狀態檢查點，使迴圈檢測更加系統化。

---

## 參考文獻

- CrewAI。〈多代理流程引擎〉（2025/2026，v1.13）
- Microsoft。〈Agent Framework 概述〉（2026）— learn.microsoft.com/en-us/agent-framework
- Microsoft。〈AutoGen 到 Agent Framework 遷移指南〉（2026）
- Anthropic。〈Claude Agent SDK〉（2026）— platform.claude.com/docs/en/agent-sdk
- OpenAI。〈Agents SDK 文件〉（2026）
- Google。〈Agent Development Kit〉（2026）— google.github.io/adk-docs
- OpenAI Swarm。〈輕量級多代理編排〉（2024 技術報告）

---

*下一篇：[框架選擇指南](08-framework-selection-guide.md)*