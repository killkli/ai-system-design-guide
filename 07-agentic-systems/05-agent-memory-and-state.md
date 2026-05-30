# 代理記憶與狀態

記憶使代理能夠隨時間學習並維持上下文。代理記憶已從「聊天歷史」成熟為**多層認知架構**，具有四個命名層級（工作記憶、情節記憶、語義記憶、程序記憶），每層都有各自的寫入模式、延遲預算與失敗模式。生產系統（Mem0、Letta、Anthropic Memory Tool + Skills、Zep/Graphiti、LangMem）現在將記憶選擇視為第一公民的架構決策。

2026 年塑造本章的研究浪潮：A-MEM（NeurIPS 2025）、HippoRAG（多跳圖檢索）、多層記憶架構、HaluMem（操作層級記憶幻覺基準）、MINJA / MemoryGraft（僅查詢的記憶汙染攻擊），以及 NVIDIA 的 TTT-E2E 測試時間訓練方法，可將上下文壓縮至權重中。

## 目錄

- [記憶層級架構](#hierarchy)
- [短期：推理軌跡](#short-term)
- [情節記憶：過去經驗](#episodic)
- [語義記憶：人物設定](#semantic)
- [程序記憶：學習到的技能與工作流程](#procedural-memory-learned-skills-and-workflows)
- [取捨：事實 X 該放哪裡？](#tradeoffs)
- [生產實作（2026 年 5 月）](#production-implementations)
- [失敗模式與緩解](#failure-modes)
- [Mem0 與個人化](#mem0)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 記憶層級架構

代理使用分層儲存方法：

| 層級 | 類型 | 技術 | 目的 |
|------|------|------|------|
| **L1** | 工作記憶 | 上下文視窗 / KV Cache | 目前任務步驟、本地變數 |
| **L2** | 情節記憶 | 向量資料庫 / 圖形 | 「我上次做了什麼？」 |
| **L3** | 語義記憶 | SQL / 知識圖譜 | 使用者偏好，「真相」 |
| **L4** | 程序記憶 | 技能登錄 / 工具策略 / 工作流程圖 | 「我如何執行此任務？」 |

### 各層級的實際屬性

各層級不僅在目的上有所不同。讀取模式、寫入模式、延遲預算與新近度期望各自傾向不同的儲存技術：

| 維度 | L1 工作記憶 | L2 情節記憶 | L3 語義記憶 | L4 程序記憶 |
|------|------------|------------|------------|------------|
| **儲存內容** | 活躍回合與工具輸出、演算本、系統提示 | 過去工作階段、軌跡帶時間戳的觀察 | 濃縮事實、偏好、實體關係 | 技能、劇本、系統提示指令、程式碼/工具序列 |
| **讀取模式** | 每個 token、每個回合（在注意力中） | 按相似度+新近度+重要性加權的 top-k | 在實體/主題提及時觸發查詢 | 符合任務簽名時載入，通常是檔案名稱或標籤查詢 |
| **寫入模式** | 推理引擎連續附加；KV-cache 變異 | 僅附加日誌；在回合邊界提交 | 萃取、去重、upsert；寫入時衝突解決 | 成功/失敗後反思寫入；明確的人類或自我編輯 |
| **延遲預算** | <50ms（駐留在 GPU HBM 中） | 100-300ms（向量 ANN + 重排） | 200-800ms（圖形周遊 + LLM 萃取） | 50-500ms（檔案讀取或小型索引查詢） |
| **新近度期望** | token 新鮮；工作階段結束時遺失 | 小時到月；容忍陳舊 | 應反映*目前*狀態；陳舊是錯誤 | 變化緩慢；更新是經過考量的 |
| **儲存技術** | GPU HBM 中的 KV cache（vLLM PagedAttention 區塊） | 向量 DB（Pinecone、Weaviate、Qdrant）、僅附加日誌 | 知識圖譜（Neo4j、Graphiti）、KV 存放區、雙時間關聯式列 | 檔案系統（Claude `/memories/`、技能作為 `SKILL.md`）、提示登錄、微調 LoRA |
| **查詢語意** | 位置 + 注意力 | 相似度 + 新近度 + 重要性（Park et al. 加權） | 實體關係匹配、結構化查詢、雙時間過濾 | 任務簽名匹配，通常是檔案名稱或標籤查詢 |
| **驅逐** | KV 區塊雜湊上的滑動視窗、LRU | 衰減評分、濃縮至 L3、歸檔至冷存放區 | 透過時間 `valid_to` 替換；明確刪除用於 GDPR | 手動棄用、對更新版本 A/B、版本釘選 |

**這在實踐中的意義：** 當一個事實到來時，架構問題不是「我們應該記住它嗎？」而是「*放在哪一層*，有什麼新近度合約，以及什麼驅逐規則？」選擇錯誤的層級會產生可預測的失敗模式（一個工作階段偏好被提升至 L3 會跨工作階段洩漏；一個穩定的使用者事實留在 L2 會在兩週內被驅逐）。見下方[取捨：事實 X 該放哪裡？](#tradeoffs)。

---

## 短期：推理軌跡

生產代理不再只儲存「訊息」；它們儲存**狀態物件**。
- **演算本**：提示中一個專門區段，代理在這裡「寫筆記」給自己，但*不*顯示給使用者。
- **KV Cache 分塊**：對於長期執行的代理，我們使用**前綴快取**將「系統指令」與「標準工具」保持在 GPU 記憶體中熱態，只交換動態任務狀態。

---

## 情節記憶：過去經驗

情節記憶儲存「運行」或「軌跡」。
- 如果代理上週二未能成功爬取某網站，情節記憶應防止它今天嘗試同樣失敗的選擇器。
- **模式**：任務完成時，將「學到的教訓」摘要並儲存在向量資料庫中。在新任務開始時，執行**自我搜尋**以尋找類似的先前任務。

---

## 語義記憶：人物設定

語義記憶儲存關於使用者或環境的「事實」。
- *「使用者偏好 JSON 輸出。」*
- *「正式 DB 在凌晨 3 點到 4 點之間離線。」*

**最佳實踐**：對語義記憶使用**知識圖譜**。與向量搜尋（模糊）不同，圖提供實體與關係的確定性檢索（例如 `User` -- `OWNER_OF` --> `Project_A`）。

---

## 程序記憶：學習到的技能與工作流程

程序記憶儲存如何做事。情節記憶回答「之前發生了什麼？」而語義記憶回答「什麼是真的？」，程序記憶回答：

「完成此類任務的正確流程是什麼？」

這層擷取可重用技能、工具使用模式、操作程序與工作流程偏好。

範例：

- 「產生每週報告時，先從 Snowflake 提取指標，再根據儀表板驗證，然後摘要異常。」
- 「回應客戶投訴時，先分類緊急程度、檢索政策、起草回應，若信心低則升級。」
- 「撰寫 SQL 時，總是先檢查結構描述、產生查詢、執行驗證，並說明假設。」

程序記憶對代理系統特別重要，因為許多任務不僅僅是記住事實，還需要遵循正確的動作順序。

---

## 取捨：事實 X 該放哪裡？

首要決策不是「哪一層」而是*「誰來承擔錯誤的代價？」* L2 中的一次失敗檢索只失敗一個回合。L3 中的一個錯誤事實*每個回合*都失敗，直到被修正。L4 中的一個中毒技能傳播到每個未來的叫用。

### 層級選擇表

| 事實 / 關注點 | 層級 | 推理 |
|--------------|------|------|
| 「使用者的 API 速率限制是 1000 req/min」 | L3 搭配雙時間 `valid_to` | 租戶範圍事實；可按實體查詢；必須支援替換。不是 L4——它是資料，不是程序。 |
| 「部署我們服務的步驟」 | L4 作為版本化技能 | 具有條件分支的多步驟配方。技能可組合；語義三元組不行。 |
| 「代理上次嘗試此任務失敗」 | L2 原始，*然後* 若可推廣則將教訓反思至 L4 | 原始軌跡屬於情節記憶；推廣的教訓（「永遠不要在高峰時段執行遷移」）值得反思式寫入 L4。 |
| 「使用者偏好簡潔回覆」 | L3 | 穩定偏好，可按 `user_id` 查詢，單一三元組。 |
| 「使用者*在此對話中*要求簡潔回覆」 | 僅 L1 | 工作階段範圍；不要用可能暫時的偏好汙染 L3。 |
| 目前天氣、今日股價 | 無：呼叫工具 | 具有其他真實來源的快速變化事實不應進入記憶。 |
| 「專案 Phoenix 有團隊成員 A、B、C」 | L3 作為圖形片段 | 多跳周遊價值；Graphiti 或 Neo4j 風格儲存。 |

### 成本取捨

- **L1 主導*延遲成本***：TTFT 隨上下文大小縮放；更長的工作記憶意味著更慢的首個 token。KV-cache 壓力將高階加速器記憶體推向飽和。
- **L2 主導*儲存成本*（規模化）**：僅附加日誌隨使用量線性成長。[Day-30 問題](https://cipherbuilds.ai/blog/day-30-agent-memory-problem) 描述未修剪的情節存放區如何在一個月後使代理品質腐敗。
- **L3 主導*寫入放大成本***：每個回合都可能觸發萃取、去重、衝突解決。Mem0 的設計明確地在寫入時間工作上交易檢索速度。
- **L4 主導*治理成本***：一個不良技能傳播到每個未來的叫用。Anthropic 的「[Claude Dreaming](https://www.mindstudio.ai/blog/what-is-claude-dreaming-anthropic-agent-memory)」排程濃縮透過審查閘控技能更新，承認了這點。

### 升級規則

有趣的設計問題是*何時讓 L2 episode 升至 L3 或 L4*。可辯護的規則是基於閾值，而非隱式衰減：

1. **N 次獨立觀察**同一模式（N=3 到 5 是典型的）。
2. **信心加權**（來源）：使用者陳述 > 工具輸出 > 模型推斷。
3. **人類或 LLM 法官審查**在濃縮步驟（非每回合）。
4. **排程批量濃縮**，而非同步每回合寫入（避免寫入放大）。
5. **雙向的**：L3 中的語義事實可以重新具現化為特定任務的情節上下文。記憶不是單行道。

---

## 生產實作（2026 年 5 月）

命名系統在「儲存什麼」上差異較小，而在*寫入紀律*、*檢索演算法*與*治理姿態*上差異較大。

| 系統 | 甜蜜點 | 做得好的地方 | 不足之處 |
|------|--------|------------|---------|
| **[Mem0](https://github.com/mem0ai/mem0)** | 大規模跨工作階段個人化 | 混合圖+向量+KV。2026 年 4 月單次通過重新設計後，在 LoCoMo 上達到 92.5、在 LongMemEval 上達到 94.4（[基準](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)）。在頭對頭比拚中以 26% 準確度擊敗 OpenAI 內建記憶。 | 每個記憶 8K 字元上限（不適合文件）；雲端優先姿態造成資料主權摩擦；無正式信念狀態模型（僅覆寫或附加）。 |
| **[Letta（前身 MemGPT）](https://docs.letta.com/concepts/memgpt/)** | 連續性即產品的長期自主代理 | 跨核心/召回/歸檔層的 OS 風格虛擬上下文分頁；代理使用工具呼叫將資料換入/換出。當使用者體驗是「代理永遠記得」時最好。 | 每回合延遲高於 Mem0 風格。針對跨使用者檢索精確度未優化。 |
| **[Anthropic Memory Tool + Skills](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)** | 單一基底中的檔案系統掛載 L3 和 L4 | `/memories/` 中的記憶；技能作為 `SKILL.md` 封裝加可選指令碼；托管代理在每次工作階段時將記憶掛載在 `/mnt/memory/`，並具有不可變版本控制（2026 年 4 月 23 日 GA）。排程「Claude Dreaming」在工作階段之間濃縮。 | 檔案系統語意將複雜性推向代理（代理必須良好地結構化自己的目錄）。 |
| **[Zep + Graphiti](https://github.com/getzep/graphiti)** | 「這個何時變成真的？」很重要的時間事實 | 開源時間知識圖譜。每條邊有 `valid_from` / `valid_to` / `invalid_at`。在 DMR 上以 94.8% 擊敗 MemGPT 93.4%。雙時間查詢支援「我們在 3 月 12 日相信什麼？」vs.「現在什麼是真的？」 | 比僅向量的存放區更重的寫入路徑（图萃取、去重、衝突解決）。 |
| **[LangMem + LangGraph](https://langchain-ai.github.io/langmem/)** | 當你想在 LangGraph 編排中擁有全部四種記憶類型時 | 支援情節、語義*和*程序記憶。LangMem 中的程序記憶讓代理能夠根據回饋更新自己的系統提示。背景萃取帶外執行。 | 與 LangGraph 耦合；若不在 LangChain 堆疊上則吸引力較低。 |
| **[OpenAI ChatGPT Memory](https://openai.com/index/memory-and-new-controls-for-chatgpt/)** | 消費者級聊天連續性，非生產級代理記憶 | 雙層架構：明確「已儲存記憶」加上輕量級對話摘要預先注入上下文。跳過推理時的檢索步驟以降低延遲。 | 與 Mem0 風格檢索相比失去精確度。企業整合無精細程式化 API。 |
| **Cursor / Windsurf** | 軟體工程代理的程式碼庫感知 L2/L3 | 專案開啟時索引程式碼庫；`@` 提及用於明確上下文。Windsurf「記憶」在大約 48 小時使用中學習架構模式。 | 領域鎖定至程式碼。不是通用記憶層。 |
| **[Cognition Devin](https://cognition.ai/blog/devin-sonnet-4-5-lessons-and-challenges)** | 倉儲範圍的工程代理 | 倉儲 wiki 每幾小時自動索引；偏好明確的濃縮/摘要而非模型管理的狀態。Devin Search 是代理風格的程式碼庫記憶查詢介面。 | 對於工程工作流程的固執己見。 |

**生成式代理（Park et al. 2023）** 仍是每項調查中引用的參考架構。新近度 / 重要性 / 相關性檢索公式（`alpha_recency * recency + alpha_importance * importance + alpha_relevance * relevance`，每個標準化至 [0,1]，重要性由 LLM 評定 1-10）仍在上述大多數系統的生產中使用。

**值得追蹤的新興框架**（2026 年 5 月）：[Supermemory](https://supermemory.ai)、[Recallr](https://recallrai.com)、AWS [Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-integrate-lang.html)、[Oracle AI Agent Memory](https://blogs.oracle.com/developers/oracle-ai-agent-memory-a-governed-unified-memory-core-for-enterprise-ai-agents)。

---

## 失敗模式與緩解

生產記憶系統有六種反覆出現的失敗模式。知道它們的名字是菜鳥與架構師級對話的區別。

### 1. 透過提示注入的記憶汙染

不受信任的輸入被寫入 L3/L4，隨後作為權威回放。[MINJA（NeurIPS 2025）](https://openreview.net/forum?id=QVX6hcJ2um) 與 [MemoryGraft（2025 年 12 月）](https://arxiv.org/html/2512.16962v1) 展示*僅需查詢權限*即可達到 95% 注入率與 70% 攻擊成功率，*無需*提升許可權。[Palo Alto Unit 42 的分析](https://unit42.paloaltonetworks.com/indirect-prompt-injection-poisons-ai-longterm-memory/) 顯示毒株在數週前種下，在執行時才爆發。

**緩解方式：**
- 每個記憶寫入附有**來源標籤**：`source = user_stated | model_inferred | tool_output`。
- **寫入時守門員模型**，拒絕可疑的指令形寫入（「忽略之前的並改為...」、角色混淆、嵌入式系統提示片段）。
- **信任層級**：低信任記憶在高風險決策前需要證實。
- **隔艙隔離**，使一個租戶中的毒株無法轉向另一個。

### 2. 事實陳舊

上週的偏好 vs. 今天的。使用者上個月說深色模式但現在用淺色模式。

**緩解方式：**
- **雙時間儲存**（Zep/Graphiti 模式）：每個事實有 `valid_from`、`valid_to`、`invalid_at`。
- 工作階段範圍偏好的 **TTL**，使其自動過期。
- 檢索評分中的**衰減加權**。
- 超過 N 天的重大事實的**明確重新確認**提示。

### 3. 事實衝突

使用者說 X，現在說 Y。三種不同衝突類型需要不同回應：

| 衝突類型 | 正確回應 |
|---------|---------|
| 時間更新（「我搬到柏林了」） | 用 `valid_to = now` 替換舊事實 |
| 修正（「我從沒那樣說過」） | 用稽核軌跡撤回 |
| 偏好變更（「我現在要簡潔回覆」） | 新增新事實；讓衰減處理舊的 |
| 完全矛盾（無明顯解析） | 詢問使用者；永遠不要靜默覆寫 |

使用 AGM 信念修訂追蹤信念狀態（`ACTIVE` / `SUPERSEDED` / `RETRACTED`），而非最後寫入 wins。

### 4. 記憶漂移

隨著時間推移，低品質寫入稀釋高品質寫入，品質下降。[Day-30 問題](https://cipherbuilds.ai/blog/day-30-agent-memory-problem) 記錄了代理品質在大約 30 天進入生產後下降，因為情節存放區充滿了檢索無法區分的噪音。

**緩解方式：**
- **品質加權檢索**：提升具有高驗證分數的記憶。
- **排程濃縮作業**，合併重複並修剪低效用記憶。
- CI 中的**金絲雀事實測試**：「代理在 50 回合後仍應記住使用者的名字。」

### 5. 幻覺記憶寫入

代理推斷出一個事實，將其儲存為真理，然後隨後引用它作為權威。級聯失敗，一個錯誤寫入汙染未來檢索。[HaluMem 基準（2025 年 11 月）](https://arxiv.org/abs/2511.03506) 顯示現有系統在寫入時累積錯誤，這些錯誤傳播通過 QA 階段。

**緩解方式：**
- **結構描述強制的記憶物件**，具有 `confirmed_facts`（含來源）與 `inferred_facts`（含信心）的獨立欄位。
- 永遠不要在沒有明確使用者信號或工具輸出證實的情況下將推斷自動提升至已確認。
- CI 中 HaluMem 風格分段評估：分別測量萃取精確度、更新正確性與 QA 準確度，而非作為單一端到端指標。

### 6. 跨租戶洩漏

向量 ANN 返回另一個租戶的鄰居；快取的提示包含另一個租戶的資料。[現場測量](https://medium.com/@isuruig/multi-tenant-ai-infrastructure-the-5-isolation-layers-that-determine-whether-your-customers-data-stays-separate-340aaeef4922) 顯示在無隔離的多租戶 RAG 中，約 95% 的有機洩漏率。

**緩解方式：**
- **實體分離**：每租戶集合，而非元資料過濾的共享索引。
- 在*存放區層*透過服務帳戶權限強制執行租戶範圍，而非應用程式碼。
- 每租戶的單獨 KV-cache 前綴。
- 記憶 blob 上的每租戶加密金鑰，使跨命名空間讀取在密碼學層面失敗。
- 每個跨命名空間查詢嘗試的**稽核日誌記錄**：深度檢測。

---

## Mem0 與代理個人化

**Mem0**、Zep、Letta 與 Cognee 是代理堆疊中「智慧記憶」的標準框架。
- 它自動從對話中萃取的「使用者洞察」。
- 它提供代理可以呼叫「記住」或「忘記」特定資訊三元組的「記憶 API」。
- **影響**：代理感覺「有生命」，因為它記得你在 3 個月前不同工作階段中提到的細節。

---

## 面試問題

### Q：如何在代理系統中處理「衝突記憶」？

**理想回答：**
衝突記憶（例如使用者上週說「我喜歡藍色」但現在說「我喜歡紅色」）透過**時間加權**或**明確爭議**處理。在我的架構中，我為每個記憶三元組指派 `timestamp` 與 `confidence_score`。如果新事實與舊事實衝突，代理會被提示透過詢問使用者或預設最新時間戳來「解決衝突」。我們還使用**衰減函數**，使較舊的、非強化的記憶最終從活躍索引中修剪。

### Q：為什麼「上下文視窗」單獨不足以應對專業級代理架構？

**理想回答：**
首先，**成本與延遲**：為每個回合填補 1M token 的上下文，即使有上下文快取，也貴得令人卻步。其次，**信噪比**：大上下文視窗遭受「上下文學習」衰減：模型被不相關的歷史回合分散注意力。專業級架構使用**選擇性記憶檢索**（在歷史上執行 RAG），只提取 3-5 個最相關的歷史互動，使推理引擎專注於目前子目標。

### Q：如何為生產 AI 代理設計程序記憶？

**理想回答：**

我會將程序記憶設計為**技能登錄、工作流程圖與工具使用策略**的組合。每個程序定義任務類型、所需步驟、可用工具、驗證檢查、失敗模式與升級規則。每次運行後，代理可以執行反思並在發現更好方法時更新程序。例如，如果 NL2SQL 代理因跳過結構描述檢查而反覆失敗，我們可以將結構描述檢查編碼為所有 SQL 生成任務的程序記憶中必需的的第一步。

### Q：情節記憶何時變成負債而非資產？

**理想回答：**

情節記憶在三種命名模式中成為負債。首先，**索引過載**：添加 1,000 個低品質觀察將 10 個高品質觀察埋在檢索中。這是 RAG 意義上的災難性遺忘。其次，**Day-30 漂移模式**：代理品質在大約 30 天進入生產後下降，因為情節存放區充滿了檢索無法區分訊號的噪音。第三，**陳舊上下文滲漏**：在一种配置下成功的過去軌跡在另一配置下成為*錯誤*上下文。Stripe 的成功工具序列在使用者切換至 Adyen 時會主動誤導。

緩解方式是品質加權檢索、濃縮至 L3 以及上下文敏感軌跡的硬性新近度截止。最重要的教訓：情節記憶從第一天就需要*修剪策略*。沒有它，它是隨使用量線性複利的技術債務。

### Q：當代理可以寫入自己的長期存放區時，如何防止記憶汙染？

**理想回答：**

困難的部分是最近的攻擊（MINJA、MemoryGraft）是*僅需查詢*的——不需要提升許可權。毒株在執行時才爆發，數週前就種下了。因此威脅模型是「每個輸入都可能成為未來的權威記憶。」防禦有四層：

1. **寫入時的出處**：每個記憶帶有 `source`（使用者陳述、模型推斷、工具輸出）、`timestamp` 與 `trust_tier`。
2. **寫入時守門員模型**：一個較小的分類器在使用可疑的指令形寫入到達存放區之前拒絕它。
3. **證實閾值**：高風險決策不能基於單一低信任記憶；它們需要多個獨立證實的寫入。
4. **CI 中的金絲雀測試**：合成毒株負載不得傳播至輸出。每週執行。

最重要的架構分離：代理的工具表面和其記憶寫入表面不應共享信任。工具輸出在成為記憶前應通過消毒器。

### Q：記憶層級選擇：以下每個你會放在哪裡，為什麼？(a) 使用者的 API 速率限制，(b) 部署我們服務的步驟，(c) 代理上次嘗試此任務失敗，(d) 今日股價。

**理想回答：**

(a) **L3 語義**搭配雙時間有效性。這是一個具有替換壽命的租戶範圍事實。不是 L4，因為它是資料，不是程序。

(b) **L4 程序**作為版本化技能或劇本。這是一個具有條件分支的多步驟配方。技能可組合；語義三元組不行。

(c) **L2 情節原始**，並在失敗揭示可推廣的教訓時進行*反思跳至* L4。原始軌跡屬於情節記憶。教訓（「永遠不要在高峰時段執行遷移」）值得反思式寫入程序記憶。

(d) **無——呼叫工具。** 具有即時真實來源的快速變化事實不應進入記憶。它們按定義會變陳舊。

一般規則：資料放 L3，程序放 L4，觀察放 L2，永遠不儲存有即時真實來源的快速變化事實。

### Q：說說你會為情節至語義過渡設計的濃縮策略。一個 episode 何時成為一個事實？

**理想回答：**

我使用基於閾值的升級策略，而非隱式衰減：

- **頻率閾值**：對同一模式進行 N 次獨立觀察（通常為 3 到 5）。
- **信心加權**：使用者陳述 > 工具輸出 > 模型推斷。
- **法官審查**：排程批量濃縮作業在候選升級上執行 LLM 法官（或高風險領域的人類審查者）。
- **排程的，非同步的**：濃縮在 cron 上帶外執行，而非每回合。這避免了寫入放大。
- **雙向的**：L3 中的語義事實可以重新具現化為特定任務的情節上下文。記憶是雙向流動的。

要避免的陷阱：僅通過衰減權重的隱式濃縮。它在小規模下有效，在生產規模下靜默失敗，因為沒有「為什麼這個事實出現在 L3 中？」的稽核軌跡。

### Q：你的代理記憶存放區有 50M 記憶跨 10K 租戶。如何保證跨租戶隔離，什麼是隔離失敗時的爆炸半徑？

**理想回答：**

架構有五層隔離：

1. **存放區層的實體分離**：每租戶集合或分片，而非元資料過濾的共享索引。共享索引加租戶 ID 模式在錯誤下開放失敗。
2. **透過服務帳戶範圍強制執行**：應用程式碼不能選擇退出租戶範圍；資料庫角色對其他租戶沒有可見性。
3. **每租戶的單獨 KV-cache 前綴**：防止快取提示在租戶之間洩漏。
4. **每租戶加密金鑰**：即使因錯誤返回，跨命名空間的位元組也無法讀取。
5. **每個跨命名空間查詢嘗試的稽核日誌記錄**：深度檢測。

**隔離失敗時的爆炸半徑**：一次糟糕的向量查詢可能洩漏一個查詢嵌入的*鄰域*——可能來自一個租戶的數百條記錄。現場測量顯示在無隔離的多租戶 RAG 中約 95% 的有機洩漏率。緩解不是「更小心的應用程式碼」；而是無法被應用程式錯誤繞過的結構分離。

### Q：HaluMem 顯示記憶幻覺在寫入時累積，然後傳播。如何為生產記憶進行檢測？

**理想回答：**

大多數團隊陷入的陷阱是只在 QA 階段（端到端）測量記憶品質。HaluMem 證明 60-80% 的記憶錯誤起源於*萃取*（寫入）時並傳播。你需要檢測三個獨立指標：

1. **萃取精確度**：當代理將事實寫入 L3 時，該事實是否實際得到來源觀察的支持？每天抽樣寫入，用更強的法官評估。
2. **更新正確性**：當衝突事實到達時，衝突解決邏輯是否產生了正確結果？使用雙時間查詢檢測「沒有元資料替換就翻轉的事實」。
3. **QA 準確度**：端到端回憶正確性。

在此之上，執行**影子模式重放**：寫入通過影子驗證器模型；即時寫入和影子驗證器寫入之間的不匹配標記潛在幻覺以供審查。**CI 中的金絲雀事實**確保記憶系統不會靜默迴歸。**定期全存放區稽核**抽樣隨機記憶並問「這是否仍與來源對話一致？」

### Q：NVIDIA 的 TTT-E2E 透過測試時間訓練將上下文壓縮至權重。它在 L1-L4 層級中處於什麼位置，引入什麼新的失敗模式？

**理想回答：**

TTT-E2E 介於 L1 和 L4 之間。它使上下文衍生資訊成為模型本身的組成部分，適用於剩餘的工作階段。吸引力是延遲：無論上下文長度如何，成本恆定（根據 NVIDIA 的基準，在 128K 時 2.7 倍加速，在 2M 時 35 倍加速，在 H100 上）。

新的失敗模式是治理。權重中的記憶：

- **無稽核軌跡**：你無法檢查「這個模型現在相信什麼？」
- **無驅逐介面**：一旦壓縮至權重，你無法刪除記憶而不回滾模型狀態。
- **GDPR 被遺忘權挑戰**：監管框架假設資料處於靜止狀態，而非權重中。
- **更難的汙染檢測**：沒有可掃描以獲取金絲雀簽名的可檢查存放區。

正確的框架：TTT-E2E 將記憶治理從存放區層移至訓練和部署管線。成本沒有消除；它是重新配置的。對於 2026 年 5 月的大多數生產團隊，這是一個值得追蹤的研究方向，而非已可部署的架構。

---

## 參考文獻

### 生產框架

- [Mem0: Production-Ready AI Agents with Scalable Long-Term Memory (ECAI 2025)](https://arxiv.org/abs/2504.19413)
- [Mem0 AI Memory Benchmarks 2026](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)
- [Letta（前身 MemGPT）文件](https://docs.letta.com/concepts/memgpt/)
- [MemGPT: Towards LLMs as Operating Systems (arXiv 2310.08560)](https://arxiv.org/abs/2310.08560)
- [Anthropic Memory Tool 文件](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic Claude Sonnet 4.6 Skills 公告](https://www.anthropic.com/news/claude-sonnet-4-6)
- [Claude Dreaming: scheduled memory consolidation](https://www.mindstudio.ai/blog/what-is-claude-dreaming-anthropic-agent-memory)
- [Zep: Temporal Knowledge Graph Architecture (arXiv 2501.13956)](https://arxiv.org/abs/2501.13956)
- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [LangMem 文件](https://langchain-ai.github.io/langmem/)
- [OpenAI Memory and new controls for ChatGPT](https://openai.com/index/memory-and-new-controls-for-chatgpt/)
- [Cognition: Rebuilding Devin for Claude Sonnet 4.6](https://cognition.ai/blog/devin-sonnet-4-5-lessons-and-challenges)

### 研究（2023-2026）

- [Generative Agents: Interactive Simulacra of Human Behavior (Park et al. 2023)](https://arxiv.org/abs/2304.03442)
- [Reflexion: Language Agents with Verbal Reinforcement Learning (Shinn et al. 2023)](https://arxiv.org/abs/2303.11366)
- [HippoRAG: Neurobiologically Inspired Long-Term Memory (Gutierrez et al. 2024)](https://arxiv.org/abs/2405.14831)
- [A-MEM: Agentic Memory for LLM Agents (Xu et al. NeurIPS 2025)](https://arxiv.org/abs/2502.12110)
- [Multi-Layered Memory Architectures (arXiv 2603.29194, March 2026)](https://arxiv.org/abs/2603.29194)
- [Memp: Exploring Agent Procedural Memory (Aug 2025)](https://arxiv.org/html/2508.06433v2)
- [LEGOMem: Modular Procedural Memory for Multi-agent LLM (Oct 2025)](https://arxiv.org/pdf/2510.04851)
- [Rethinking Memory Mechanisms of Foundation Agents (Feb 2026 survey)](https://arxiv.org/abs/2602.06052)
- [Position: Episodic Memory is the Missing Piece (arXiv 2502.06975)](https://arxiv.org/pdf/2502.06975)

### 安全、汙染與幻覺

- [HaluMem: Operation-Level Memory Hallucination Benchmark (Nov 2025)](https://arxiv.org/abs/2511.03506)
- [MINJA Memory Injection Attack (NeurIPS 2025)](https://openreview.net/forum?id=QVX6hcJ2um)
- [MemoryGraft Persistent Memory Compromise (Dec 2025)](https://arxiv.org/html/2512.16962v1)
- [Palo Alto Unit 42: Indirect prompt injection poisons AI long-term memory](https://unit42.paloaltonetworks.com/indirect-prompt-injection-poisons-ai-longterm-memory/)
- [Multi-tenant AI Infrastructure: 5 Isolation Layers](https://medium.com/@isuruig/multi-tenant-ai-infrastructure-the-5-isolation-layers-that-determine-whether-your-customers-data-stays-separate-340aaeef4922)
- [The Day-30 Problem: agent memory drift](https://cipherbuilds.ai/blog/day-30-agent-memory-problem)

### 基礎設施

- [NVIDIA TTT-E2E: Reimagining LLM Memory (May 2026)](https://developer.nvidia.com/blog/reimagining-llm-memory-using-context-as-training-data-unlocks-models-that-learn-at-test-time/)
- [vLLM PagedAttention](https://docs.vllm.ai/en/latest/design/paged_attention/)
- [Anthropic Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

---

*下一篇：[規劃與分解](06-planning-and-decomposition.md)*
