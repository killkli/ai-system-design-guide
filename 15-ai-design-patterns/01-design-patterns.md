# AI 設計模式

本章收錄構建 AI 系統的常見模式，類似於軟體工程中的設計模式。每個模式都包含使用時機、實施指導和取捨。

## 目錄

- [RAG 模式](#rag-模式)
- [智慧體模式](#智慧體模式)
- [優化模式](#優化模式)
- [可靠性模式](#可靠性模式)
- [成本模式](#成本模式)
- [面試題目](#面試題目)
- [參考文獻](#參考文獻)

---

## RAG 模式

### 模式：樸素 RAG

最簡單的 RAG 實現：

```
查詢 → 嵌入 → 檢索 → Top K → 填充到提示 → 生成
```

**使用時機：**
- MVP 和原型設計
- 簡單的問答
- 當檢索品質足夠時

**限制：**
- 無重排名
- 無查詢增強
- 可能檢索無關的區塊

---

### 模式：進階 RAG

具有多個階段的增強管道：

```
查詢 → 重寫 → 嵌入 → 混合檢索 → 重排名 → 過濾 → 生成
```

```python
class AdvancedRAG:
    async def query(self, user_query: str) -> str:
        # 步驟 1：查詢重寫
        enhanced_query = await self.rewrite_query(user_query)
        
        # 步驟 2：混合檢索
        semantic_results = await self.vector_search(enhanced_query, top_k=50)
        keyword_results = await self.bm25_search(enhanced_query, top_k=50)
        
        # 步驟 3：融合
        combined = self.reciprocal_rank_fusion(semantic_results, keyword_results)
        
        # 步驟 4：重排名
        reranked = await self.rerank(enhanced_query, combined[:20])
        
        # 步驟 5：使用頂部結果生成
        context = self.format_context(reranked[:5])
        return await self.generate(user_query, context)
```

**使用時機：**
- 生產系統
- 準確性很重要
- 複雜文檔集合

---

### 模式：父子檢索

檢索小子塊，返回較大的父區塊：

```
文檔
    └── 父區塊（2000 token）
            ├── 子區塊（200 token）← 在此檢索
            ├── 子區塊（200 token）
            └── 子區塊（200 token）
```

```python
class ParentChildRetriever:
    def __init__(self, vector_store):
        self.vector_store = vector_store
    
    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        # 在子區塊上搜尋（更精確）
        child_results = await self.vector_store.search(
            query, 
            collection="child_chunks",
            top_k=top_k * 3
        )
        
        # 獲取唯一的父區塊
        parent_ids = set(r.metadata["parent_id"] for r in child_results)
        
        # 返回父區塊（更多上下文）
        parents = await self.get_parents(list(parent_ids)[:top_k])
        return parents
```

**使用時機：**
- 需要檢索精確度
- 需要生成的上下文
- 文檔結構是分層的

---

### 模式：Self-RAG

模型決定何時以及檢索什麼：

```python
class SelfRAG:
    async def generate(self, query: str) -> str:
        # 步驟 1：決定是否需要檢索
        needs_retrieval = await self.assess_retrieval_need(query)
        
        if needs_retrieval:
            # 步驟 2：檢索
            context = await self.retrieve(query)
            
            # 步驟 3：評估相關性
            relevant_context = await self.filter_relevant(query, context)
            
            # 步驟 4：使用上下文生成
            response = await self.generate_with_context(query, relevant_context)
            
            # 步驟 5：自我批判
            is_supported = await self.check_support(response, relevant_context)
            if not is_supported:
                response = await self.regenerate(query, relevant_context)
        else:
            response = await self.generate_without_context(query)
        
        return response
```

**使用時機：**
- 混合知識（參數 + 檢索）
- 希望模型有選擇性
- 研究和實驗

---

### 模式：更正 RAG (CRAG)

評估和更正檢索品質：

```python
class CorrectiveRAG:
    async def query(self, user_query: str) -> str:
        # 初始檢索
        docs = await self.retrieve(user_query)
        
        # 為每個文檔評級
        graded = []
        for doc in docs:
            grade = await self.grade_relevance(user_query, doc)
            graded.append((doc, grade))
        
        # 對結果分類
        relevant = [d for d, g in graded if g == "relevant"]
        ambiguous = [d for d, g in graded if g == "ambiguous"]
        
        if len(relevant) >= 3:
            # 足夠的相關文檔
            context = relevant
        elif len(relevant) + len(ambiguous) >= 2:
            # 優化模糊的文檔
            refined = await self.refine_search(user_query, ambiguous)
            context = relevant + refined
        else:
            # 網路搜尋回退
            web_results = await self.web_search(user_query)
            context = relevant + web_results
        
        return await self.generate(user_query, context)
```

**使用時機：**
- 不可靠的文檔語料庫
- 需要高準確性
- 可以負擔品質檢查的延遲

---

## 智慧體模式

### 模式：ReAct

交錯推理和行動：

```
思考 → 行動 → 觀察 → 思考 → 行動 → 觀察 → 答案
```

見[智慧體架構](../07-agentic-systems/01-agent-architectures.md)以獲取實施。

**使用時機：**
- 通用智慧體
- 可解釋的決策
- 中等複雜度任務

---

### 模式：計劃與執行

先創建計劃，然後執行步驟：

```python
class PlanAndExecuteAgent:
    async def run(self, task: str) -> str:
        # 步驟 1：創建計劃
        plan = await self.create_plan(task)
        
        # 步驟 2：執行每個步驟
        results = []
        for step in plan.steps:
            result = await self.execute_step(step, results)
            results.append(result)
            
            # 需要時重新規劃
            if result.needs_replanning:
                plan = await self.replan(task, results)
        
        # 步驟 3：綜合最終答案
        return await self.synthesize(task, results)
    
    async def create_plan(self, task: str) -> Plan:
        prompt = f"""
        創建完成此任務的逐步計劃：{task}
        
        返回 JSON：
        {{
            "steps": [
                {{"id": 1, "description": "...", "tool": "..."}},
                ...
            ]
        }}
        """
        return await self.llm.generate(prompt)
```

**使用時機：**
- 複雜的多步驟任務
- 需要可見計劃
- 任務受益於分解

---

### 模式：批評者/驗證者

一個智慧體生成，另一個批評：

```python
class CriticPattern:
    async def generate_with_critique(self, task: str, max_iterations: int = 3) -> str:
        response = await self.generator.generate(task)
        
        for i in range(max_iterations):
            # 批評回應
            critique = await self.critic.evaluate(task, response)
            
            if critique.is_acceptable:
                break
            
            # 使用回饋重新生成
            response = await self.generator.regenerate(
                task, 
                previous=response,
                feedback=critique.feedback
            )
        
        return response
```

**使用時機：**
- 品質至關重要
- 可以負擔額外延遲
- 任務有明確的成功標準

---

### 模式：分層智慧體

管理者委派給專家工作者：

```python
class ManagerAgent:
    def __init__(self):
        self.workers = {
            "research": ResearchAgent(),
            "coding": CodingAgent(),
            "writing": WritingAgent(),
        }
    
    async def run(self, task: str) -> str:
        # 分析任務並委派
        subtasks = await self.decompose(task)
        
        # 並行執行相關的子任務
        results = await asyncio.gather(*[
            self.workers[subtask.type].run(subtask.description)
            for subtask in subtasks
        ])
        
        # 綜合結果
        return await self.synthesize(results)
```

**使用時機：**
- 複雜的多領域任務
- 需要專業知識
- 可擴展到多個任務

---

## 優化模式

### 模式：快取

儲存和重用常見回應：

```python
class SemanticCache:
    def __init__(self, threshold: float = 0.95):
        self.cache = {}
        self.embedding_model = embed_model
        self.threshold = threshold
    
    async def get_or_generate(self, query: str, generator) -> str:
        # 檢查精確匹配
        if query in self.cache:
            return self.cache[query]
        
        # 檢查語義相似性
        query_embedding = await self.embedding_model.encode(query)
        
        for cached_query, (cached_embedding, response) in self.cache.items():
            similarity = cosine(query_embedding, cached_embedding)
            if similarity > self.threshold:
                return response
        
        # 生成新回應
        response = await generator(query)
        self.cache[query] = (query_embedding, response)
        
        return response
```

**使用時機：**
- 重複查詢
- 高流量系統
- 可以接受輕微延遲節省

---

### 模式：路由

將查詢導向最適合的模型或流程：

```python
class Router:
    def __init__(self):
        self.routes = {
            "simple": SimpleHandler(),
            "complex": ComplexHandler(),
            "creative": CreativeHandler(),
        }
        self.classifier = QueryClassifier()
    
    async def handle(self, query: str) -> str:
        # 分類查詢
        category = await self.classifier.classify(query)
        
        # 路由到適當的處理器
        handler = self.routes.get(category, self.routes["simple"])
        
        return await handler.process(query)
```

**使用時機：**
- 異質查詢類型
- 需要成本/品質平衡
- 多個專業模型

---

### 模式：熔斷器

防止級聯故障：

```python
class CircuitBreaker:
    def __init__(self, threshold: float = 0.5, timeout: int = 60):
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"
    
    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise CircuitOpenError()
        
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
```

**使用時機：**
- 外部 API 依賴
- 需要韌性
- 防止故障傳播

---

## 可靠性模式

### 模式：回退

當主要方法失敗時切換到備用：

```python
class FallbackHandler:
    async def generate(self, query: str) -> str:
        providers = ["openai", "anthropic", "google"]
        
        for provider in providers:
            try:
                return await self.call_provider(provider, query)
            except RetryableError:
                continue
        
        # 全部失敗，返回緩存或錯誤訊息
        return await self.get_cached_or_error(query)
```

**使用時機：**
- 多個 LLM 提供商
- 最大化可用性
- 關鍵任務應用

---

### 模式：限流

控制請求速率以防止過載：

```python
class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests = deque(maxlen=requests_per_minute)
    
    async def acquire(self):
        now = time.time()
        
        # 清除一分鐘前的請求
        while self.requests and self.requests[0] < now - 60:
            self.requests.popleft()
        
        if len(self.requests) >= self.rpm:
            wait_time = 60 - (now - self.requests[0])
            await asyncio.sleep(wait_time)
        
        self.requests.append(now)
```

**使用時機：**
- API 速率限制
- 防止過載
- 成本控制

---

## 成本模式

### 模式：模型路由

根據查詢複雜度選擇模型：

```python
class ModelRouter:
    def __init__(self):
        self.simple_model = "gpt-4o-mini"
        self.complex_model = "gpt-4o"
        self.classifier = ComplexityClassifier()
    
    async def generate(self, query: str) -> str:
        complexity = await self.classifier.classify(query)
        
        if complexity == "simple":
            return await self.llm.generate(query, model=self.simple_model)
        else:
            return await self.llm.generate(query, model=self.complex_model)
```

**成本節省：** 簡單查詢使用 mini 模型可節省 95%。

---

### 模式：Token 預算

限制上下文大小以控制成本：

```python
class TokenBudgetManager:
    def __init__(self, max_tokens: int = 128000):
        self.max_tokens = max_tokens
        self.target_budget = int(max_tokens * 0.8)  # 保留 20% 用於輸出
    
    async def build_context(self, query: str, docs: list) -> list:
        """智慧地選擇要包含的文檔以保持在預算內"""
        selected = []
        current_tokens = self.count_tokens(query)
        
        for doc in sorted_by_relevance(docs):
            doc_tokens = self.count_tokens(doc)
            
            if current_tokens + doc_tokens <= self.target_budget:
                selected.append(doc)
                current_tokens += doc_tokens
            else:
                break
        
        return selected
```

**使用時機：**
- 大上下文模型
- 成本控制
- 需要預測性支出

---

## 面試題目

### Q：何時使用 Advanced RAG 而非 Naive RAG？

**強烈回答：**

「Naive RAG 適用於：
- 早期原型和 MVP
- 簡單的問答系統
- 當您只需要基本功能時

Advanced RAG 適用於：
- 生產系統需要高準確性
- 複雜文檔集或異質內容
- 需要處理查詢模糊性或需要多步推理
- 使用者期望高品質回應

關鍵區別是 Advanced RAG 在檢索後增加了重排名步驟，以及在檢索前增加了查詢重寫。這有助於：
1. 更好地理解用戶意圖
2. 混合搜尋（向量 + 關鍵字）捕获更多相關文檔
3. 重排名確保最相關的文檔在頂部
4. 過濾去除不相關的結果」

### Q：什麼是 Self-RAG？何時使用？

**強烈回答：**

「Self-RAG 是一種讓模型自己決定是否需要檢索的模式。傳統 RAG 總是檢索，而 Self-RAG 模型評估：
1. 是否需要外部知識
2. 檢索的文檔是否相關
3. 回應是否被文檔支持

使用時機：
- 混合知識任務（部分可以從模型參數回答，部分需要檢索）
- 當您希望模型有選擇性以減少不必要的檢索
- 研究和實驗環境
- 當延遲是考量時（避免不必要的檢索）

限制是模型需要額外的步驟來評估，這可能增加延遲。」

---

## 參考文獻

- Meta 的 Self-RAG 論文
- RAG 架構模式：Pinecone 指南
- 設計模式：Martin Fowler

---

*上一篇：[可觀測性](14-evaluation-and-observability/02-observability.md)*