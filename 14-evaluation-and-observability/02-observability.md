# LLM 可觀測性

LLM 系統的可觀測性需要調整日誌、指標和追蹤這三個支柱，以適應 AI 應用程式的獨特特性。

## 目錄

- [為什麼 LLM 可觀測性不同](#為什麼-llm-可觀測性不同)
- [三個支柱](#三個支柱)
- [關鍵指標](#關鍵指標)
- [追蹤 LLM 管道](#追蹤-llm-管道)
- [品質監控](#品質監控)
- [成本追蹤](#成本追蹤)
- [警報策略](#警報策略)
- [可觀測性工具](#可觀測性工具)
- [面試題目](#面試題目)
- [參考文獻](#參考文獻)

---

## 為什麼 LLM 可觀測性不同

傳統可觀測性專注於：
- 請求/響應模式
- 延遲和吞吐量
- 錯誤率
- 資源利用率

LLM 系統增加了：
- **品質是一等公民指標**：一個快速、可用的系統產生不良輸出就是失敗
- **非確定性**：相同輸入可能產生不同輸出
- **代幣經濟學**：成本以複雜方式隨使用量擴展
- **多組件管道**：RAG 有檢索、重排名、生成步驟
- **主觀正確性**：通常沒有可比較的基本事實

---

## 三個支柱

### 日誌記錄

```python
class LLMLogger:
    def log_request(
        self,
        request_id: str,
        model: str,
        messages: list[dict],
        parameters: dict
    ):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "type": "llm_request",
            "model": model,
            "parameters": parameters,
            "input_tokens": self.count_tokens(messages),
            # 為隱私雜湊，完整內容在安全儲存中
            "content_hash": self.hash_content(messages)
        }
        self.logger.info(json.dumps(log_entry))
    
    def log_response(
        self,
        request_id: str,
        response: str,
        latency_ms: float,
        tokens: dict
    ):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "type": "llm_response",
            "latency_ms": latency_ms,
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "ttft_ms": tokens.get("ttft_ms"),
            "content_hash": self.hash_content(response)
        }
        self.logger.info(json.dumps(log_entry))
```

**要記錄的內容：**
- 用於關聯的請求 ID
- 模型和參數
- Token 數量
- 延遲（TTFT 和總計）
- 內容（如果是隱私敏感的則雜湊）

### 指標

```python
from prometheus_client import Counter, Histogram, Gauge

# 請求指標
llm_requests_total = Counter(
    "llm_requests_total",
    "LLM 請求總數",
    ["model", "status"]
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM 請求延遲",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

llm_ttft_seconds = Histogram(
    "llm_ttft_seconds",
    "到第一個 token 的時間",
    ["model"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
)

# Token 指標
tokens_used_total = Counter(
    "tokens_used_total",
    "消耗的 token 總數",
    ["model", "direction"]  # direction: input/output
)

# 成本指標
llm_cost_dollars = Counter(
    "llm_cost_dollars",
    "美元計費的 LLM 成本",
    ["model"]
)

# 品質指標（抽樣）
quality_score = Gauge(
    "llm_quality_score",
    "抽樣品質分數",
    ["model", "task_type"]
)
```

### 追蹤

RAG 管道的端到端追蹤：

```python
from opentelemetry import trace

tracer = trace.get_tracer("rag_pipeline")

async def rag_query(query: str) -> str:
    with tracer.start_as_current_span("rag_query") as span:
        span.set_attribute("query", query)
        
        # 嵌入步驟
        with tracer.start_as_current_span("embed_query") as embed_span:
            query_embedding = await embed(query)
            embed_span.set_attribute("embedding_dim", len(query_embedding))
        
        # 檢索步驟
        with tracer.start_as_current_span("vector_search") as search_span:
            results = await vector_db.search(query_embedding, top_k=10)
            search_span.set_attribute("results_count", len(results))
            search_span.set_attribute("top_score", results[0].score if results else 0)
        
        # 重排名步驟
        with tracer.start_as_current_span("rerank") as rerank_span:
            reranked = await reranker.rerank(query, results)
            rerank_span.set_attribute("reranked_count", len(reranked))
        
        # 生成步驟
        with tracer.start_as_current_span("generate") as gen_span:
            response = await llm.generate(query, context=reranked[:5])
            gen_span.set_attribute("model", llm.model)
            gen_span.set_attribute("output_tokens", count_tokens(response))
        
        return response
```

---

## 關鍵指標

### 操作指標

| 指標 | 描述 | 典型警報閾值 |
|--------|-------------|------------------------|
| 請求率 | 每秒請求數 | 異常檢測 |
| 錯誤率 | 失敗請求 / 總數 | > 5% |
| 延遲 p50 | 中位響應時間 | > 2秒 |
| 延遲 p95 | 第 95 百分位 | > 5秒 |
| 延遲 p99 | 第 99 百分位 | > 10秒 |
| TTFT | 到第一個 token 的時間 | > 1秒 |
| Token 吞吐量 | 每秒 token 數 | < 基線 |

### 品質指標

| 指標 | 描述 | 收集方法 |
|--------|-------------|-------------------|
| 品質分數 | LLM 作為裁判評級 | 抽樣（1-5%） |
| 忠實度 | RAG 答案基於上下文 | 抽樣 |
| 相關性 | 答案回答問題 | 抽樣 |
| 使用者滿意度 | 讚/踩、評分 | 使用者回饋 |
| 任務完成 | 使用者是否達到目標？ | 隱含信號 |

### 成本指標

| 指標 | 描述 | 粒度 |
|--------|-------------|-------------|
| 每請求成本 | 平均成本 | 每模型 |
| 每日成本 | 每日總支出 | 整體 + 每模型 |
| 每使用者操作成本 | 完成使用者目標的成本 | 每任務類型 |
| Token 效率 | 每 token 提供的價值 | 每用例 |

---

## 品質監控

### 抽樣策略

```python
class QualitySampler:
    def __init__(self, sample_rate: float = 0.05):
        self.sample_rate = sample_rate
        self.judge = LLMJudge()
    
    async def maybe_evaluate(
        self,
        request_id: str,
        query: str,
        context: list[str],
        response: str
    ):
        # 隨機抽樣
        if random.random() > self.sample_rate:
            return
        
        # 評估品質
        scores = await self.judge.evaluate(
            query=query,
            context=context,
            response=response,
            criteria=["relevance", "faithfulness", "helpfulness"]
        )
        
        # 記錄指標
        for criterion, score in scores.items():
            quality_score.labels(
                model=self.model,
                criterion=criterion
            ).set(score)
        
        # 儲存以供分析
        await self.store_evaluation(request_id, scores)
```

### 漂移檢測

```python
class QualityDriftDetector:
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.baseline_scores = []
        self.current_scores = []
    
    def add_score(self, score: float):
        self.current_scores.append(score)
        
        if len(self.current_scores) >= self.window_size:
            self.check_drift()
            self.current_scores = []
    
    def check_drift(self):
        if not self.baseline_scores:
            self.baseline_scores = self.current_scores.copy()
            return
        
        # 漂移的統計檢驗
        baseline_mean = np.mean(self.baseline_scores)
        current_mean = np.mean(self.current_scores)
        
        # 簡單的基於閾值的檢測
        drift_threshold = 0.1  # 10% 下降
        if (baseline_mean - current_mean) / baseline_mean > drift_threshold:
            self.alert_drift(baseline_mean, current_mean)
    
    def alert_drift(self, baseline: float, current: float):
        alert = {
            "type": "quality_drift",
            "baseline_score": baseline,
            "current_score": current,
            "degradation_pct": (baseline - current) / baseline * 100
        }
        self.send_alert(alert)
```

---

## 成本追蹤

### 即時成本計算

```python
class CostTracker:
    # 每百萬 token 的定價（驗證當前費率）
    PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3.5-haiku": {"input": 0.25, "output": 1.25},
    }
    
    def track(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        request_id: str
    ) -> float:
        pricing = self.PRICING.get(model, {"input": 0, "output": 0})
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        # 記錄指標
        llm_cost_dollars.labels(model=model).inc(total_cost)
        tokens_used_total.labels(model=model, direction="input").inc(input_tokens)
        tokens_used_total.labels(model=model, direction="output").inc(output_tokens)
        
        # 記錄日誌以供分析
        self.log_cost(request_id, model, input_tokens, output_tokens, total_cost)
        
        return total_cost
```

### 成本歸因

```python
class CostAttributor:
    def attribute_cost(
        self,
        request_id: str,
        user_id: str,
        team: str,
        use_case: str,
        cost: float
    ):
        # 儲存以供計費和分析
        attribution = {
            "request_id": request_id,
            "user_id": user_id,
            "team": team,
            "use_case": use_case,
            "cost": cost,
            "timestamp": datetime.utcnow()
        }
        
        self.store(attribution)
        
        # 更新運行總計
        self.update_user_total(user_id, cost)
        self.update_team_total(team, cost)
        
        # 檢查預算
        if self.exceeds_budget(team):
            self.alert_budget_exceeded(team)
```

---

## 警報策略

### 警報配置

```yaml
alerts:
  # 可用性
  - name: high_error_rate
    condition: error_rate > 0.05
    for: 5m
    severity: critical
    runbook: "檢查提供商狀態、驗證 API 金鑰、審查最近的變更"
    
  # 延遲
  - name: high_latency_p95
    condition: latency_p95 > 10s
    for: 5m
    severity: warning
    runbook: "檢查模型、減少上下文大小、驗證提供商狀態"
    
  # 成本
  - name: cost_spike
    condition: hourly_cost > 2 * rolling_avg_hourly_cost
    for: 1h
    severity: warning
    runbook: "檢查流量峰值、審查最近的部署、驗證緩存"
    
  # 品質
  - name: quality_degradation
    condition: avg_quality_score < 3.5 over 1h
    for: 30m
    severity: warning
    runbook: "審查最近的變更、檢查模型效能、抽樣響應"
    
  # 資源
  - name: rate_limit_approaching
    condition: rate_limit_usage > 0.8
    for: 15m
    severity: warning
    runbook: "考慮模型路由、實施背壓"
```

### 警報優先順序

| 嚴重性 | 響應時間 | 範例 |
|----------|---------------|----------|
| 關鍵 | < 15 分鐘 | 服務癱瘓、> 50% 錯誤率 |
| 高 | < 1 小時 | > 10% 錯誤率、P99 > 30秒 |
| 警告 | < 4 小時 | 品質下降、成本峰值 |
| 資訊 | 下一個工作日 | 趨勢變化、容量規劃 |

---

## 可觀測性工具

### LLM 特定工具

| 工具 | 焦點 | 最適合 |
|------|-------|----------|
| LangSmith | LangChain 追蹤 | 基於 LangChain 的應用 |
| Langfuse | 開源追蹤 | 自托管、隱私 |
| Weights & Biases | 實驗追蹤 | ML 團隊 |
| Arize Phoenix | LLM 監控 | 生產監控 |
| Helicone | API 代理日誌 | 簡單整合 |

### 整合示例：Langfuse

```python
from langfuse import Langfuse

langfuse = Langfuse()

async def traced_rag_query(query: str) -> str:
    # 開始追蹤
    trace = langfuse.trace(name="rag_query", input=query)
    
    # 嵌入範圍
    embed_span = trace.span(name="embed")
    embedding = await embed(query)
    embed_span.end()
    
    # 檢索範圍
    retrieve_span = trace.span(name="retrieve")
    results = await vector_db.search(embedding)
    retrieve_span.end(output={"count": len(results)})
    
    # 生成範圍
    gen_span = trace.generation(
        name="generate",
        model="gpt-4o",
        input={"query": query, "context": results}
    )
    response = await llm.generate(query, context=results)
    gen_span.end(output=response)
    
    # 結束追蹤
    trace.update(output=response)
    
    return response
```

---

## 面試題目

### Q：您會為生產 LLM 系統追蹤哪些指標？

**強烈回答：**

「我將指標組織為三個類別：

**操作指標：** 這是任何服務的基本要求。
- 請求率和錯誤率
- 延遲百分位：p50、p95、p99
- 到第一個 token 的時間（TTFT）用於串流
- 可用性

**品質指標：** 這是 LLM 可觀測性獨特之處。
- 使用 LLM 作為裁判的抽樣品質分數（1-5% 抽樣率）
- 對於 RAG：忠實度和相關性分數
- 使用者回饋：讚/踩、明確評分
- 任務完成率（可測量時）

**成本指標：**
- 按模型計算的每請求成本
- 每日/每週成本趨勢
- 每成功使用者操作的成本
- Token 效率

我為操作問題（錯誤率 > 5%、P95 > SLA）和品質漂移（平均分數比基線下降 10%）設定警報。成本警報有助於捕捉失控的使用量。

關鍵洞見是，一個快速、可用的 LLM 系統產生不良輸出仍然是在失敗。品質必須是一等公民指標。」

### Q：如何檢測生產中的品質下降？

**強烈回答：**

「檢測品質下降需要多層方法：

1. **持續抽樣**：隨機抽樣 1-5% 的請求進行深度評估
   - 使用 LLM 作為裁判評估品質
   - 追蹤趨勢而非單個值

2. **自動化閾值**：
   - 當平均分數低於 3.5（5 分制）時發出警告
   - 當分數比基線下降 10% 時發出警報

3. **使用者回饋循環**：
   - 追蹤讚/踩比率
   - 監控具有低評分的特定查詢類型

4. **分段分析**：
   - 按任務類型、使用者群組、模型版本追蹤
   - 隔離特定維度的下降

5. **漂移檢測**：
   - 保持基線分數窗口
   - 當當前分數與基線顯著偏離時警報

關鍵是不要只看平均值——追蹤分布並注意尾部（即低分數的比例）。」

---

## 參考文獻

- OpenTelemetry LLM Instrumentation
- Arize AI: LLM Observability Guide
- Langfuse Documentation

---

*上一篇：[LLM 評估](01-llm-evaluation.md)*