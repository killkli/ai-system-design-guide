# 建構工具使用代理程式

本章節涵蓋工具使用代理程式的實務工程：設計 LLMs 可可靠呼叫的工具結構描述、建構托管這些工具的 MCP 伺服器、將工具組合成工作流程，以及測試整個系統。這些是將演示與生產部署分開的模式。

## 目錄

- [為 LLMs 設計工具結構描述](#designing-tool-schemas-for-llms)
- [MCP 伺服器建立](#mcp-server-creation)
- [工具註冊與發現](#tool-registration-and-discovery)
- [輸入驗證與輸出格式化](#input-validation-and-output-formatting)
- [工具組合：連結工具](#tool-composition-chaining-tools)
- [建構自訂代理程式技能](#building-custom-agent-skills)
- [建立函式呼叫端點](#creating-function-calling-endpoints)
- [測試工具使用代理程式](#testing-tool-use-agents)
- [工具使用的可觀測性](#observability-for-tool-use)
- [常見錯誤與反模式](#common-mistakes-and-anti-patterns)
- [工具版本管理與向後相容](#tool-versioning-and-backwards-compatibility)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 為 LLMs 設計工具結構描述

工具結構描述是 LLM 與你的系統之間的合約。良好的結構描述減少了幻覺參數、防止誤用，並使模型的工具選擇更可靠。

### 良好工具定義的結構

```json
{
  "name": "search_customers",
  "description": "Search for customers by name, email, or account ID. Returns up to 10 matching customer records. Use this when the user asks about a specific customer. Do NOT use this for aggregate queries like 'how many customers do we have'.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search term: customer name, email address, or account ID (e.g., 'john@acme.com' or 'ACC-12345')"
      },
      "limit": {
        "type": "integer",
        "description": "Max results to return (1-10). Default: 5",
        "default": 5,
        "minimum": 1,
        "maximum": 10
      }
    },
    "required": ["query"]
  }
}
```

### 結構描述設計規則

**1. 名稱精確**：使用 `verb_noun` 格式。`search_customers` 而非 `search` 或 `customer_tool`。

**2. 描述何時不使用**：模型需要負面範例。「不用於聚合查詢」比僅列出有效用途更能防止誤用。

**3. 給出參數範例**：在描述字串中包含範例值。模型使用這些來校準其輸出。

**4. 約束範圍**：使用 `minimum`、`maximum`、`enum` 和 `pattern` 在結構描述層級而非處理常式中防止無效參數。

**5. 保持工具原子化**：一個工具做一件事。避免建立、讀取、更新和刪除的 `manage_customer` 工具——分成四個工具。

**6. 使用 `strict: true`**：Anthropic 的嚴格模式保證模型輸出與結構描述完全匹配。在生產中始終啟用它。

```
Good Tool Design:                    Bad Tool Design:

+-------------------+                +-------------------+
|| search_customers  |                | customer_tool     |
|| - query (string)  |                | - action (string) |
|| - limit (int 1-10)|                | - data (object)   |
+-------------------+                | - options (any)   |
|| create_customer   |                +-------------------+
|| - name (string)   |                "action" can be
|| - email (string)  |                "search", "create",
+-------------------+                "update", "delete"
|| update_customer   |                => model confused,
|| - id (string)     |                   schema too loose,
|| - fields (object) |                   hard to validate
+-------------------+
```

---

## MCP 伺服器建立

MCP 伺服器是一個獨立的程序，向任何 MCP 相容用戶端（Claude、GPT、基於 Llama 的代理程式）暴露工具、資源和提示。你編寫伺服器一次，任何 LLM 都可以使用它。

### MCP 架構

```
+------------------+          JSON-RPC           +------------------+
||                  |  ========================>  |                  |
||   MCP Client     |                             |   MCP Server     |
||   (AI App)       |  <========================  |   (Your Code)    |
||                  |                             |                  |
||  - Claude Code   |  Transport:                 |  Exposes:        |
||  - Custom Agent  |  - stdio (local)            |  - Tools         |
||  - IDE Plugin    |  - Streamable HTTP (remote)  |  - Resources     |
||                  |                             |  - Prompts       |
+------------------+                             +------------------+
```

### TypeScript MCP 伺服器

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "customer-service", version: "1.0.0" });

server.tool(
  "search_customers",
  "Search customers by name, email, or ID. Returns up to 10 matches.",
  {
    query: z.string().describe("Search term: name, email, or account ID"),
    limit: z.number().min(1).max(10).default(5).describe("Max results"),
  },
  async ({ query, limit }) => ({
    content: [{ type: "text",
      text: JSON.stringify(await db.customers.search(query, limit), null, 2) }],
  })
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

### Python MCP 伺服器 (FastMCP)

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("customer-service")

@mcp.tool()
async def search_customers(query: str, limit: int = 5) -> str:
    """Search customers by name, email, or ID. Returns up to 10 matches.
    Args:
        query: Search term - customer name, email, or account ID
        limit: Max results to return (1-10, default 5)
    """
    return json.dumps(await db.customers.search(query, limit), indent=2)
```

兩個 SDK 遵循相同的模式：建立伺服器、使用類型結構描述註冊工具、連接傳輸。TypeScript SDK 使用 Zod 進行驗證；Python 使用類型提示和 docstring。

### 部署模式

| 模式 | 傳輸 | 使用案例 |
|------|-----------|----------|
| 本地 (stdio) | stdin/stdout 管道 | 桌面工具、IDE 外掛程式 |
| 遠端 (Streamable HTTP) | HTTP + SSE | 雲端服務、共享伺服器 |
| 混合 | 兩者 | 本地開發、遠端部署 |

---

## 工具註冊與發現

在生產中，代理程式需要動態發現可用工具，而不是對其進行硬編碼。

### 靜態註冊

在配置檔案中聲明 MCP 伺服器（例如 `claude_desktop_config.json`）。每個條目將伺服器名稱對應到命令、參數和可選環境變數。簡單但不靈活——每個伺服器在啟動時載入，無論相關性如何。

### 動態發現（工具搜尋）

Anthropic 的工具搜尋（2025）解決了結構描述過載問題。不是將 200 個工具結構描述載入上下文（會降低推理），而是代理程式發送輕量級搜尋查詢並僅接收 3-5 個相關工具結構描述。這使上下文視窗專注於推理而非解析未使用的結構描述。

### MCP 發現協定

MCP 用戶端透過標準 JSON-RPC 方法發現功能：`tools/list` 返回可用工具，`resources/list` 返回資料資源，`prompts/list` 返回提示模板。這使得無需硬編碼即可進行執行時發現。

---

## 輸入驗證與輸出格式化

### 輸入驗證層

```
+---------------------+
||  Schema Validation   |  <-- JSON Schema / Zod / Pydantic
||  (type, range, enum) |      Catches: wrong types, out-of-range
+----------+----------+
           |
           v
+---------------------+
||  Business Validation |  <-- Your handler code
||  (exists, permitted) |      Catches: invalid IDs, unauthorized
+----------+----------+
           |
           v
+---------------------+
||  Execution           |  <-- Actual operation
+---------------------+
```

始終在兩層進行驗證。結構描述驗證捕獲格式錯誤的輸入。業務驗證捕獲語義無效的輸入。

```python
@mcp.tool()
async def transfer_funds(
    from_account: str,
    to_account: str,
    amount: float
) -> str:
    """Transfer funds between accounts."""
    # Schema already enforced types via type hints

    # Business validation
    if amount <= 0:
        return "Error: Amount must be positive."
    if amount > 10000:
        return "Error: Transfers over $10,000 require manual approval."
    if from_account == to_account:
        return "Error: Cannot transfer to the same account."

    from_acct = await db.accounts.get(from_account)
    if not from_acct:
        return f"Error: Account {from_account} not found."

    # Execute
    result = await db.transfers.execute(from_account, to_account, amount)
    return f"Transferred ${amount:.2f}. Confirmation: {result.id}"
```

### 輸出格式化

當模型需要推理時返回結構化資料。當結果是最終的時返回人類可讀的文字。

```python
# Good: structured for further reasoning
return json.dumps({
    "customers": [
        {"id": "ACC-123", "name": "Jane Smith", "email": "jane@acme.com"},
        {"id": "ACC-456", "name": "John Doe", "email": "john@acme.com"}
    ],
    "total_matches": 2,
    "has_more": False
})

# Bad: unstructured blob
return "Found Jane Smith (ACC-123, jane@acme.com) and John Doe (ACC-456, john@acme.com)"
```

---

## 工具組合：連結工具

真實任務需要按順序呼叫的多個工具。有兩種組合模式：

### 模式 1：LLM 協調連結

LLM 根據先前的結果決定下一步呼叫哪個工具：

```
User: "Find customer Jane Smith and create a high-priority ticket for her billing issue"

Turn 1:  LLM -> search_customers("Jane Smith")
         Result: {"id": "ACC-123", "name": "Jane Smith", ...}

Turn 2:  LLM -> create_ticket("ACC-123", "Billing issue", "...", "high")
         Result: "Ticket TK-789 created."

Turn 3:  LLM -> "I found Jane Smith (ACC-123) and created ticket TK-789."
```

每個工具呼叫是一個單獨的 API 往返。模型在呼叫之間推理結果。

### 模式 2：程式化工具呼叫

Anthropic 的程式化工具呼叫（2025）讓模型編寫在單次往返中連結工具的程式碼：

```
LLM generates code:
  customer = search_customers("Jane Smith")
  if customer.results:
    ticket = create_ticket(customer.results[0].id, ...)
    return f"Created {ticket.id} for {customer.results[0].name}"
  else:
    return "Customer not found"
```

這作為單個 API 呼叫執行，將延遲從 3 次往返減少到 1 次。

### 模式 3：伺服器端組合

在 MCP 伺服器內部組合工具——單個 `resolve_customer_issue` 工具在內部呼叫搜尋和建立工單，對 LLM 隱藏多步驟邏輯。將此用於 LLM 不需要在步驟之間進行推理的固定、定義明確的工作流程。

### 何時使用每個

| 模式 | 延遲 | 靈活性 | 最適合 |
|---------|---------|-------------|----------|
| LLM 協調 | 高（N 次往返） | 非常高 | 複雜、分支邏輯 |
| 程式化 | 低（1 次往返） | 高 | 線性鏈接、批次 |
| 伺服器端 | 最低 | 低 | 固定、常見工作流程 |

---

## 建構自訂代理程式技能

代理程式技能（Anthropic，2025）是代理程式動態載入的指令、工具和資源的捆綁包。技能是一個資料夾：

```
my-skill/
  SKILL.md          # Instructions the agent loads into system prompt
  tools/            # MCP tool implementations
  resources/        # Data files, templates, schemas
  tests/            # Evaluation cases
```

在執行時，SkillManager 註冊可用技能並按需啟動它們——將技能的指令注入系統提示並将其工具添加到可用工具集中。這保持了基礎代理程式的輕量，同時實現深度專業化。

---

## 建立函式呼叫端點

要使你的 API 可被任何 LLM 呼叫，透過 FastAPI 搭配 Pydantic 模型暴露它。自動生成的 OpenAPI 規範（`/openapi.json`）兼作函式呼叫的工具結構描述。或者，將相同的邏輯包裝在 MCP 伺服器中，以直接整合 Claude、GPT 或其他 MCP 相容用戶端。

---

## 測試工具使用代理程式

### 三個測試層

```
+---------------------------+
||   Eval Suites             |  End-to-end: does the agent
||   (Agent + LLM + Tools)  |  complete the task?
+-------------+-------------+
              |
+-------------+-------------+
||   Integration Tests       |  Does tool X work correctly
||   (Tool + Dependencies)   |  with real DB / API?
+-------------+-------------+
              |
+-------------+-------------+
||   Unit Tests              |  Does validation logic
||   (Tool Logic Only)       |  handle edge cases?
+---------------------------+
```

### 工具的單元測試

使用模擬的依賴項隔離測試每個工具處理常式。覆蓋：輸入驗證邊界情況（範圍外值、缺失欄位）、錯誤訊息品質（是否引導模型恢復？）、輸出格式（有效 JSON、正確結構描述）。

### 代理程式行為的評估套件

建立 100+ 個帶預期結果的現實查詢資料集：

```python
eval_cases = [
    {
        "input": "Find Jane Smith's account and check her last payment",
        "expected_tools": ["search_customers", "get_payment_history"],
        "max_tool_calls": 5,
    },
    {
        "input": "What is the meaning of life?",
        "expected_tools": [],  # Should NOT call any tools
        "max_tool_calls": 0,
    },
]
```

對於每個案例，測量：工具選擇準確率（正確的工具？）、參數品質（正確的參數？）、任務完成率、效率（工具呼叫次數）。在每個模型版本變更和每個工具結構描述變更上運行評估。

---

## 工具使用的可觀測性

每個工具呼叫都應記錄：追蹤/跨距 ID、時間戳記、工具名稱、輸入參數、輸出大小、延遲、狀態、使用的模型、token 使用量和工作階段 ID。

### 關鍵指標

| 指標 | 測量內容 | 警報閾值 |
|--------|-----------------|-----------------|
| 工具呼叫成功率 | 返回有效結果的呼叫百分比 | < 95% |
| 工具選擇準確率 | 是否選擇了正確的工具？ | < 90% |
| 每任務平均工具呼叫數 | 工具使用效率 | > 2x 基線 |
| 每工具呼叫延遲 | 工具處理常式的回應時間 | > 5s (p99) |
| 幻覺參數 | 儘管有結構描述仍是無效參數 | > 2% |
| 每任務成本 | 總 LLM + 工具執行成本 | > 預算 |

### 追蹤架構

```
+-------------+     +----------------+     +--------------+
||  Agent      |---->|  Tool Handler  |---->|  Backend     |
||  (LLM call) |     |  (MCP Server)  |     |  (DB/API)    |
+------+------+     +--------+-------+     +------+-------+
       |                     |                     |
       v                     v                     v
+------+---------------------+---------------------+------+
||                    Trace Collector                       |
||              (OpenTelemetry / Langfuse)                  |
+---------------------------+------------------------------+
                            |
                            v
                   +--------+--------+
                   |   Dashboard     |
                   |   - Success %   |
                   |   - Latency     |
                   |   - Cost        |
                   +-----------------+
```

---

## 常見錯誤與反模式

| 反模式 | 問題 | 修復 |
|-------------|---------|-----|
| 工具過載 | 50+ 工具降低選擇準確率 | 動態發現，每回合載入 5-10 個 |
| 模糊描述 | 「處理客戶操作」——太模糊 | 包含何時使用、何時不使用、範例 |
| 上帝工具 | 一個帶 `action` 參數的工具做所有事情 | 拆分為原子工具，每個操作一個 |
| 缺少錯誤上下文 | 工具返回「錯誤」但沒有詳細資訊 | 可操作的訊息：「ACC-999 not found. Use search_customers...」 |
| 無結構輸出 | 工具返回模型必須解析的散文 | 返回 JSON 以便結構化推理 |
| 無冪等性 | `create_ticket` 被呼叫兩次會建立重複 | 接受冪等金鑰，創建前檢查 |
| 暴露內部 ID | 工具需要資料庫 UUID，模型不知道 | 接受人類可讀的識別符，內部解析 |
| 忽略速率限制 | 代理程式循環 100 次 API 呼叫，被節流 | 在處理常式中退避，返回「X 秒後重試」 |

---

## 工具版本管理與向後相容

隨著工具的發展，你必須維護依賴它們的代理程式的相容性。

**規則：**
1. **附加變更**（新的可選參數）：無需版本提升。舊呼叫仍然有效。
2. **破壞性變更**（重新命名、移除參數、改變語義）：使用新結構描述建立新工具名稱。保持舊工具運行並在其描述中新增「DEPRECATED: Use new_tool instead」。記錄每個棄用呼叫以進行監控。
3. **永不移除工具**，直到你驗證沒有活躍的代理程式依賴它。

---

## 面試問題

### Q：你需要讓 LLM 代理程式存取 200 個內部工具。你如何處理結構描述過載？

**強而有力的回答：**
我不會將所有 200 個工具結構描述載入上下文。相反，我會實施兩階段方法。首先是一個工具發現階段，代理程式描述它需要做什麼，輕量級搜尋（嵌入相似性或關鍵字匹配）返回 5-10 個最相關的工具結構描述。其次是一個工具執行階段，只有選定的工具包含在實際 LLM 呼叫的上下文中。

這反映了 Anthropic 的工具搜尋模式。發現步驟可以是單獨的、更便宜的 LLM 呼叫，甚至是非 LLM 搜尋。關鍵洞察是，與不相關工具結構描述使用的上下文視窗空間直接降低模型的推理品質。我會將工具選擇準確率作為關鍵指標進行測量——如果代理程式應該呼叫 `get_customer_by_id` 時卻呼叫了 `search_customers`，則需要調整發現階段。

對於 MCP 實現，我會將工具分組為特定領域的伺服器（客戶服務、帳單、分析），並僅連接與當前對話相關的伺服器。

### Q：為處理客戶支援的工具使用代理程式設計測試策略。

**強而有力的回答：**
我會在三層進行測試。首先是每個工具處理常式的單元測試：驗證輸入邊界情況、錯誤訊息和輸出格式。這些在每次提交時配合模擬依賴項在 CI 中運行。

其次是整合測試，驗證工具在真實（預備）資料庫上運行。例如，`create_ticket` 實際建立一條記錄，`search_customers` 返回它。這些捕獲工具和後端之間的結構描述漂移。

第三是評估套件，測試完整代理程式——LLM 加上工具。我會建立 100+ 個帶預期工具呼叫序列和輸出標準的現實客戶查詢資料集。評估測量工具選擇準確率（是否選擇了正確的工具？）、參數品質（參數是否正確？）、任務完成率（是否解決了問題？）和效率（花了多少工具呼叫？）。

我會在每個模型版本變更和每個工具結構描述變更上運行評估。結構描述變更後工具選擇準確率下降 2% 意味著描述需要修訂，而非模型。

---

## 參考文獻

- Anthropic. "Tool Use with Claude" API Documentation (2025)
- Model Context Protocol. "Build an MCP Server" (2025)
- MCP TypeScript SDK: github.com/modelcontextprotocol/typescript-sdk
- MCP Python SDK: github.com/modelcontextprotocol/python-sdk
- Anthropic. "Introducing Advanced Tool Use" (2025)
- Anthropic. "Agent Skills" Beta Documentation (2025)

---

*上一章：[電腦使用代理程式](04-computer-use-agents.md)*
