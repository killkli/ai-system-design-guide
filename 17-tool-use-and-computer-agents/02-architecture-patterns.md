# 工具使用代理程式的架構模式

2026 年的每一個工具使用代理程式——從 OpenClaw 到 Claude Code 到 Cursor 的背景代理程式——都建立在一系列核心架構模式之上。理解這些模式讓你能夠從第一性原理設計代理程式，而不是複製特定工具。本章節深入解析每種模式，包括詳細圖表、程式碼範例、權衡分析，以及何時使用哪種模式的指導。

## 目錄

- [模式 1：函式/工具呼叫](#pattern-1-functiontool-calling)
- [模式 2：視覺式自動化](#pattern-2-vision-based-automation)
- [模式 3：本地程式碼執行](#pattern-3-local-code-execution)
- [模式 4：多代理程式工具協調](#pattern-4-multi-agent-tool-orchestration)
- [沙盒化與非沙盒化執行](#sandboxed-vs-unsandboxed-execution)
- [跨工具呼叫的狀態管理](#state-management-across-tool-calls)
- [錯誤處理與重試模式](#error-handling-and-retry-patterns)
- [MCP 整合模式](#mcp-integration-patterns)
- [架構決策樹](#architecture-decision-tree)
- [系統設計面試切入點](#system-design-interview-angle)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 模式 1：函式/工具呼叫

這是生產環境中部署最廣泛的模式。LLM 決定呼叫哪個工具及帶什麼參數；框架執行呼叫；結果被反饋到對話中用於下一步推理。

### 架構

```
+-------------------------------------------------------------------+
|              Function/Tool Calling Pattern                        |
+-------------------------------------------------------------------+
|                                                                   |
|  +------------------+                                             |
|  |  User Message     |                                            |
|  +--------+---------+                                             |
|           |                                                       |
|           v                                                       |
|  +--------+---------+     +------------------+                    |
|  |  LLM Reasoning   |---->|  Tool Selection  |                   |
|  |                   |     |                  |                    |
|  |  "I need to look  |     |  tool: search_db |                   |
|  |   up the order"  |     |  args: {id: 42}  |                    |
|  +-------------------+     +--------+---------+                   |
|                                     |                             |
|                                     v                             |
|                            +--------+---------+                   |
|                            |  Tool Executor   |                   |
|                            |  (Framework)     |                   |
|                            |                  |                   |
|                            |  Validates args  |                   |
|                            |  Calls function  |                   |
|                            |  Returns result  |                   |
|                            +--------+---------+                   |
|                                     |                             |
|                                     v                             |
|                            +--------+---------+                   |
|                            |  Result Injected |                   |
|                            |  into Context    |                   |
|                            |                  |                   |
|                            |  {status: "shipped",                 |
|                            |   tracking: "1Z..."} |               |
|                            +--------+---------+                   |
|                                     |                             |
|                                     v                             |
|                            +--------+---------+                   |
|                            |  LLM Generates   |                   |
|                            |  Final Response  |                   |
|                            +------------------+                   |
+-------------------------------------------------------------------+
```

### 三步驟詳解

**步驟 1——結構描述呈現**：模型接收描述可用工具的 JSON 結構描述。2026 年的最佳實踐是使用動態清單，根據使用者意圖僅獲取相關工具，而不是預先載入所有工具結構描述。

**步驟 2——意圖擷取**：模型輸出結構化工具呼叫。這不是自由形式文字；它是帶有 `tool_name` 和 `arguments` 的 JSON 物件，框架可以確定性地解析它。

**步驟 3——執行與上下文關聯**：框架驗證參數（使用 Pydantic、Zod 或類似工具）、呼叫函式，並將結果作為具有 role `tool` 的新訊息注入回對話中。

### 程式碼範例：MCP 伺服器 + 用戶端

```python
# MCP Server: defines a tool with strict schema
from mcp.server import Server
from pydantic import BaseModel, Field

server = Server("order-service")

class OrderLookup(BaseModel):
    """Look up an order by ID. DO NOT use for cancelled orders."""
    order_id: str = Field(..., description="The order UUID")

@server.tool()
async def lookup_order(args: OrderLookup) -> dict:
    order = await db.orders.find_one({"id": args.order_id})
    if not order:
        return {"error": "Order not found", "suggestion": "Check order ID format"}
    return {"status": order["status"], "tracking": order.get("tracking_number")}
```

```python
# MCP Client: agent discovers tools dynamically, calls them, feeds results back
tools = await mcp_client.list_tools()
response = client.messages.create(model="claude-sonnet-4-6", tools=tools,
    messages=[{"role": "user", "content": "Where is my order ORD-12345?"}])

if response.stop_reason == "tool_use":
    tool_call = response.content[0]
    result = await mcp_client.call_tool(tool_call.name, tool_call.input)
    # Feed result back as a tool_result message for the next LLM turn
```

### 何時使用此模式

- API 整合（資料庫、SaaS 工具、內部服務）
- 結構化資料檢索與變異
- 可預先定義工具介面的任何工作流程
- 需要稽核追蹤和輸入驗證的生產系統

### 權衡

| 優勢 | 劣勢 |
|-----------|--------------|
| 確定性執行 | 需要預先準備工具結構描述 |
| 易於稽核和記錄 | 無法與任意 UI 互動 |
| 快速（每工具呼叫 50-200ms） | 模型可能產生幻覺工具名稱/參數 |
| 與任何支援工具使用的 LLM 相容 | 工具過多時結構描述過載 |

---

## 模式 2：視覺式自動化

模型查看螢幕截圖、推理應該做什麼，然後發出低層級動作（點擊、輸入、滾動）。環境執行動作、拍攝新截圖，迴圈重複。這是 Claude Computer Use 和 Open Interpreter 的 Computer API 工作的方式。

### 架構

```
+-------------------------------------------------------------------+
|              Vision-Based Automation Pattern                      |
+-------------------------------------------------------------------+
|                                                                   |
|  +------------------+                                             |
|  |  Task Goal        |  "Fill out the expense form with           |
|  |  (NL instruction) |   last week's receipts"                    |
|  +--------+---------+                                             |
|           |                                                       |
|           v                                                       |
|  +--------+--------------------------------------------------+    |
|  |                    VISION-ACTION LOOP                      |    |
|  |                                                            |    |
|  |   +------------+    +-------------+    +------------+     |    |
|  |   |  OBSERVE   |    |  REASON     |    |  ACT       |     |    |
|  |   |            |    |             |    |            |     |    |
|  |   | Screenshot |--->| Analyze     |--->| Emit action|     |    |
|  |   | (base64)   |    | screenshot  |    | {type:     |     |    |
|  |   |            |    | + goal      |    |  "click",  |     |    |
|  |   |            |    | + history   |    |  x: 450,   |     |    |
|  |   |            |    | + prev acts |    |  y: 320}   |     |    |
|  |   +-----^------+    +-------------+    +------+-----+     |    |
|  |         |                                      |          |    |
|  |         +--------------------------------------+          |    |
|  |                    (Loop until done)                       |    |
|  +-----------------------------------------------------------+    |
|                            |                                      |
|                            v                                      |
|  +-------------------------+------------------------------+       |
|  |         Sandboxed Environment (VM / Docker + VNC)      |       |
|  |                                                        |       |
|  |   +----------+  +----------+  +----------+            |       |
|  |   | Desktop  |  | Browser  |  | Apps     |            |       |
|  |   | (Xfce)   |  | (Chrome) |  | (any)    |            |       |
|  |   +----------+  +----------+  +----------+            |       |
|  +--------------------------------------------------------+       |
+-------------------------------------------------------------------+
```

### 觀察-推理-行動循環

**觀察**：捕獲當前螢幕狀態的截圖。在 Claude Computer Use 中，這是作為圖像內容區塊發送的 base64 編碼 PNG。2026 年新推出的 Zoom Action 允許捕獲特定區域的高解析度裁切，用於密集 UI。

**推理**：多模態 LLM 分析截圖以及任務目標和動作歷史。它決定下一步應該做什麼。這步驟消耗最多的 tokens。

**行動**：模型發出結構化動作：
- `left_click(x, y)` -- 在座標處點擊
- `type(text)` -- 輸入字串
- `key(key_combo)` -- 按下鍵盤快捷鍵
- `scroll(direction, amount)` -- 滾動頁面
- `screenshot()` -- 不執行動作地拍攝新截圖
- `zoom(x0, y0, x1, y1)` -- 高解析度檢視區域

### 程式碼範例：電腦使用迴圈

```python
tools = [
    {"type": "computer_20250124", "name": "computer",
     "display_width_px": 1280, "display_height_px": 800},
    {"type": "bash_20250124", "name": "bash"},
    {"type": "text_editor_20250124", "name": "str_replace_based_edit_tool"}
]
messages = [{"role": "user", "content": "Open the browser and go to GitHub."}]

while True:  # The vision-action loop
    response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=4096, tools=tools, messages=messages)
    if response.stop_reason == "end_turn":
        break
    for block in response.content:
        if block.type == "tool_use":
            result = sandbox.execute_action(block.name, block.input)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": block.id, "content": result}]})
```

### 何時使用此模式

- 為沒有 API 的舊版應用程式自動化
- 圖形介面的端到端測試
- 需要與多個應用程式互動的任務
- 用自然語言描述任務的非開發者使用者

### 權衡

| 優勢 | 劣勢 |
|-----------|--------------|
| 可與任何 GUI 應用程式配合使用 | 慢（每動作步驟 1-3 秒） |
| 無需 API 或整合 | 高 token 成本（截圖很大） |
| 處理動態 UI | 密集介面上的錯誤點擊風險 |
| 對非技術使用者可及性高 | 需要沙盒化 VM 以確保安全 |

---

## 模式 3：本地程式碼執行

使用者用自然語言描述任務。LLM 生成程式碼。程式碼在本地機器上運行（或在沙盒中）。觀察輸出，LLM 要麼生成更多程式碼，要麼提供最終答案。這是 Open Interpreter 和部分 Claude Code 的工作方式。

### 架構

```
User (NL): "Analyze the CSV and plot the top 10 products"
  |
  v
[LLM Generates Code] --> Python/Bash/JS
  |
  v
[Permission Gate] --> "Run this code? [y/N]" (auto-approve, always-ask, or rules-based)
  |
  v
[Code Executor] --> Execute, capture stdout/stderr/return value
  |
  v
[Output Observer] --> Error? Feed back to LLM for fix. Success? Present to user.
  |
  v
[LLM Decides] --> Done? Return result. Need more? Generate next code block. (Loop)
```

### NL-程式碼-執行-觀察循環

**1. 自然語言到程式碼**：LLM 將使用者意圖轉換為可執行程式碼。程式碼語言取決於任務——Python 用於資料分析、bash 用於系統操作、JavaScript 用於 Web 任務。

**2. 許可閘道**：執行前，要求使用者批准。這是非沙盒化環境的關鍵安全機制。實作方式各異：
- **始終詢問**（Open Interpreter 預設）：每個程式碼區塊都需要明確批准
- **自動批准**（信任模式）：危險但快速
- **基於規則**（Claude Code 模式）：配置中的允許/拒絕模式。例如：允許 `git` 命令，拒絕 `rm -rf`

**3. 執行並捕獲**：程式碼在使用完整（或受限）系統存取的執行時中運行。stdout、stderr、返回值和任何生成的檔案都被捕獲。

**4. 觀察並迭代**：LLM 看到執行輸出。如果有錯誤，它生成修復。如果輸出不完整，它生成下一步。這創建了一個自我修正迴圈。

### 程式碼範例：程式碼執行代理程式

```python
class CodeExecutionAgent:
    def __init__(self, llm_client, sandbox=None):
        self.llm = llm_client
        self.sandbox = sandbox  # None = unsandboxed (host)
        self.history = []

    async def run(self, task: str) -> str:
        self.history.append({"role": "user", "content": task})
        for iteration in range(10):  # Max 10 code-execute cycles
            response = await self.llm.generate(messages=self.history)
            code = extract_code_block(response)
            if not code:
                return response  # No code = final answer
            if not self.sandbox and not await user_approves(code):
                return "Execution cancelled by user."
            result = await (self.sandbox or LocalExecutor()).run(code, timeout=30)
            self.history.append({"role": "assistant", "content": response})
            self.history.append({"role": "user",
                "content": f"stdout: {result.stdout}\nstderr: {result.stderr}"})
        return "Max iterations reached."
```

### 何時使用此模式

- 資料分析和視覺化任務
- 系統管理和 DevOps 自動化
- 檔案處理和轉換
- 任何使用者描述「什麼」而代理程式想出「如何」的任務

### 權衡

| 優勢 | 劣勢 |
|-----------|--------------|
| 極度靈活 | 如果非沙盒化則有安全風險 |
| 透過觀察迴圈自我修正 | 模型可能生成危險程式碼 |
| 可與本地模型離線工作 | 需要使用者評估程式碼（或信任） |
| 需要時可完整存取系統 | 非確定性（相同提示，不同程式碼） |

---

## 模式 4：多代理程式工具協調

不是一個擁有許多工具的代理程式，而是多個專業化代理程式，每個擁有自己的工具子集。協調器將任務路由到正確的代理程式。這是代理程式的「微服務革命」。

### 架構

```
  [User Request]
       |
       v
  [ORCHESTRATOR] (Frontier model: Claude Opus, GPT-4o)
  Analyzes task, selects agent, routes and waits
       |
  +----+----+----+
  |         |         |
  v         v         v
[Code Agent]  [Data Agent]  [Web Agent]
 bash, edit,   SQL, plot,    fetch, scrape,
 git           csv            browse
  |         |         |
  v         v         v
[Sandbox]  [Sandbox]  [Sandbox]
(Docker)   (Docker)   (Docker)
```

### 協調策略

**1. 基於路由器的（最簡單）**：協調器是一個分類器。它查看使用者的訊息，選擇正確的專業代理程式，並轉發整個任務。沒有代理程式間通訊。

**2. Plan-and-Execute**：規劃模型（前沿級）將任務分解為子任務，並將每個分配給適當的專業代理程式。子任務結果由規劃者聚合。基準測試顯示比順序 ReAct 高 92% 任務完成率，快 3.6 倍。

**3. 階層式**：高層級代理程式向低層級代理程式分配工作，低層級代理程式可能進一步委派。這反映了組織結構，適用於複雜專案。

**4. 協作式（點對點）**：代理程式可以直接相互通訊，共享觀察並請求協助。這是最複雜的模式，但能很好地處理緊急任務。

### 成本優化：Plan-and-Execute 的優勢

```
Traditional: [Frontier Model] handles all steps       Cost: $1.00/task

Plan-and-Execute:
  [Frontier Model] plans (1 call)                     Cost: $0.05
  [Small Model] executes steps 1-3                    Cost: $0.03
  [Frontier Model] aggregates (1 call)                Cost: $0.05
                                                      Total: $0.13/task
                                                      Savings: ~87%
```

2026 年的趨勢是將代理程式成本優化作為一等考量，類似於雲端成本優化在微服務時代變得必不可少的方式。

---

## 沙盒化與非沙盒化執行

這是任何工具使用代理程式最重要的架構決策。

### 比較

```
  UNSANDBOXED (Host Access)              SANDBOXED (Isolated)
  +------------------------+             +------------------------+
  | LLM output executes    |             | LLM output executes    |
  | directly on host OS     |             | inside Docker/VM/E2B   |
  |                        |             |                        |
  | Risk: rm -rf /         |             | Isolated filesystem,   |
  | Risk: data exfiltration|             | network, processes     |
  |                        |             |                        |
  | Used by: OpenClaw,     |             | Used by: OpenHands,    |
  | Open Interpreter,      |             | OpenAI Codex, Jules,   |
  | Claude Code (default)   |             | Cursor Background Agents|
  +------------------------+             +------------------------+
```

### 沙盒實作選項

| 技術 | 隔離等級 | 啟動時間 | 使用案例 |
|------------|----------------|-------------|----------|
| Docker | 程序 + 檔案系統 | 1-5 秒 | 大多數代理程式沙盒（OpenHands） |
| Firecracker | 完整 VM（microVM） | ~125ms | 高安全性、多租戶 |
| gVisor | 核心層級 | ~200ms | Google Cloud Run |
| E2B | 雲端沙盒 | 2-3 秒 | 遠端代理程式執行 |
| WebAssembly | 語言層級 | <50ms | 基於瀏覽器的執行 |

### 2026 年共識

預設沙盒化，帶逃生口。OpenClaw 安全危機（135,000 個暴露在公共網路上的實例）已使產業認真對待這一點。新的生產代理程式預計預設提供沙盒化。非沙盒化執行保留用於單一使用者、受監督的環境。

---

## 跨工具呼叫的狀態管理

代理程式需要在工具呼叫之間維持狀態。策略取決於代理程式的生命週期和使用案例。

### 狀態管理模式

| 模式 | 生命週期 | 儲存 | 使用者 |
|---------|-----------|---------|---------|
| **對話狀態** | 短暫（單一對話） | 訊息陣列 | 大多數基於 API 的代理程式 |
| **對話狀態** | 每對話（工作目錄、開啟的檔案） | Docker 容器 / 暫存目錄 | OpenHands、Claude Code |
| **持久化狀態** | 跨對話（天、週） | 資料庫、檔案、Markdown | OpenClaw（Memories/）、CLAUDE.md |
| **環境狀態** | 外部（真理來源） | Git 儲存庫、資料庫、檔案系統 | Claude Code（git 狀態）、CI/CD |

### 實作：對話狀態

```python
class AgentSession:
    """Manages state across tool calls within a single session."""
    def __init__(self):
        self.conversation: list[dict] = []
        self.working_dir: str = tempfile.mkdtemp()
        self.open_files: dict[str, str] = {}  # path -> content cache
        self.tool_call_count: int = 0

    def add_tool_result(self, tool_name: str, args: dict, result: dict):
        self.tool_call_count += 1
        self.conversation.append({"role": "tool", "tool_name": tool_name,
            "args": args, "result": result, "timestamp": time.time()})
        # Update derived state from side effects
        if tool_name == "write_file":
            self.open_files[args["path"]] = args["content"]

    def get_context_for_llm(self, max_tokens: int = 100_000) -> list[dict]:
        """Return conversation history, compressed if over budget."""
        if estimate_tokens(self.conversation) < max_tokens:
            return self.conversation
        return self._compress_history(max_tokens)  # Summarize old results
```

---

## 錯誤處理與重試模式

工具呼叫會失敗。網路超時。API 返回錯誤。程式碼拋出異常。生產代理程式需要系統化的錯誤處理。

### 錯誤分類

| 錯誤類型 | 範例 | 策略 |
|-----------|----------|----------|
| **暫時性** | 網路超時、速率限制、503 | 指數退避重試（最多 3 次） |
| **輸入** | 無效參數、錯誤格式 | 將錯誤提供給 LLM，讓它修正參數 |
| **許可** | 認證失敗、存取被拒絕 | 報告給使用者，不重試 |
| **邏輯** | 錯誤工具、不可能操作 | 將錯誤提供給 LLM，讓它重新規劃 |
| **災難性** | OOM、沙盒崩潰、無限迴圈 | 中止、報告、清理資源 |

### 重試模式實作

```python
class ToolExecutor:
    MAX_RETRIES = 3

    async def execute_with_retry(self, tool_name: str, args: dict) -> dict:
        for attempt in range(self.MAX_RETRIES):
            try:
                result = await self.call_tool(tool_name, args)
                if not result.get("error"):
                    return result  # Success
                error_type = classify_error(result["error"])
                if error_type == "transient":
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                elif error_type == "input":
                    return {"error": result["error"], "fix_hint": "Adjust args"}
                elif error_type == "permission":
                    return {"error": result["error"], "action": "Report to user"}
                else:  # catastrophic
                    await self.cleanup_sandbox()
                    return {"error": "Fatal error. Task aborted."}
            except TimeoutError:
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
        return {"error": f"Failed after {self.MAX_RETRIES} retries"}
```

### 自我修正迴圈

2026 年最強大的錯誤處理模式。代理程式觀察自己的失敗並自主修正它們：

```
LLM generates code/tool call
  --> Execute --> Success? -- YES --> Return result
                     |
                     NO
                     |
                     v
              Feed error + stderr to LLM --> LLM generates fix --> Execute again
              (max 5 corrections to prevent infinite loops)
```

這是 Claude Code、OpenHands 和 Cline 處理測試失敗的方式：執行測試、看失敗、編輯程式碼、重新執行測試、重複直到綠燈。

---

## MCP 整合模式

MCP 已成為 2026 年工具整合的標準協定。以下是將 MCP 整合到代理程式架構中的關鍵模式。

### 模式 A：直接 MCP 連接

```
[Agent (Client)] <-- stdio / HTTP --> [MCP Server]
```

最簡單的模式。一個代理程式、一個伺服器。用於單一用途工具（資料庫、檔案系統）。

### 模式 B：多伺服器扇出

```
                  +--> [GitHub MCP]
[Agent (Client)]--+--> [Postgres MCP]
                  +--> [Slack MCP]
```

代理程式同時連接到多個 MCP 伺服器。工具結構描述合併為一個清單。由 Claude Code 和多工具助理使用。

### 模式 C：MCP 閘道（企業）

```
[Agent 1] --+                          +--> [GitHub MCP]
[Agent 2] --+--> [MCP Gateway]  --+--> [Postgres MCP]
[Agent 3] --+    (Auth, Rate Limit,    +--> [Slack MCP]
                  Audit, Route)
```

中央閘道處理認證、速率限制和稽核日誌。代理程式僅與閘道進行認證。用於企業和多租戶部署。

### MCP 路線圖缺口

截至 2026 年 5 月的當前 MCP 規範缺少三個關鍵的生產原語：

1. **身份傳播**：沒有標準化方式將使用者身份從客戶端傳遞到伺服器。閘道模式是一種變通方法。
2. **自適應工具預算**：沒有協定級支援來限制每個工具呼叫的 token/成本消耗。
3. **結構化錯誤語義**：沒有標準錯誤碼或錯誤類別。每個伺服器定義自己的錯誤格式。

這些在 2026 年路線圖上但尚未批准。

---

## 架構決策樹

使用此決策樹為你的使用案例選擇正確的模式：

```
Does the target system have an API?
 +-- YES --> Pattern 1 (Tool Calling). Wrap as MCP server. Fastest, most reliable.
 +-- NO  --> Does the task require GUI interaction?
              +-- YES --> Pattern 2 (Vision-Based). Sandbox in VM. Accept latency.
              +-- NO  --> Is the task primarily code/data work?
                           +-- YES --> Pattern 3 (Code Exec). Sandbox if multi-tenant.
                           +-- NO  --> Complex enough for multiple specialists?
                                        +-- YES --> Pattern 4 (Multi-Agent Orch.)
                                        +-- NO  --> Pattern 1 with custom tool.
```

### 混合架構

在實踐中，生產系統結合模式。Claude Code 使用：
- 模式 1（工具呼叫）用於檔案操作和 git
- 模式 2（基於視覺）用於電腦使用功能
- 模式 3（程式碼執行）用於 bash 和測試執行
- 模式 4（多代理程式）用於子代理程式生成

關鍵是預設使用最簡單的模式（函式呼叫），只有在使用案例需要時才增加複雜性。

---

## 系統設計面試切入點

在面試中討論工具使用架構時，圍繞這五個維度組織你的答案：

### 1. 模式選擇

首先確定哪種模式適合：「目標系統有一個 REST API，所以我將使用帶有 MCP 伺服器包裝 API 的函式/工具呼叫模式。」這表明你理解了決策樹。

### 2. 沙盒邊界

始終解決安全問題：「對於多租戶部署，我將在 Docker 容器中隔離每個使用者的代理程式對話，沒有對內部服務的網路存取。MCP 伺服器在沙盒外運行，調解所有外部呼叫。」

### 3. 狀態策略

解釋如何管理狀態：「我將使用 Docker 容器內的對話狀態進行工作檔案，以及環境狀態（git 儲存庫）作為真理來源。此使用案例不需要跨對話的持久化代理程式記憶體。」

### 4. 錯誤預算

討論失敗模式：「工具呼叫可能因暫時性錯誤而失敗（帶退避的重試）、輸入錯誤（讓 LLM 自我修正）或許可錯誤（呈現給使用者）。我將最多設定 5 次自我修正嘗試，然後升級。」

### 5. 成本模型

解決經濟問題：「對於協調器，我將使用 Plan-and-Execute 模式：Opus 規劃任務，Haiku 執行每個步驟。與使用 Opus 處理一切相比，這降低成本約 87%。」

---

## 面試問題

### Q：設計一個讓客服代理程式使用 Zendesk、Salesforce 和內部知識庫中的資料回答問題的系統。

**強而有力的回答：**
帶三個 MCP 伺服器（每個資料來源一個）的模式 1（函式/工具呼叫）。使用動態清單的多伺服器扇出模式，這樣每個查詢只載入相關工具。對於生產，添加 MCP 閘道來處理每個資料來源的 OAuth、速率限制（對於 Salesforce API 限制至關重要）和稽核日誌。狀態是短暫的——客戶支援不需要跨對話記憶體。

### Q：你如何防止 AI 代理程式透過工具呼叫造成損害？

**強而有力的回答：**
跨五層進行深度防禦：(1) 帶拒絕模式的結構約束（拒絕 `DROP TABLE` 等的正則表達式）。(2) 破壞性操作的許可閘道——Claude Code 的允許/拒絕規則是一個很好的模型。(3) 沙盒隔離（帶唯讀掛載的 Docker，無出站網路）。(4) Token 和成本上限以防止失控迴圈。(5) 透過 MCP 閘道模式的稽核追蹤。沒有單一層是足夠的——模型可能產生通過驗證的幻覺參數（需要沙盒），沙盒無法防止透過允許路徑的滲透（需要稽核日誌）。

### Q：解釋基於視覺的電腦使用與基於 API 的工具呼叫之間的權衡。

**強而有力的回答：**
API 方式更快（每步驟 50-200ms 對比 1-3 秒）、更便宜（文字對比圖像 tokens）、更可靠（確定性對比座標點擊），更容易測試。當 API 存在時始終首選它。基於視覺是沒有 API 的應用程式、舊版系統或多應用程式工作流程的備選。2026 年的 Zoom Action 減輕了密集 UI 上的錯誤點擊。最佳實踐：API 呼叫用於有 API 支援的 80% 任務，基於視覺用於剩餘的 20%。

---

## 參考文獻

- Anthropic. "Computer Use Tool Documentation" (2024-2026)
- Anthropic. "Model Context Protocol Specification" (2025-2026)
- MCP 2026 Roadmap. "Transport Evolution, Agent Communication, Governance" (2026)
- IBM Developer. "MCP Architecture Patterns for Multi-Agent AI Systems" (2026)
- Google Cloud. "Choose a Design Pattern for Your Agentic AI System" (2025-2026)
- Microsoft Azure. "AI Agent Orchestration Patterns" (2025-2026)
- OpenHands Documentation. "Runtime Architecture" (2025-2026)
- OpenClaw Documentation. "Architecture and SOUL.md Guide" (2025-2026)
- Open Interpreter GitHub Repository (2024-2026)
- ArXiv 2603.13417. "Design Patterns for Deploying AI Agents with MCP" (2026)

---

*上一章：[工具使用與電腦代理程式全景](01-tool-use-landscape.md)*
*下一章：[案例研究](../16-case-studies/)*
