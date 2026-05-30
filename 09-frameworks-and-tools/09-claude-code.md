# Claude Code：自主程式設計代理

Claude Code 是 Anthropic 的**終端原生自主程式設計代理**。與建議補全的 IDE 外掛不同，Claude Code 作為全端軟體工程師：閱讀您的程式碼庫、編輯檔案、執行命令、執行測試，並反覆運算直到任務完成。

## 目錄

- [Claude Code 是什麼](#what-it-is)
- [核心架構](#architecture)
- [核心工具](#tools)
- [CLAUDE.md 資清單模式](#claude-md)
- [執行 Claude Code](#running)
- [子代理和平行處理](#subagents)
- [自訂 MCP 整合](#mcp-integration)
- [安全性和許可模型](#safety)
- [生產使用：CI 管線](#production)
- [比較：Claude Code 對比替代方案](#comparison)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## Claude Code 是什麼

Anthropic 於 2025 年初發布，Claude Code 是：

- **CLI 工具**：終端中的 `claude` 命令
- **MCP 原生代理**：使用 bash、text_editor 和 computer 工具
- **SDK**：可嵌入 Python/TypeScript 應用程式
- **不只是一個聊天機器人**：它自主規劃、實現和驗證

```
# 安裝
pip install claude-code  # 或：npm install -g @anthropic-ai/claude-code

# 互動式執行
claude

# 無頭執行（用於 CI）
claude -p "為 src/utils.py 中的所有函式新增單元測試" --output-format json
```

**與 Copilot/Cursor 的關鍵差異：**
- Copilot/Cursor：建議您接受或拒絕的程式碼
- Claude Code：**自主實現整個任務**，執行測試來驗證

---

## 核心架構

```
┌─────────────────────────────────────────────────────────┐
│                   CLAUDE CODE ARCHITECTURE               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  User Request                                           │
│       ↓                                                 │
│  ┌─────────────┐    ┌──────────────┐                   │
│  │  Claude 3.7 │    │  CLAUDE.md   │                   │
│  │   Sonnet    │ ←  │  (manifest)  │                   │
│  │ (Extended   │    └──────────────┘                   │
│  │  Thinking)  │                                       │
│  └──────┬──────┘                                       │
│         │ Tool calls                                    │
│         ↓                                               │
│  ┌──────────────────────────────────────┐              │
│  │           TOOL LAYER                 │              │
│  │  ┌─────────┐ ┌───────────┐ ┌──────┐ │              │
│  │  │  bash   │ │text_editor│ │  MCP │ │              │
│  │  └────┬────┘ └─────┬─────┘ └──┬───┘ │              │
│  └───────┼────────────┼──────────┼─────┘              │
│          │            │          │                      │
│   Shell cmds     File edits    Custom tools             │
│   (test, lint,   (read/write)  (DB, APIs,               │
│    git, build)                  internal)               │
└─────────────────────────────────────────────────────────┘
```

Claude Code 使用 **Claude 3.7 Sonnet** 作為其骨幹模型，預設為複雜規劃任務啟用延伸思考。

---

## 核心工具

Claude Code 有三個原生工具並支援自訂 MCP 工具：

### 1. `bash` — 殼層執行

```python
# Claude 在內部呼叫這個：
bash(command="pytest tests/ -v --tb=short", timeout=60)
# 返回：stdout, stderr, exit_code
```

**Claude 用它做的事：**
- 執行測試套件（`pytest`、`jest`、`cargo test`）
- Git 操作（`git diff`、`git commit`、`git log`）
- 建置命令（`npm build`、`make`、`docker build`）
- 套件安裝（`pip install`、`npm install`）

bash 工作階段**在回合之間持續** — 環境變數和工作目錄在工作階段內保留。

### 2. `text_editor` — 檔案操作

```python
# 讀取檔案
text_editor(command="view", path="/project/src/auth.py")

# 在檔案中查找
text_editor(command="view", path="/project/src/auth.py", view_range=[1, 50])

# 編輯（精準替換）
text_editor(
    command="str_replace",
    path="/project/src/auth.py",
    old_str="def authenticate(user, password):",
    new_str="def authenticate(user: str, password: str) -> AuthResult:"
)

# 建立新檔案
text_editor(command="create", path="/project/tests/test_auth.py", file_text="...")
```

**為何精準替換勝過重寫：**
- 保留檔案上下文
- 減少幻覺（僅更改需要更改的內容）
- 實現原子性、可審查的差異

### 3. `computer` — GUI 自動化（可選）

完整桌面控制（螢幕截圖、鼠标、鍵盤）— 用於瀏覽器測試和 UI 驗證。需要沙盒環境。

---

## CLAUDE.md 資清單模式

`CLAUDE.md` 檔案是**使用 Claude Code 時最重要的模式**。它將持久的專案上下文注入每個 Claude Code 工作階段。

```markdown
# CLAUDE.md — 專案：電子商務 API

## 架構
- Python 3.11 FastAPI 後端
- PostgreSQL 15 搭配 Alembic 遷移
- Redis 用於工作階段快取
- 所有 API 回應必須是 Pydantic 模型

## 測試命令
- 執行所有測試：`pytest tests/ -v`
- 執行單一測試：`pytest tests/test_auth.py::test_login -v`
- Lint：`ruff check . --fix`
- 型別檢查：`mypy src/`

## 程式碼標準
- 始終新增型別提示
- 絕不使用 `global` 變數
- 所有資料庫查詢透過 SQLAlchemy ORM，從不 raw SQL
- 新功能需要覆蓋率 >80% 的測試

## 禁止模式
- 不要使用 `os.system()` — 使用 `subprocess.run()`
- 不要提交機密 — 使用環境變數
- 不要修改 `alembic/versions/` — 建立新遷移

## 架構決策
- 認證：JWT token，1 小時過期，刷新 token 模式
- 錯誤：始終返回 RFC 7807 Problem Details 格式
- 日誌：structlog 搭配 JSON 輸出，始終包含 request_id
```

**巢狀 CLAUDE.md 檔案：**
```
project/
  CLAUDE.md          # 全域專案規則
  src/
    auth/
      CLAUDE.md      # auth 特定規則（更嚴格的安全）
    payments/
      CLAUDE.md      # 支付特定規則（PCI 合規注意事項）
```

Claude 在目錄中工作時自動閱讀最近的 CLAUDE.md。

---

## 執行 Claude Code

### 互動模式

```bash
# 啟動工作階段（自動閱讀 CLAUDE.md）
claude

# 指定模型
claude --model claude-3-7-sonnet-20250219

# 指定 MCP 配置
claude --mcp-config .claude/mcp.json
```

### 無頭模式（用於腳本）

```bash
# 單一任務，JSON 輸出
claude -p "修復 src/ 中的所有型別錯誤" \
  --output-format json \
  --max-turns 20

# 從檔案 pipe
echo "重構 src/utils.py 使用 async/await" | claude -p -

# 串流輸出
claude -p "為所有 API 端點新增日誌" --output-format stream-json
```

### Python SDK

```python
import asyncio
from claude_code_sdk import query, ClaudeCodeOptions

async def run_coding_task(task: str) -> str:
    options = ClaudeCodeOptions(
        max_turns=30,
        allowed_tools=["bash", "str_replace_based_edit_tool"],
        system_prompt_suffix="變更後始終執行測試。",
    )
    
    messages = []
    async for message in query(prompt=task, options=options):
        messages.append(message)
    
    return messages[-1].content[0].text

result = asyncio.run(run_coding_task(
    "為 src/api/ 中的所有 POST 端點新增輸入驗證"
))
```

---

## 子代理和平行處理

Claude Code 支援**子代理派遣**用於大型程式碼庫：

```
Main Claude Code session
    ↓
"此程式碼庫有 5 個模組。我將為每個產生子代理。"
    ├── Sub-agent 1: 修復 auth 模組測試
    ├── Sub-agent 2: 為 utils/ 添型式別提示
    ├── Sub-agent 3: 將 payments 遷移到 async
    └── Sub-agent 4: 更新 API 文件
```

每個子代理平行執行，然後主代理審查並合併結果。

**何時使用子代理：**
- 程式碼庫 >50K 行
- 平行獨立變更（無共享狀態）
- 模組級重構任務

---

## 自訂 MCP 整合

Claude Code 從 `~/.claude/config.json` 或 `.claude/mcp.json` 讀取 MCP 伺服器：

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "description": "Live library documentation"
    },
    "postgres": {
      "command": "uvx",
      "args": ["mcp-server-postgres"],
      "env": {"DATABASE_URL": "postgresql://localhost/myapp"},
      "description": "Schema-aware database queries"
    },
    "filesystem": {
      "command": "uvx",
      "args": ["mcp-server-fs"],
      "description": "Safe file operations with权限 tracking"
    }
  }
}
```

---

## 安全性和許可模型

### 許可配置

```yaml
permissions:
  # 允許的命令（明確列表）
  allow:
    - "pytest * -v"
    - "ruff check * --fix"
    - "mypy src/"
    - "git add *"
    - "git commit *"
  
  # 禁止的命令
  deny:
    - "rm -rf *"
    - "pip install *"
    - "curl *"
```

### 生產安全檢查清單

- [ ] 在隔離的 Docker 容器中執行
- [ ] 網路存取：無（除非明確需要）
- [ ] 許可清單：僅允許已知的測試/lint 命令
- [ ] 人類審查：所有 PR 都需要人工審查
- [ ] secret 掃描：CI 中的 gitleaks/trufflehog

---

## 生產使用：CI 管線

### GitHub Actions 範例

```yaml
name: AI Code Review

on:
  issue_comment:
    types: [created]

jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.issue.comment.head_ref }}
      
      - name: Run Claude Code
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          pip install claude-code
          
          ISSUE_BODY="${{ github.event.issue.body }}"
          
          claude -p "Fix the following bug: $ISSUE_BODY
          
          Rules:
          - Read the relevant files first
          - Make minimal changes
          - Run tests and verify they pass
          - Do not change unrelated code
          " --output-format json --max-turns 15 > result.json
      
      - name: Create Pull Request
        uses: peter-evans/create-pull-request@v5
        with:
          title: "AI Fix: ${{ github.event.issue.title }}"
          body: "Automated fix by Claude Code"
          branch: "ai-fix/${{ github.event.issue.number }}"
```

### CI 成本模型

| 任務類型 | 平均回合數 | 平均 Token 數 | 預估成本 |
|-----------|-----------|------------|----------------|
| 小型錯誤修正 | 8 | 15K | $0.23 |
| 測試生成 | 12 | 25K | $0.38 |
| 功能實現 | 20 | 50K | $0.75 |
| 大型重構 | 30 | 100K | $1.50 |

*每天 100 次 CI 執行：根據任務混合，約 $75-150/天。*

---

## 比較：Claude Code 對比替代方案

| 功能 | Claude Code | Cursor/Windsurf | Cline | OpenHands |
|---------|-------------|-----------------|-------|-----------|
| **介面** | CLI + SDK | IDE（VS Code 分叉） | VS Code 擴充功能 | Web UI + CLI |
| **模型** | 僅 Claude | 任何（GPT、Claude、Gemini） | 任何 | 任何 |
| **自主性** | 完整 | 中（需要點擊） | 完整 | 完整 |
| **CI/無頭** | ✅ 原生 | ❌ | ✅ | ✅ |
| **MCP 支援** | ✅ 原生 | ✅ | ✅ | ✅ |
| **CLAUDE.md** | ✅ | ❌（類似：.cursorrules） | ❌ | ❌ |
| **開源** | ❌ | ❌ | ✅ | ✅ |
| **最適合** | 後端開發人員、CI/CD | UI/前端開發人員、視覺 | 任何開發人員 | 自託管團隊 |

### SWE-bench 驗證分數（2026 年 5 月）

| 代理 | 分數 | 備註 |
|-------|-------|-------|
| GPT-5.5（原始模型領導者） | 88.7% | SWE-Bench 驗證排行榜第一名 |
| Claude Opus 4.7（原始模型） | 87.6% | SWE-Bench Pro 領先者 64.3% |
| Claude Code（Opus 4.7 / Sonnet 4.6） | ~87% | Anthropic 官方代理 |
| OpenHands + Claude Sonnet 4.6 | ~75% | 開源框架 |
| Aider + Claude Sonnet 4.6 / GPT-5.5 | ~74% | 開源 CLI |
| Devin（商業） | ~65% | Cognition AI 產品 |
| SWE-agent + GPT-5.5 | ~55% | Princeton 研究基準 |

---

## 面試題目

### Q：Claude Code 與 GitHub Copilot 有何不同？

**強烈回答：**
Copilot 是一個**補全工具** — 它在您輸入時預測接下來的幾行程式碼。Claude Code 是一個**自主代理** — 您給它一個任務（例如「為此 API 新增認證」），它閱讀程式碼庫、規劃實現、編輯多個檔案、執行測試、修正失敗，只有在測試通過時才完成。體驗根本上不同：Copilot 幫助您更快地編碼；Claude Code *為*您編碼，而您審查輸出。

### Q：什麼是 CLAUDE.md，為何它至關重要？

**強烈回答：**
CLAUDE.md 就像專門為 AI 同事寫的 `README`。沒有它，Claude Code 將您的專案視為通用的 Python/JS 專案。有了它，Claude 知道：您的確切測試命令、您的禁止模式（無 raw SQL，使用 ORM）、您的架構決策（JWT 認證、特定錯誤格式）和您的程式碼標準。它將通用代理轉換為**專案專家**。我用過的好的 CLAUDE.md 將任務完成速度提高 2-3 倍，並減少 60% 的錯誤。

### Q：如何在生產 CI 中安全地執行 Claude Code？

**強烈回答：**
三層：
1. **沙箱**：在沒有外部網路存取的 Docker 容器中執行 Claude Code。只有 git 存放庫和測試執行器可存取。
2. **許可 allow-list**：使用許可配置將精確允許的 bash 命令列入白名單（測試執行器、linter）並阻止破壞性操作（rm -rf、pip install 未經審查）。
3. **人類閘道**：Claude Code 輸出一個帶有差異的分支。人類在 PR 中審查差異並合併。Claude 永遠不直接合併到 main。這將人類判斷保持在最終決策的迴路中。

### Q：如何處理高流量 CI 的 Claude Code 成本？

**強烈回答：**
我用三種方式優化：
1. **任務範圍**：Claude Code 對於獨立、有界限的任務（錯誤修正、測試生成）具有成本效益。我不會將其用於開放式探索 — 這仍然比人類便宜。
2. **最大回合數**：設定 `max_turns=15` 可防止在循環推理中燃燒 $10+ 的失控工作。
3. **模型路由**：對於簡單的錯誤修正（語法錯誤、明顯的錯字），我透過 SDK 使用 Claude 3.5 Haiku — 便宜 5 倍。對於架構重構，我使用帶有延伸思考的 Claude 3.7 Sonnet。

---

## 參考文獻

- Anthropic。〈Claude Code：構建代理程式設計體驗〉（2025）— https://docs.anthropic.com/claude-code
- Anthropic。〈Claude Code SDK 文件〉 — https://github.com/anthropics/claude-code
- Anthropic。〈CLAUDE.md 最佳實踐〉 — https://docs.anthropic.com/claude-code/settings#claudemd
- SWE-bench 驗證排行榜 — https://www.swebench.com/

---

*下一篇：[OpenCoder / AI 程式設計代理景觀](10-opencoderguide.md)*