# OpenCoder：AI 程式設計代理景觀

AI 程式設計代理景觀已經爆發。本指南涵蓋開源權重程式設計模型、代理型 IDE、開源代理，以及如何為您的工程工作流程選擇正確的工具。

## 目錄

- [AI 程式設計景觀（2026）](#landscape)
- [開源權重程式設計模型](#models)
- [AI 原生 IDE](#ides)
- [開源程式設計代理](#agents)
- [基準測試深入探討](#benchmarks)
- [成本比較](#costs)
- [選擇指南](#selection)
- [生產架構](#production)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## AI 程式設計景觀（2026）

程式設計 AI 景觀有三個不同的層級：

```
┌─────────────────────────────────────────────────────────────┐
│                    AI CODING STACK (2026)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LAYER 3: CODING AGENTS (Autonomous, multi-turn)           │
│  ┌──────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │  Claude Code │ │  OpenHands │ │  Cline / Aider     │   │
│  │  (Anthropic) │ │  (Open)    │ │  (Open)            │   │
│  └──────────────┘ └────────────┘ └────────────────────┘   │
│                                                             │
│  LAYER 2: AI IDEs (Completion + editing, developer-in-loop)│
│  ┌──────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │    Cursor    │ │  Windsurf  │ │  GitHub Copilot    │   │
│  └──────────────┘ └────────────┘ └────────────────────┘   │
│                                                             │
│  LAYER 1: CODING MODELS (The brains behind everything)     │
│  ┌──────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │  Opus 4.7    │ │  GPT-5.5   │ │ DeepSeek V4 Pro    │   │
│  │  Sonnet 4.6  │ │ Gemini 3.1 │ │ Qwen 3.6 Coder     │   │
│  └──────────────┘ └────────────┘ └────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 開源權重程式設計模型

這些模型可以自託管、微調，並在不依賴任何 API 的情況下部署。

### Qwen2.5-Coder（阿里巴巴）

一個強大的開源程式設計模型系列。截至 2026 年 5 月，開源程式設計領導者是 Qwen 3.6 Coder 和 DeepSeek V4 Pro；Qwen 2.5 Coder 仍然是較小硬體上自託管部署的熱門選擇：

| 模型 | 參數 | 上下文 | HumanEval+ | 備註 |
|-------|------------|---------|------------|-------|
| Qwen2.5-Coder-32B-Instruct | 32B | 128K | 88.2% | 最佳開源程式設計模型 |
| Qwen2.5-Coder-7B-Instruct | 7B | 128K | 79.3% | 出色的小模型 |
| Qwen2.5-Coder-1.5B | 1.5B | 32K | 65.8% | 邊緣/裝置上使用 |

**優勢：**
- 在程式設計基準測試上表現強勁；在 SWE-bench 驗證上與前沿封閉模型競爭
- 支援 100+ 程式語言
- 出色的填充中間（FIM）補全
- Apache 2.0 授權 — 完全商業可用

```python
# 使用 vLLM 自託管
from vllm import LLM

model = LLM(
    model="Qwen/Qwen2.5-Coder-32B-Instruct",
    tensor_parallel_size=2,  # 2× A100 80GB
)
response = model.generate("def fibonacci(n: int) -> list[int]:")
```

### DeepSeek-Coder-V2（DeepSeek）

| 模型 | 參數 | 架構 | HumanEval+ |
|-------|------------|-------------|------------|
| DeepSeek-Coder-V2-Instruct | 236B (MoE) | MoE | 90.2% |
| DeepSeek-Coder-V2-Lite | 16B (MoE) | MoE | 81.1% |

**優勢：**
- MoE 架構 → 每個 token 僅啟動 21B 參數（高效）
- 在競技程式設計（CodeForces 問題）上表現強勁
- 開源權重；強大的中文語言支援

### StarCoder2（BigCode / Hugging Face）

| 模型 | 參數 | 上下文 | 備註 |
|-------|------------|---------|-------|
| StarCoder2-15B | 15B | 16K | 最佳中型開源程式設計 LM |
| StarCoder2-7B | 7B | 16K | 高效，80+ 語言 |
| StarCoder2-3B | 3B | 16K | 輕量，裝置上 |

**優勢：**
- 完全開源（BigCode OpenRAIL-M 授權）
- 出色用於 IDE 補全（低延遲）
- 強大的 Stack Overflow / GitHub 資料

### DeepSeek-R1-Distill（用於程式設計）

| 模型 | 參數 | Math/Code | 備註 |
|-------|------------|-----------|-------|
| DeepSeek-R1-Distill-Qwen-32B | 32B | 出色 | 推理蒸餾到較小模型 |
| DeepSeek-R1-Distill-Llama-8B | 8B | 良好 | 微型推理模型 |

**使用場景**：當您需要自託管規模的推理品質程式碼生成時。

### 開源模型選擇指南

```
簡單補全（需要 < 100ms 延遲）？
  → StarCoder2-3B 或 Qwen2.5-Coder-1.5B（本地，快速）

最佳品質自託管？
  → Qwen2.5-Coder-32B-Instruct（2× A100）

預算 < 1× A100 GPU？
  → Qwen2.5-Coder-7B-Instruct（1× RTX 4090 足夠）

需要推理 + 程式設計？
  → DeepSeek-R1-Distill-Qwen-32B

競技程式設計 / 演算法？
  → DeepSeek-Coder-V2 或 DeepSeek-R1
```

---

## AI 原生 IDE

### Cursor

**網站：** cursor.sh | **基底：** VS Code 分叉 | **定價：** $20/月 Pro

Cursor 是領先的 AI 原生 IDE。關鍵能力：

| 功能 | 描述 |
|---------|-------------|
| **Composer** | 多檔案代理編輯（Cursor 的 Claude Code 等價物） |
| **Ctrl+K** | 內聯程式碼生成 |
| **Tab** | 預測補全（比 Copilot 更聰明） |
| **@-mentions** | 附加檔案、URL、文件到上下文 |
| **.cursorrules** | 專案級 AI 指令（類似 CLAUDE.md） |
| **模型選擇** | GPT-5.5、Claude Sonnet 4.6 / Opus 4.7、Gemini 3.1 Pro、DeepSeek V4 Pro |

**最適合**：想要在熟悉 GUI 中進行代理編輯的前端/全端開發人員。

**限制**：閉源；您的程式碼被髮送到 Cursor 的伺服器（他們提供隱私模式）。

### Windsurf（by Codeium）

**網站：** codeium.com/windsurf | **基底：** VS Code 分叉 | **定價：** 免費層 + $15/月 Pro

Windsurf 透過**Flows** 進行差異化（不要與 CrewAI Flows 混淆）：

| 功能 | 描述 |
---------|-------------|
| **Cascade** | Windsurf 的代理編輯模式 |
| **Flows** | 確定性代理序列（代理 + 使用者和諧） |
| **模型選擇** | 任何：GPT-5.5、Claude Sonnet 4.6 / Opus 4.7、Gemini 3.1 Pro、DeepSeek V4 |
| **免費層** | 慷慨的免費額度 |

**最適合**：想要 Cursor 體驗但具有免費層和模型靈活性的團隊。

### GitHub Copilot（Microsoft/OpenAI）

| 功能 | 狀態（2026 年 5 月） |
|---------|---------------------|
| 補全 | ✅ 仍按安裝基底是市場領導者 |
| Copilot Workspace | ✅ 多檔案代理編輯（GA 中） |
| 模型 | GPT-5.5（預設）、Claude Sonnet 4.6 / Opus 4.7（可用） |
| 企業功能 | ✅ IP 保護、組織策略、程式碼引用關閉 |

**最適合**：已加入 Microsoft/GitHub 生態系統的企業團隊。

**2026 年現實**：對於大多數開發人員，Copilot 的補全品質已被 Cursor/Windsurf 超越，但其企業功能和 GitHub 整合在大組織中保持主導地位。

---

## 開源程式設計代理

### OpenHands（前身為 OpenDevin）

**GitHub：** github.com/All-Hands-AI/OpenHands | **授權：** MIT

領先的開源自主程式設計代理：

```bash
# 使用 Docker 執行
docker pull docker.all-hands.dev/all-hands-ai/openhands:latest
docker run -it --rm \
  -e SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:latest \
  -e LLM_API_KEY=$ANTHROPIC_API_KEY \
  -e LLM_MODEL=claude-3-7-sonnet-20250219 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -p 3000:3000 \
  docker.all-hands.dev/all-hands-ai/openhands:latest
# 在 http://localhost:3000 存取
```

**架構：**
```
User request
    ↓
OpenHands Controller
    ├── CodeActAgent（主要策略）
    ├── Docker Sandbox（隔離執行）
    ├── File editor（str_replace_editor）
    └── Browser（用於 Web 任務的 playwright）
```

**關鍵功能：**
- **任何 LLM**：使用 Claude Sonnet 4.6 / Opus 4.7、GPT-5.5、Gemini 3.1 Pro、DeepSeek V4、本地 Ollama
- **Docker 沙箱**：代理在隔離容器中執行
- **Web UI**：聊天介面；顯示代理的推理
- **API 存取**：用於 CI 整合的 REST API
- **SWE-bench 分數**：~55-60%（取決於後端模型）

### Aider

**GitHub：** github.com/paul-gauthier/aider | **授權：** Apache 2.0

終端優先、git 原生程式設計代理：

```bash
pip install aider-chat

# 直接與您的 git 存放庫一起使用
aider --model claude-3-7-sonnet-20250219

# 將檔案新增到上下文
/add src/auth.py src/models.py

# 給予任務
> Add JWT authentication to the User model
```

**讓 Aider 與眾不同的原因：**
- **Git 原生**：隨著進行提交；保持乾淨的 git 歷史
- **上下文映射**：維護整個程式碼庫的地圖（即使不在上下文中也是如此）
- **語音模式**：大聲說出任務  
- **架構模式**：在觸摸程式碼之前討論設計

```bash
# SWE-bench 驗證基準測試（2026 年 5 月）
# Aider + Claude Sonnet 4.6  → ~74%
# Aider + Claude Opus 4.7    → ~87%
# Aider + GPT-5.5            → ~88%
```

### Cline（VS Code 擴充功能）

**GitHub：** github.com/cline/cline | **授權：** Apache 2.0

用於自主程式設計的開源 VS Code 擴充功能：

```
VS Code
  └── Cline Extension
        ├── 任何模型（Claude、GPT、Gemini、Ollama）
        ├── 檔案系統存取（讀寫任何檔案）
        ├── 終端（bash 命令）
        ├── 瀏覽器（playwright）
        └── MCP 伺服器（任何 MCP 工具）
```

**關鍵差異化：**
- **MCP 原生**：開箱即用的完整 MCP 支援
- **每動作許可**：每個 shell 命令、檔案編輯都需要使用者批准
- **模型靈活性**：支援任何 OpenAI 相容 API 端點（包括本地 Ollama）
- **免費**：開源，無訂閱

**最適合**：想要 Cursor 體驗但免費、具有完整模型靈活性的開發人員。

---

## 基準測試深入探討

### SWE-bench 驗證（2026 年 3 月）

軟體工程的黃金標準。衡量解決真實 GitHub 問題的能力。

| 代理 / 系統 | 分數 | 模型後端 | 備註 |
|---------------|-------|---------------|-------|
| GPT-5.5（單次射擊領導者） | 88.7% | OpenAI | 在 SWE-Bench 驗證（2026 年 5 月）保持第一名 |
| Claude Opus 4.7（Anthropic） | 87.6% | Anthropic | 在 SWE-Bench Pro 領先 64.3% |
| Claude Code | ~87% | Claude Opus 4.7 / Sonnet 4.6 | Anthropic 官方代理 |
| OpenHands（最佳配置） | ~75% | Claude Sonnet 4.6 | 開源 |
| Aider | ~74% | Claude Sonnet 4.6 / Opus 4.7 / GPT-5.5 | 開源 CLI |
| SWE-agent | ~55% | GPT-5.5 | Princeton 研究基準 |

> [!NOTE]
> SWE-bench 分數對後端模型高度敏感。相同的代理使用 claude-3-7-sonnet 通常比使用 GPT-4o 高 10-15%。

### HumanEval+（開源模型）

| 模型 | HumanEval+ 分數 |
|-------|-----------------|
| Claude 3.7 Sonnet | 93.6% |
| GPT-4o | 90.2% |
| Qwen2.5-Coder-32B-Instruct | 88.2% |
| DeepSeek-Coder-V2-Instruct | 90.2% |
| StarCoder2-15B | 73.3% |

### LiveCodeBench（執行期評估，更強信號）

LiveCodeBench 使用新鮮的競技程式設計問題（不在訓練資料中）：

| 模型 | LiveCodeBench 分數 |
|-------|---------------------|
| o3 (high) | 68.1% |
| Claude 3.7 Sonnet | 54.2% |
| GPT-4.5 | 38.7% |
| Qwen2.5-Coder-32B | 43.2% |
| DeepSeek-R1 | 57.0% |

**洞察**：LiveCodeBench 分數比 HumanEval 低得多，因為它測試新穎問題。o3 和 DeepSeek-R1 因其推理能力而主導。

---

## 成本比較

### 封閉 API 對比 開源自託管

**場景：每天 1,000 個程式設計任務，每個平均 5K token**

| 方案 | 每月成本 | 品質 | 延遲 |
|----------|-------------|---------|---------|
| Claude 3.7 Sonnet（API） | ~$9,000 | ★★★★★ | 中等 |
| GPT-4o（API） | ~$7,500 | ★★★★ | 中等 |
| o3-mini（API） | ~$3,300 | ★★★★★（推理） | 慢 |
| Qwen2.5-Coder-32B（4×A100） | ~$4,000（基礎設施） | ★★★★ | 快速 |
| DeepSeek-V3（Together AI） | ~$1,350 | ★★★★ | 中等 |

**關鍵洞察**：每天 500+ 個任務時，自託管 Qwen2.5-Coder-32B 變得具有成本競爭力。每天 <200 個任務時，API 幾乎總是更便宜，當您考慮工程開銷時。

---

## 選擇指南

### 快速決策樹

```
您的主要需求是什麼？

├─ IDE 程式設計輔助（補全 + 聊天）？
│  ├─ Microsoft 生態系統 / 企業？ → GitHub Copilot
│  ├─ 想要最佳品質？ → Cursor（Pro）
│  └─ 想要免費 + 模型選擇？ → Windsurf 或 Cline
│
├─ 用於獨立程式設計任務的自主代理？
│  ├─ 最佳品質，不介意專有？ → Claude Code
│  ├─ 需要開源？ → OpenHands
│  ├─ CLI 優先，git 原生？ → Aider
│  └─ VS Code 內嵌，MCP 原生？ → Cline
│
├─ 自託管模型用於自訂部署？
│  ├─ 最佳品質？ → Qwen2.5-Coder-32B
│  ├─ 需要推理？ → DeepSeek-R1-Distill-32B
│  ├─ 快速補全？ → Qwen2.5-Coder-7B 或 StarCoder2-7B
│  └─ 邊緣/裝置上？ → Qwen2.5-Coder-1.5B 或 StarCoder2-3B
│
└─ CI/CD 管線整合？
   ├─ 最佳結果？ → Claude Code SDK（無頭）
   ├─ 開源？ → OpenHands REST API
   └─ git 原生？ → Aider CLI 在 GitHub Actions 中
```

### 比較矩陣

| 維度 | Claude Code | Cursor | OpenHands | Aider | Cline |
|-----------|-------------|--------|-----------|-------|-------|
| 自主性 | 完整 | 中 | 完整 | 完整 | 完整 |
| 模型鎖定 | Claude | 任何 | 任何 | 任何 | 任何 |
| 開源 | ❌ | ❌ | ✅ | ✅ | ✅ |
| CI/無頭 | ✅ | ❌ | ✅ | ✅ | ❌ |
| GUI | CLI | 完整 IDE | Web UI | 終端 | VS Code |
| MCP | ✅ | ✅ | 部分 | ❌ | ✅ |
| Git 原生 | 部分 | 部分 | ✅ | ✅ | 部分 |
| 價格 | API 成本 | $20/月 | 免費 + API | 免費 + API | 免費 + API |

---

## 生產架構

### 企業程式設計代理平台

以下是如何構建內部 AI 程式設計平台：

```
┌────────────────────────────────────────────────────────────┐
│             ENTERPRISE CODING AGENT PLATFORM                │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Developer                                                 │
│     ↓ (Jira ticket / PR description)                      │
│  ┌──────────────────────────────────┐                      │
│  │        TASK INTAKE LAYER         │                      │
│  │  • Parse task from Jira/GitHub   │                      │
│  │  • Classify: simple/complex      │                      │
│  │  • Route to appropriate agent    │                      │
│  └──────────────┬───────────────────┘                      │
│                 │                                          │
│    Simple fix   │   Complex feature                        │
│        ↓        │        ↓                                 │
│  ┌──────────┐   │  ┌──────────────────┐                    │
│  │  Aider   │   │  │   Claude Code    │                    │
│  │ (cheap)  │   └→ │  SDK (headless)  │                    │
│  └────┬─────┘      └────────┬─────────┘                    │
│       │                     │                              │
│       └─────────────────────┘                              │
│                 ↓                                          │
│  ┌──────────────────────────────────┐                      │
│  │         REVIEW LAYER             │                      │
│  │  • Git diff → PR creation        │                      │
│  │  • Auto-run CI tests             │                      │
│  │  • Human review (required)       │                      │
│  └──────────────────────────────────┘                      │
│                 ↓                                          │
│         Merge to main (human approved)                     │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 關鍵生產決策

| 決策 | 選項 | 建議 |
|----------|---------|----------------|
| 代理模型 | Claude 3.7、GPT-4o、開源 | 使用 Claude 3.7 Sonnet 以獲得最佳結果 |
| 任務攝入 | 手動、Jira webhook、GitHub label | GitHub label 觸發 Actions 工作流程 |
| 程式碼執行 | 本地、Docker、E2B | Docker（可重現、隔離） |
| 人類審查 | PR、Slack 批准、自動化 | 需要 PR 審查，從不自動合併 |
| 成本控制 | 最大回合數、模型路由 | max_turns=20，Haiku 用於簡單任務 |

---

## 面試題目

### Q：您如何在 Claude Code、Cursor 和 OpenHands 之間選擇？

**強烈回答：**
這取決於三個軸：

1. **介面需求**：如果開發人員想要 GUI（在上下文中介看變更），使用 Cursor 或 Windsurf。如果任務是腳本化/無頭的（錯誤修正、CI 中的測試生成），使用 Claude Code SDK 或 OpenHands。

2. **模型控制**：如果您需要使用任何模型（或您自己的微調模型），使用 OpenHands 或 Aider。如果您可以接受僅 Anthropic 並且想要同類最佳的結果，使用 Claude Code。

3. **開源要求**：企業安全團隊通常需要可審計的開源工具。OpenHands（MIT）和 Aider（Apache 2.0）是答案。

對於典型的初創公司，我會推薦：Cursor 用於日常開發，Claude Code 用於批次任務（來自 GitHub 問題的 PR），以及 OpenHands 用於自託管 CI 管線。

### Q：為何像 Qwen2.5-Coder 這樣的開源權重程式設計模型對企業很重要？

**強烈回答：**
三個原因：

1. **資料隱私**：發送到封閉 API 的程式碼可能用於訓練或暴露給第三方。對於醫療（HIPAA）、金融（SOX）和政府團隊，沒有專有程式碼可以離開網路。Qwen2.5-Coder-32B 在本地執行可以解決這個問題。

2. **規模成本**：在每月 100 萬+ 程式碼生成請求時，自託管比 API 定價便宜 40-60%，特別是對於補全（對比代理任務）。

3. **微調**：開源權重可以領域專業化。法律科技公司可以在我們的內部 DSL（領域特定語言）上進行微調。API 不允許這樣做。

Qwen2.5-Coder-32B 和 Claude 3.7 Sonnet 之間的品質差距是真實的但正在縮小。對於補全和更簡單的任務，開源模型通常「足夠好」。

### Q：您將如何為 CI 中的 AI 程式設計代理設計測試策略？

**強烈回答：**
我會使用三層評估：

**1. 功能測試**（自動化，每次執行）：
```
代理輸出 → 執行 pytest → 通過率指標
```

**2. 地面真實比較**（每週）：
```
已知錯誤 → 代理修正 → 與專家修正比較
指標：差異的語意相似度（非位元組精確）
```

**3. 人類評估**（抽樣 5% 的代理 PR）：
```
資深工程師評分：正確性、樣式、安全性，1-5 規模
```

我還追蹤**回歸率** — 如果代理修正引入了新的失敗測試，那是硬失敗。代理應該執行完整測試套件，只有在通過率提高或維持時才成功。

---

## 參考文獻

- Qwen2.5-Coder：https://qwenlm.github.io/blog/qwen2.5-coder/
- SWE-bench：https://www.swebench.com/
- OpenHands：https://github.com/All-Hands-AI/OpenHands
- Aider：https://github.com/paul-gauthier/aider
- Cline：https://github.com/cline/cline

---

*下一篇：[Pydantic AI 和 Mastra：型別化代理框架](11-pydantic-ai-and-mastra.md)*