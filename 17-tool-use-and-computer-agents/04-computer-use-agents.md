# 電腦使用代理程式

電腦使用代理程式讓 LLM 能夠查看螢幕、推理並透過滑鼠點擊和鍵盤敲擊來行動——與人類操作電腦的方式相同。模型不呼叫結構化 API，而是處理原始像素。本章節涵蓋它們如何運作、何時它們優於傳統自動化，以及如何圍繞它們設計生產系統。

## 目錄

- [什麼是電腦使用代理程式？](#what-are-computer-use-agents)
- [截圖-推理-行動迴圈](#the-screenshot-reason-act-loop)
- [Claude Computer Use：工具和 API](#claude-computer-use-tools-and-api)
- [架構：沙盒化環境](#architecture-sandboxed-environments)
- [瀏覽器與桌面自動化比較](#browser-vs-desktop-automation)
- [與傳統自動化的比較](#comparison-with-traditional-automation)
- [何時電腦使用優於 API 呼叫](#when-computer-use-beats-api-calls)
- [錯誤處理與恢復](#error-handling-and-recovery)
- [效能：延遲、成本、吞吐量](#performance-latency-cost-throughput)
- [真實世界應用](#real-world-applications)
- [安全考量](#security-considerations)
- [程式碼範例](#code-examples)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 什麼是電腦使用代理程式？

電腦使用代理程式是一種透過解讀螢幕截圖和發出低層級輸入命令（滑鼠移動、點擊、鍵盤敲擊）來控制圖形介面的 LLM。它取代了人類-電腦互動迴圈中的人類。

```
Traditional Tool Use:           Computer Use:

User Request                    User Request
     |                               |
     v                               v
 LLM reasons                    LLM reasons
     |                               |
     v                               v
 Structured API call             Screenshot captured
 {"tool": "search",                  |
  "query": "..."}                    v
     |                          LLM sees pixels, finds button
     v                               |
 API returns JSON                    v
     |                          Mouse click at (x=340, y=220)
     v                               |
 LLM formats answer                  v
                                New screenshot captured
                                     |
                                     v
                                LLM verifies result, continues...
```

關鍵區別：傳統工具使用需要具有已知結構描述的預定義 API。電腦使用可與任何具有視覺介面的應用程式配合使用——無需 API。

### 景觀（2026）

多個提供商現在提供電腦使用能力：

| 提供商 | 代理程式 | 方法 | 關鍵優勢 |
|----------|-------|----------|--------------|
| Anthropic | Claude Computer Use | 視覺 + 座標推理 | 桌面 + 瀏覽器，成熟 API |
| OpenAI | ChatGPT Agent Mode | 基於操作員的瀏覽器代理程式 | 深度網頁導航 |
| Google | Project Mariner | Gemini 視覺語言 | Chrome 整合 |
| Microsoft | UFO/UFO2 | Windows UI 自動化 + 視覺 | 原生 Windows 支援 |
| Amazon | Nova Act | 專用瀏覽器模型 |電子商務工作流程 |

---

## 截圖-推理-行動迴圈

每個電腦使用代理程式遵循相同的核心迴圈，通常稱為「代理程式迴圈」或「行動迴圈」：

```
+------------------+
|  Capture Screen  |<-----------+
+--------+---------+            |
         |                      |
         v                      |
+------------------+            |
|  Send to LLM     |            |
|  (screenshot +   |            |
|   task context)  |            |
+--------+---------+            |
         |                      |
         v                      |
+------------------+            |
|  LLM Reasons     |            |
|  about next      |            |
|  action           |           |
+--------+---------+            |
         |                      |
    +----+----+                 |
    |         |                 |
    v         v                 |
 [Action]  [Done]               |
    |                           |
    v                           |
+------------------+            |
| Execute Action   |            |
| (click, type,    |            |
|  scroll, key)    |            |
+--------+---------+            |
         |                      |
         +----------------------+
```

每個迭代：
1. **捕獲**：拍攝當前顯示狀態的螢幕截圖。
2. **傳送**：將截圖（base64 圖像）加上對話歷史傳遞給 LLM。
3. **推理**：模型分析螢幕上的內容，確定朝向目標的下一步。
4. **行動**：模型輸出工具呼叫（例如，`click at (450, 320)`），執行時執行它。
5. **重複**：捕獲新截圖並繼續迴圈，直到模型發出完成信號。

模型透過對話歷史維持跨迭代的上下文，該歷史累積截圖和動作，像視覺「記憶」一樣記錄發生的事情。

---

## Claude Computer Use：工具和 API

Claude 為電腦使用暴露了三個內建工具。這些是 Anthropic 定義的工具——你不編寫實作；Claude 知道如何生成對它們的呼叫，你的執行時對環境執行它們。

### 三個工具

**1. `computer`——完整 GUI 控制**

在虛擬顯示器上控制滑鼠和鍵盤。功能：
- `screenshot`——捕獲當前螢幕狀態
- `left_click`, `right_click`, `double_click`, `triple_click`——在座標處點擊滑鼠
- `left_click_drag`——從一點拖曳到另一點
- `type`——輸入文字字串
- `key`——按下鍵盤按鍵（例如，`ctrl+c`、`Return`、`Escape`）
- `scroll`——在座標處上下左右滾動
- `move`——將遊標移動到座標
- `hold_key`——在執行另一動作時按住修飾鍵
- `wait`——暫停指定持續時間

**2. `bash`——Shell 命令執行**

在持久化對話中執行 shell 命令：
- 命令共享狀態（環境變數、工作目錄）
- 支援多行腳本
- 輸出被捕獲並作為文字返回

**3. `text_editor`——檔案操作**

帶有以下命令的結構化檔案編輯：
- `view`——讀取檔案內容（帶可選行範圍）
- `create`——建立具有內容的新檔案
- `str_replace`——替換檔案中的特定字串（必須是唯一匹配）
- `insert`——在特定行號處插入文字

### API 請求結構

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    tools=[
        {
            "type": "computer_20250124",
            "name": "computer",
            "display_width_px": 1280,
            "display_height_px": 800,
            "display_number": 1
        },
        {
            "type": "bash_20250124",
            "name": "bash"
        },
        {
            "type": "text_editor_20250124",
            "name": "str_replace_based_edit_tool"
        }
    ],
    messages=[
        {
            "role": "user",
            "content": "Open Firefox, navigate to github.com, and find repos trending today."
        }
    ],
    betas=["computer-use-2025-01-24"]
)
```

回覆將包含 `tool_use` 區塊，你的執行時必須執行並作為 `tool_result` 訊息反饋。

---

## 架構：沙盒化環境

電腦使用代理程式必須在隔離環境中運行。模型完全控制滑鼠和鍵盤——你不會想在你的生產工作站上這樣做。

### 標準架構：Docker + VNC

```
+-----------------------------------------------------+
|  Docker Container                                   |
|                                                     |
|  Xvfb (Virtual X11) + Mutter (WM) + Tint2 (Panel)  |
|         |                                           |
|         v                                           |
|  +------------------+     +-------------------+     |
|  | Virtual Desktop  |---->| Screenshot Capture|     |
|  | 1280x800         |     | (scrot/maim)      |     |
|  | Firefox, apps    |     +--------+----------+     |
|  +------------------+              |                |
|                                    v                |
|                           +--------+----------+     |
|                           | Agent Runtime     |     |
|                           | - Calls Claude API|     |
|                           | - Executes actions|     |
|                           | - Manages loop    |     |
|                           +-------------------+     |
+-----------------------------------------------------+
```

### 雲端托管替代方案

像 E2B（e2b.dev）這樣的服務提供預先配置的沙盒化環境：
- 帶預安裝瀏覽器和工具的臨時 VM
- 用於截圖捕獲和輸入注入的 API
- 對話結束後自動清理
- 無 Docker 管理開銷

### 關鍵環境元件

| 元件 | 用途 | 範例 |
|-----------|---------|---------|
| Xvfb | 虛擬 X11 顯示伺服器 | 建立無實體顯示的 framebuffer |
| Mutter/Xfwm | 視窗管理器 | 處理視窗定位、調整大小 |
| Tint2 | 任務面板 | 顯示運行的應用程式 |
| xdotool | 輸入注入 | 執行滑鼠/鍵盤命令 |
| scrot/maim | 截圖捕獲 | 以 PNG 拍攝顯示快照 |

---

## 瀏覽器與桌面自動化比較

| 維度 | 僅瀏覽器 | 完整桌面 |
|----------|-------------|--------------|
| 範圍 | 僅 Web 應用程式 | 任何 GUI 應用程式 |
| 設定複雜性 | 較低（無頭瀏覽器） | 較高（完整桌面環境） |
| 效能 | 更快（較小截圖） | 較慢（完整螢幕捕獲） |
| 可靠性 | 較高（可預測佈局） | 較低（OS 變化） |
| 使用案例 | 網頁抓取、表單填寫 | 舊版軟體、跨應用程式工作流程 |

瀏覽器自動化控制網頁瀏覽器（導航、填寫表單、點擊按鈕、處理 SPA）。桌面自動化控制完整 OS 環境（啟動應用程式、使用原生對話方塊、與厚用戶端軟體互動、在多個應用程式之間連結操作）。

---

## 與傳統自動化的比較

Selenium、Playwright 和 Puppeteer 透過直接 DOM 存取自動化瀏覽器。電腦使用代理程式處理像素。兩者在生產中都有其位置。

| 特性 | Selenium/Playwright | 電腦使用代理程式 |
|---------|--------------------|--------------------|
| 速度 | 快（直接 DOM） | 慢（截圖 + LLM） |
| 可靠性 | 脆弱（選擇器變化） | 有彈性（視覺識別） |
| 維護 | 持續選擇器更新 | 極少（適應 UI 變化） |
| 反機器人檢測 | 經常被封鎖 | 較難檢測 |
| 每動作成本 | ~$0.001 | ~$0.01-0.05 |
| 非 Web 支援 | 否 | 是（任何 GUI） |

**混合方法**在生產中效果最好：Playwright 處理高容量、定義明確的流程（登入、導航），而電腦使用代理程式處理動態、不可預測的步驟（視覺驗證、新奇佈局、反機器人站點）。

---

## 何時電腦使用優於 API 呼叫

**在以下情況使用電腦使用：** 沒有 API 存在（舊版系統）、反機器人保護封鎖 Selenium、需要視覺判斷（圖表驗證、PDF 佈局）、UI 變化速度快於選擇器維護速度、或工作流程跨越多個桌面應用程式。

**堅持使用 API：** 有結構化 API 可用（始終首選）、延遲很重要（亞秒級）、音量很高（每小時數千個動作）、或需要確定性（相同輸入、相同輸出）。

---

## 錯誤處理與恢復

電腦使用代理程式的失敗方式與基於 API 的工具不同。主要失敗模式：

### 1. 錯誤點擊（錯誤座標）

模型從截圖計算座標，但可能差幾個像素：
- **緩解**：每個點擊後使用 `screenshot` 驗證預期狀態變更發生。
- **恢復**：如果點擊了錯誤元素，模型可以推理新狀態並糾正路線。

### 2. 過時截圖

截圖和動作執行之間螢幕可能已更改（動畫、彈出視窗、載入中）：
- **緩解**：截圖前新增短暫等待。頁面載入時使用 `wait` 動作。
- **恢復**：重新捕獲並在繼續前重新評估。

### 3. 無限迴圈

模型重複相同動作而未取得進展：
- **緩解**：設定最大迭代次數（例如，每任務 50 個動作）。
- **恢復**：在 N 次重複相同動作後，強制採用不同方法或升級給人類。

### 4. 意外對話方塊

Cookie 横幅、彈出視窗、權限對話方塊意外出現：
- **緩解**：在系統提示中包含關於處理常見對話方塊的說明。
- **恢復**：模型的視覺推理通常自然處理這些——它看到對話方塊並關閉它。

### 5. 解析度和縮放比例不匹配

模型在特定解析度下訓練。不匹配導致座標錯誤：
- **緩解**：使用建議的解析度（1280x800）並將顯示縮放比例設為 100%。
- **恢復**：調整 `display_width_px` 和 `display_height_px` 以匹配實際顯示。

### 錯誤處理模式

代理程式迴圈應追蹤動作歷史並檢測重複。如果連續發出相同動作 3+ 次，注入一條訊息告訴模型嘗試不同方法。始終設定硬性最大迭代次數（例如 50），並在每個動作後捕獲驗證截圖以檢測狀態變更。請參閱下面的程式碼範例章節中的完整代理程式迴圈。

---

## 效能：延遲、成本、吞吐量

### 延遲細分

代理程式迴圈的每個迭代涉及：

```
Screenshot capture:     ~100ms
Image encoding (base64): ~50ms
API call (with image):   ~2-5s  (model inference)
Action execution:        ~100ms
                        --------
Total per action:        ~2.5-5.5s
```

典型的 10 步任務需要 25-55 秒。Playwright 在同樣的 10 步驟下在 2 秒內完成。

### 每動作成本

每個動作發送截圖（~800KB base64）加上對話歷史：

| 模型 | 每動作成本（約） | 備註 |
|-------|-------------------------|-------|
| Claude Sonnet 4 | $0.01-0.03 | 建議用於大多數任務 |
| Claude Opus 4 | $0.05-0.15 | 用於複雜視覺推理 |

20 步工作流程使用 Sonnet 成本約 $0.20-0.60，或使用 Opus 成本 $1.00-3.00。

### 吞吐量優化

- **並行對話**：運行多個 Docker 容器以實現並發任務。
- **選擇性截圖**：僅在不確定的動作後捕獲；在輸入文字後跳過。
- **降低解析度**：使用 1024x768 而非 1920x1080 以減少 token 成本。
- **提前終止**：教模型在驗證目標完成後立即發出完成信號。

---

## 真實世界應用

| 應用 | 如何運作 | 為何使用電腦使用 |
|------------|--------------|------------------|
| 舊版系統整合 | 代理程式導航大型主機/厚用戶端 UI，將資料擷取到結構化格式 | 舊版軟體沒有 API 存在 |
| 表單填寫 / 資料輸入 | 讀取源文件，逐欄填寫 Web 表單，處理多頁精靈 | 具有複雜條件邏輯的政府入口網站、保險理賠 |
| QA 和視覺測試 | 以使用者身份導航應用程式，驗證視覺呈現，以自然語言報告問題 | 超越像素差異——理解佈局和 UX |
| 競爭情報 | 導航產品頁面，從 JS 渲染的 widget 捕獲定價資料 | 在封鎖傳統抓取工具的網站上運作 |

---

## 安全考量

| 風險 | 發生什麼 | 緩解 |
|------|-------------|------------|
| **可見秘密** | 模型在截圖中看到密碼、工作階段、通知 | 臨時容器、使用後清除憑證 |
| **無限制動作** | 代理程式可執行 shell 命令、導航任何地方、下載檔案 | 防火牆規則、唯讀 FS、工作階段時間限制、破壞性操作 HITL |
| **資料滲透** | 發送到 LLM 提供商的截圖包含敏感資料 | 受監管產業的本地部署、遮罩敏感 UI 欄位 |
| **透過 UI 的提示注入** | 惡意網站顯示文字以操縱代理程式 | 系統提示警告不要遵循與任務矛盾的螢幕上指示 |

基本規則：**切勿在生產工作站上或使用真實憑證存取的情況下運行電腦使用代理程式，除非在完全沙盒化的容器中**。

---

## 程式碼範例

### 最小代理程式迴圈

```python
import anthropic, base64, subprocess

client = anthropic.Anthropic()

def capture_screenshot():
    subprocess.run(["scrot", "/tmp/screen.png", "-o"], check=True)
    with open("/tmp/screen.png", "rb") as f:
        return base64.standard_b64encode(f.read()).decode()

def execute_action(action):
    name = action["action"]
    if name == "left_click":
        x, y = action["coordinate"]
        subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "1"])
    elif name == "type":
        subprocess.run(["xdotool", "type", "--", action["text"]])
    elif name == "key":
        subprocess.run(["xdotool", "key", action["text"]])

def run_agent(task: str, max_steps: int = 30):
    messages = [{"role": "user", "content": task}]
    tools = [
        {"type": "computer_20250124", "name": "computer",
         "display_width_px": 1280, "display_height_px": 800},
        {"type": "bash_20250124", "name": "bash"},
        {"type": "text_editor_20250124", "name": "str_replace_based_edit_tool"},
    ]
    for step in range(max_steps):
        response = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=4096,
            tools=tools, messages=messages, betas=["computer-use-2025-01-24"],
        )
        if response.stop_reason == "end_turn":
            return [b.text for b in response.content if b.type == "text"]

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "computer":
                execute_action(block.input)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": [{"type": "image", "source": {
                        "type": "base64", "media_type": "image/png",
                        "data": capture_screenshot()}}],
                })
            elif block.name == "bash":
                r = subprocess.run(block.input["command"],
                    shell=True, capture_output=True, text=True)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": r.stdout + r.stderr,
                })
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
    return ["Max steps reached"]
```

### 用於沙盒化環境的 Dockerfile

```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
    xvfb mutter tint2 xdotool scrot firefox-esr python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install anthropic
ENV DISPLAY=:1
COPY agent.py /agent.py
CMD Xvfb :1 -screen 0 1280x800x24 & sleep 1 && mutter & tint2 & \
    sleep 1 && python3 /agent.py
```

---

## 面試問題

### Q：客戶每天有 500 份保險理賠 PDF，必須輸入到沒有 API 的舊版 Web 入口網站。使用電腦使用代理程式設計一個系統。

**強而有力的回答：**
我會構建一個三階段管道。首先是文件處理階段，使用 LLM 從 PDF 中擷取結構化資料（理賠號碼、理賠人姓名、金額、日期）。其次是電腦使用代理程式階段，每個理賠由在帶虛擬顯示器的隔離 Docker 容器中運行的 Claude Computer Use 代理程式處理。代理程式導航 Web 入口網站，使用擷取的資料填寫表單欄位，並在提交後捕獲確認截圖。第三是驗證階段，使用單獨的 LLM 呼叫將確認截圖與預期資料進行比較，以發現任何輸入錯誤。

對於規模，我會並行運行 10-20 個容器，每個順序處理理賠。以代理程式每理賠約 2 分鐘計算，20 個容器可在 8 小時工作日內處理 600 份理賠。我會為 3 次重試後失敗的理賠添加死信佇列，並進行人工審查。

以每理賠 $0.50 的成本（大約 20 個動作每個 $0.025）計算，500 份理賠每天 $250——可能比它取代的手動資料輸入團隊便宜。

### Q：比較用於網頁自動化的電腦使用代理程式與 Selenium。何時選擇每一個？

**強而有力的回答：**
Selenium 直接與 DOM 互動——快速、確定且便宜。但當選擇器變化時它會崩潰、被反機器人系統封鎖，無法處理需要視覺判斷的任務。

電腦使用代理程式每動作慢 100 倍、成本高 10 倍，但它們適應 UI 變化，因為它們使用像素而非選擇器工作。它們生成類人類互動模式，因此更好地處理反機器人檢測。它們可以推理視覺佈局——驗證圖表正確渲染或從 Selenium 無法檢查的 canvas 元素讀取內容。

我會為高容量、穩定的工作流程選擇 Selenium，目標網站在我的控制下。我會為一次性任務、頻繁變化的第三方網站、跨應用程式桌面工作流程，以及維護選擇器的人力成本超過 LLM 推理成本的任何任務選擇電腦使用代理程式。

最好的生產系統兩者都使用：Playwright 處理可預測的步驟（認證、導航），電腦使用代理程式處理動態步驟（解讀結果、做出判斷）。

---

## 參考文獻

- Anthropic. "Computer Use Tool" API Documentation (2025)
- Anthropic. "Bash Tool" and "Text Editor Tool" API Documentation (2025)
- E2B. "Sandboxed Cloud Environments for AI Agents" (2025)
- OSWorld Benchmark: Desktop Agent Evaluation Suite (2025)
- WebArena Benchmark: Web Agent Evaluation Suite (2024)

---

*下一章：[建構工具使用代理程式](05-building-tool-agents.md)*
