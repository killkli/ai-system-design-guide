<<<<<<< Updated upstream
# 反模式

本章記錄常見的 AI 系統錯誤模式和如何避免它們。

## 目錄

- [常見反模式](#常見反模式)
- [架構反模式](#架構反模式)
- [提示反模式](#提示反模式)
- [評估反模式](#評估反模式)
- [面試題目](#面試題目)

---

## 常見反模式

### 反模式：無限制上下文

**問題：** 將所有可用內容放入上下文，期望模型會忽略不相關的部分。

```
┌────────────────────────────────────────────────────────────┐
│  問題：                                                   │
│  「模型很聰明，它會弄清楚什麼是相關的」                      │
│                                                              │
│  現實：                                                     │
│  - 模型偏向上下文的開頭和結尾                               │
│  - 無關內容稀釋相關資訊                                     │
│  - 令牌成本飆升                                            │
│  - 品質實際下降                                            │
└────────────────────────────────────────────────────────────┘
```

**解決方案：**
- 在放入上下文之前進行檢索和過濾
- 使用重排名確保最相關的文檔在頂部
- 設定合理的上下文大小限制

---

### 反模式：單一提示適用所有情況

**問題：** 使用相同的提示適用於所有查詢類型。
=======
# AI 反模式（AI Anti-Patterns）

了解不該做什麼與知道最佳實踐同樣重要。本章記錄了 AI 系統設計中的常見錯誤。

## 目錄

- [架構反模式](#架構反模式)
- [RAG 反模式](#rag-反模式)
- [Agent 反模式](#agent-反模式)
- [Prompting 反模式](#prompting-反模式)
- [評估反模式](#評估反模式)
- [生產反模式](#生產反模式)
- [面試問題](#面試問題)

---

## 架構反模式

### The God Prompt（上帝 Prompt）

**問題：** 單一巨大 Prompt 嘗試做所有事情。
>>>>>>> Stashed changes

```python
# 不好：單一提示
SYSTEM_PROMPT = """
你是一個有用的助手。回答所有問題。
"""

# 好：針對性提示
SYSTEM_PROMPTS = {
    "technical": "你是一個技術專家。使用精確的術語...",
    "creative": "你是一個創意作家。使用生動的語言...",
    "customer_support": "你是一個客服代表。保持專業和友好..."
}
```

<<<<<<< Updated upstream
**何時避免：**
- 異質查詢類型（技術、創意、客服）
- 不同的品質要求
- 需要不同的領域知識

---

## 架構反模式

### 反模式：在循環中無限制地調用 LLM

**問題：** 允許智慧體無限期地調用 LLM，沒有退出條件。
=======
**為何失敗：**
- 上下文被指令消耗，而非使用者內容
- 模型難以處理衝突的指令
- 不可能為所有情況優化
- 更新影響一切

**解決方案：**
```python
# PATTERN: Specialized components
class QueryRouter:
    async def route(self, query: str) -> str:
        intent = await self.classify_intent(query)
        handler = self.handlers[intent]
        return await handler.process(query)
```

---

### Single Provider Dependency（單一提供者依賴）

**問題：** 整個系統依賴一個 LLM 提供者。
>>>>>>> Stashed changes

```python
# 不好：可能永遠運行
while True:
    response = await llm.generate(prompt)
    if response.is_complete:
        break
    prompt += response  # 沒有最大迭代限制
```

<<<<<<< Updated upstream
**解決方案：**
- 設定最大迭代次數
- 添加令牌預算限制
- 實現明確的停止條件

=======
**為何失敗：**
- 提供者停機 = 完全系統失敗
- 速率限制影響所有流量
- 沒有價格談判籌碼
- 鎖定在單一模型系列

**解決方案：**
>>>>>>> Stashed changes
```python
# 好：有界限的循環
MAX_ITERATIONS = 10
MAX_TOKENS = 50000

for i in range(MAX_ITERATIONS):
    response = await llm.generate(prompt)
    total_tokens += count_tokens(response)
    
    if response.is_complete or total_tokens > MAX_TOKENS:
        break
```

---

<<<<<<< Updated upstream
### 反模式：忽略錯誤處理

**問題：** 假設 LLM 調用總是會成功。

```python
# 不好：沒有錯誤處理
=======
### Premature Fine-Tuning（過早微調）

**問題：** 在窮盡更簡單的方法之前就進行微調。

**為何失敗：**
- 昂貴且耗時
- 需要高質量訓練數據（通常不可用）
- 難以更新和維護
- 通常是不必要的

**決策流程：**
```
Try prompting first
    ↓ (not working)
Try few-shot examples
    ↓ (not working)
Try RAG for knowledge
    ↓ (not working)
Consider fine-tuning (with 500+ examples)
```

---

## RAG 反模式

### Retrieve Everything（檢索所有內容）

**問題：** 無論相關性如何都檢索太多文件。

```python
# ANTI-PATTERN: Retrieve everything
results = vector_db.search(query, top_k=50)
context = "\n".join([r.text for r in results])
```

**為何失敗：**
- 雜訊淹沒信號
- 超過上下文限制
- 在無關內容上浪費 Token
- 「迷失在中間」效應

**解決方案：**
```python
# PATTERN: Quality over quantity
results = vector_db.search(query, top_k=20)
reranked = await reranker.rerank(query, results)
context = "\n".join([r.text for r in reranked[:5] if r.score > 0.7])
```

---

### No Chunking Strategy（無區塊策略）

**問題：** 任意或沒有文件的區塊劃分。

```python
# ANTI-PATTERN: Fixed-size blind chunking
chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
```

**為何失敗：**
- 在句子中間、段落中間斷開
- 失去語義連貫性
- 分離相關資訊
- 檢索品質差

**解決方案：**
```python
# PATTERN: Semantic-aware chunking
chunks = semantic_chunker.chunk(
    text,
    chunk_size=500,
    overlap=100,
    respect_boundaries=["paragraph", "section"]
)
```

---

### Ignoring Metadata（忽略中繼資料）

**問題：** 將所有文件視為相等文字。

```python
# ANTI-PATTERN: Ignore metadata
embedding = embed(document.text)
vector_db.insert(embedding, {"text": document.text})
```

**為何失敗：**
- 無法按日期、來源、類型篩選
- 無法對每份文件進行存取控制
- 無法權重近期與舊文件
- 失去有價值的上下文

**解決方案：**
```python
# PATTERN: Rich metadata
vector_db.insert(embedding, {
    "text": document.text,
    "source": document.source,
    "date": document.date,
    "access_level": document.access_level,
    "document_type": document.type,
    "section": document.section
})

# Filter query
results = vector_db.search(
    query,
    filter={"date": {"$gte": "2024-01-01"}, "access_level": user.level}
)
```

---

## Agent 反模式

### Infinite Loop Risk（無限迴圈風險）

**問題：** 代理沒有終止條件。

```python
# ANTI-PATTERN: No limits
while not done:
    action = await agent.decide_action()
    result = await execute(action)
    done = agent.check_done(result)
```

**為何失敗：**
- 代理可能永遠迴圈
- 成本失控
- 永遠不回傳給使用者
- 資源耗盡

**解決方案：**
```python
# PATTERN: Multiple termination conditions
MAX_STEPS = 20
MAX_COST = 10.0
MAX_TIME = 300  # seconds

for step in range(MAX_STEPS):
    if cost_tracker.total > MAX_COST:
        return "Cost limit reached"
    if time.time() - start > MAX_TIME:
        return "Time limit reached"
    
    action = await agent.decide_action()
    result = await execute(action)
    
    if agent.check_done(result):
        return result
    
return "Step limit reached"
```

---

### Unsafe Tool Access（不安全的工具存取）

**問題：** 給代理無限制的工具存取。

```python
# ANTI-PATTERN: Full access
tools = [
    delete_file,
    execute_shell_command,
    send_email,
    database_query  # unrestricted!
]
```

**為何失敗：**
- 代理可以刪除關鍵檔案
- 可以竊取資料
- 可以執行惡意命令
- 沒有審計追蹤

**解決方案：**
```python
# PATTERN: Scoped, validated tools
tools = [
    ScopedFileTool(allowed_dirs=["/tmp/agent"]),
    RestrictedShellTool(allowed_commands=["ls", "cat"]),
    EmailTool(requires_confirmation=True),
    ReadOnlyDatabaseTool(allowed_tables=["products"])
]
```

---

### Agent Without Memory（沒有記憶的代理）

**問題：** 代理每次回合從頭開始。

```python
# ANTI-PATTERN: Stateless agent
async def handle_message(message: str) -> str:
    return await agent.run(message)  # No context
```

**為何失敗：**
- 無法執行多回合任務
- 重複相同的錯誤
- 無法從經驗中學習
- 糟糕的使用者體驗

**解決方案：**
```python
# PATTERN: Persistent memory
async def handle_message(session_id: str, message: str) -> str:
    memory = await memory_store.get(session_id)
    response = await agent.run(message, memory=memory)
    await memory_store.update(session_id, memory)
    return response
```

---

## Prompting 反模式

### Vague Instructions（模糊指示）

**問題：** 模糊的 Prompt 期望特定的行為。

```python
# ANTI-PATTERN: Vague
prompt = "Help the user with their request."
```

**為何失敗：**
- 「幫助」的定義不明
- 沒有指定格式
- 沒有邊界
- 行為不一致

**解決方案：**
```python
# PATTERN: Specific and structured
prompt = """
You are a customer support agent for TechCorp.

Your role:
- Answer questions about our products
- Help troubleshoot issues
- Escalate to human when unsure

Response format:
1. Acknowledge the issue
2. Provide a solution or ask clarifying questions
3. Offer next steps

Do NOT:
- Make promises about refunds (escalate instead)
- Provide legal or medical advice
- Share internal company information
"""
```

---

### No Output Format（無輸出格式）

**問題：** 期望結構化輸出但未指定格式。

```python
# ANTI-PATTERN: Hope for structure
prompt = "Extract the person's name, date, and location from this text."
>>>>>>> Stashed changes
response = await llm.generate(prompt)
return response
```

**解決方案：**
<<<<<<< Updated upstream
- 實現重試邏輯（指數退避）
- 為不同錯誤類型提供回退
- 監控錯誤率並設置警報
=======
```python
# PATTERN: Explicit format
prompt = """
Extract information and return as JSON:
{
    "name": "string",
    "date": "YYYY-MM-DD",
    "location": "string"
}
>>>>>>> Stashed changes

```python
# 好：錯誤處理
async def generate_with_fallback(prompt: str) -> str:
    for attempt in range(3):
        try:
            return await llm.generate(prompt)
        except RateLimitError:
            await asyncio.sleep(2 ** attempt)
        except ValidationError:
            raise  # 不重試
    return await fallback_model.generate(prompt)
```

---

<<<<<<< Updated upstream
### 反模式：串行檢索和生成

**問題：** 等待檢索完成後才開始生成。
=======
## 評估反模式

### Vibes-Based Evaluation（直覺評估）

**問題：** 「我覺得看起來不錯」作為評估方法。
>>>>>>> Stashed changes

```python
# 不好：串行
docs = await retrieve(query)  # 等待完成
response = await generate(query, docs)  # 然後開始
```

<<<<<<< Updated upstream
**解決方案：**
- 預取下一個查詢的可能結果
- 流水線化檢索和生成
- 使用非阻塞操作

```python
# 好：並行
async def pipelined_query(query):
    # 啟動檢索
    docs_task = retrieve(query)
=======
**為何失敗：**
- 不可重現
-  cherry-picked 範例
- 沒有基線比較
- 遺漏邊界案例

**解決方案：**
```python
# PATTERN: Systematic evaluation
eval_dataset = load_eval_set()  # 100+ examples
results = []

for example in eval_dataset:
    response = await generate(example["input"])
    score = await evaluate(response, example["expected"])
    results.append(score)

metrics = {
    "accuracy": sum(results) / len(results),
    "failures": [e for e, r in zip(eval_dataset, results) if r < 0.5]
}
```

---

### Training on Test Set（在測試集上訓練）

**問題：** 使用評估數據做開發決策。

```python
# ANTI-PATTERN: Overfitting to eval
for iteration in range(100):
    accuracy = evaluate_on_test_set()  # Same set every time
    tweak_prompt_based_on_failures(test_set)  # Optimizing for test set
```

**為何失敗：**
- 過擬合特定範例
- 真實世界效能不同
- 沒有真正的泛化度量

**解決方案：**
```python
# PATTERN: Proper data splits
dev_set = load_dev_set()      # For iteration
test_set = load_test_set()    # Final evaluation only

# Iterate on dev set
for iteration in range(100):
    accuracy = evaluate(dev_set)
    improve_based_on(dev_set)

# Final evaluation on untouched test set
final_accuracy = evaluate(test_set)
```

---

## 生產反模式

### No Rate Limiting（無速率限制）

**問題：** 每位使用者無限的 LLM 呼叫。

```python
# ANTI-PATTERN: Open access
@app.route("/generate")
async def generate():
    return await llm.generate(request.prompt)  # No limits!
```

**為何失敗：**
- 單一使用者可能耗盡預算
- 拒絕服務風險
- 成本意外
- 沒有公平使用

**解決方案：**
```python
# PATTERN: Rate limiting
@app.route("/generate")
@rate_limit(requests_per_minute=10, requests_per_day=100)
@cost_limit(max_cost_per_day=1.0)
async def generate():
    return await llm.generate(request.prompt)
```

---

### No Caching（無快取）

**問題：** 每個相同請求都打到 LLM。

```python
# ANTI-PATTERN: No cache
async def answer_faq(question: str) -> str:
    return await llm.generate(question)  # Same FAQ, same cost every time
```

**為何失敗：**
- 相同查詢浪費金錢
- 不必要的延遲
- 對相同問題的回答不一致

**解決方案：**
```python
# PATTERN: Semantic caching
async def answer_faq(question: str) -> str:
    cached = await cache.get_similar(question, threshold=0.95)
    if cached:
        return cached.response
>>>>>>> Stashed changes
    
    # 同時準備提示
    prompt_task = prepare_prompt(query)
    
    # 等待兩者完成
    docs, prompt = await asyncio.gather(docs_task, prompt_task)
    
    return await generate(prompt, docs)
```

---

<<<<<<< Updated upstream
## 提示反模式

### 反模式：過於冗長的提示

**問題：** 提示包含過多指令，稀釋了重要資訊。

```python
# 不好：過度說明
prompt = """
你是一個專業的客服代表。
你為一家名為 XYZ 的公司工作。
公司成立於 2010 年。
總部位於紐約。
產品包括 A、B、C。
你應該專業、友好、準確、及時、恭敬、有禮貌...
（100 行後...）
回答這個問題：我的訂單在哪裡？
"""
```

**解決方案：**
- 保持提示簡潔
- 只包含相關指令
- 使用結構化格式

```python
# 好：精確
prompt = """
角色：專業客服
任務：訂單狀態查詢
要求：簡潔、準確
---
客戶問題：我的訂單在哪裡？
"""
```

---

### 反模式：缺乏負面例子

**問題：** 只說明做什麼，不說明不做什麼。

```python
# 不好：只有正面
prompt = """
回答問題時要準確。
"""

# 好：正面和負面
prompt = """
要做：
- 只基於提供的上下文回答
- 引用具體的文檔部分
- 承認不確定的情況

不要做：
- 猜測或編造資訊
- 引用你不知道的來源
- 忽視矛盾的上下文
"""
```

---

### 反模式：不一致的輸出格式

**問題：** 允許 LLM 任意選擇輸出格式。

```python
# 不好：自由格式
prompt = "解釋量子力學" → "量子力學是..."
# 或 "根據文檔..."

# 好：結構化格式
prompt = "以 JSON 格式回答：{question: string, answer: string, confidence: float}"
```

**解決方案：**
- 使用輸出模式/架構
- 使用解析友好的格式
- 驗證輸出結構

---

## 評估反模式

### 反模式：只使用 BLEU 分數

**問題：** 僅使用 BLEU 評估生成品質。

**為什麼這是問題：**
- BLEU 基於 n-gram 重疊，不捕獲語義
- 不適合開放式生成
- 對錶達方式過度敏感

**解決方案：**
- 使用多種指標（BLEU、ROUGE、BERT 分數）
- 包含品質評估（LLM 作為裁判）
- 進行人類評估

---

### 反模式：只在測試集上評估

**問題：** 僅在固定的測試集上測試，忽略生產性能。

**解決方案：**
- 在訓練/測試分割上評估
- 監控生產中的品質（抽樣）
- 追蹤漂移

---

## 面試題目

### Q：什麼是最常見的 LLM 系統錯誤？

**強烈回答：**

「最常見的錯誤是：

1. **忽略非確定性**：人們假設相同輸入總是產生相同輸出。實際上，溫度、隨機種子等都會影響輸出。生產系統需要處理這種變異性。

2. **無限制的上下文**：將所有內容放入上下文是一個常見錯誤。模型無法有效處理過長的上下文，而且成本會飆升。

3. **缺乏錯誤處理**：假設 LLM 調用總是會成功。實際上，速率限制、超時、提供商故障都很常見。

4. **只依賴 BLEU 分數**：BLEU 對生成任務來說是很差的指標，特別是開放式生成。

5. **單一提示適用所有情況**：不同的查詢類型需要不同的提示策略。」

### Q：如何防止「prompt 注入」？

**強烈回答：**

「Prompt 注入是透過使用者輸入引入惡意指令。主要預防措施：

1. **輸入驗證**：掃描常見的注入模式（如 'ignore previous'）

2. **上下文隔離**：確保來自外部來源的內容不能修改系統指令。使用隔離標記區分用戶輸入和系統指令。

3. **輸出監控**：檢查模型輸出是否包含異常模式

4. **LLM 裁判**：使用第二個模型檢測操縱意圖

5. **深度防禦**：沒有單一技術足夠，但多層防禦使攻擊難以成功。」

---

## 參考文獻

- Anthropic 安全最佳實踐
- OWASP LLM Top 10
- Prompt 注入攻擊類型

---

=======
## 面試問題

### Q: 你在 LLM 應用中看到的最大反模式是什麼？

**理想回答：**

「最具破壞性的是『God Prompt』反模式：單一巨大 Prompt 嘗試處理所有情境。

**為何常見：** 一開始用一個 Prompt 並根據需要添加指令似乎更簡單。

**為何失敗：**
- 上下文被指令消耗，而非使用者內容
- 衝突的指令混淆模型
- 無法為不同用例優化
- 變更有不可預測的副作用

**修復方法：** 路由到專業處理器。每個處理器有一個專注的 Prompt，針對一個任務優化。路由器本身可以很簡單（基於關鍵字）或智慧（對於複雜情況使用 LLM）。

這不僅限於 Prompt。總體原則是：將複雜性分解為專業元件，而不是將所有東西塞進一個龐然大物。」

### Q: 你如何避免代理失控成本？

**理想回答：**

「多個層級的不同限制：

**每請求限制：**
- 最大步數（例如 20）
- 最大 Token（例如 50K）
- 最大時間（例如 5 分鐘）

**每會話限制：**
- 每日 Token 預算
- 每日成本上限

**每使用者限制：**
- 速率限制（每分鐘/小時/天的請求）
- 成本歸因和上限

**監控：**
- 即時成本追蹤
- 異常警報（單一請求 > $1）
- 如果成本飆升則斷路器

**架構：**
- 從便宜到昂貴模型串聯
- 快取常見操作
- 批次相似請求

關鍵是假設代理會嘗試永遠運行。在每個層級建立硬停止。我見過代理在沒有適當限制的情況下在幾分鐘內累積 $1000 的帳單。」

---

>>>>>>> Stashed changes
*上一篇：[設計模式](01-design-patterns.md)*