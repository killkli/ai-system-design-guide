# 可靠性模式

本章涵蓋用於構建可靠 LLM 系統的生產模式：重試、備用模型、斷路器、隔離、驗證和監控。

## 目錄

- [可靠性模式地圖](#可靠性模式地圖)
- [錯誤分類](#錯誤分類)
- [備用模型與多重提供者](#備用模型與多重提供者)
- [重試策略](#重試策略)
- [斷路器模式](#斷路器模式)
- [隔離模式](#隔離模式)
- [驗證模式](#驗證模式)
- [健康檢查](#健康檢查)
- [混沌工程](#混沌工程)
- [面試問題](#面試問題)

---

## 可靠性模式地圖

```
┌─────────────────────────────────────────────────────────────────┐
│                    RELIABILITY PATTERNS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │  REDUNDANCY  │    │   FAILFAST   │    │  OBSERVABILITY│   │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤    │
│  │ Multi-provider│    │ Circuit break│    │  Health check │    │
│  │ Fallback     │    │ Rate limit   │    │  Metrics      │    │
│  │ Load balancer│    │ Timeout      │    │  Alerting     │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │  ISOLATION   │    │  VALIDATION  │    │   RETRY      │    │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤    │
│  │ Bulkhead     │    │ Input verify │    │ Exponential  │    │
│  │ Tenant iso.  │    │ Output check │    │ Jitter       │    │
│  │ Sandbox      │    │ Schema valid │    │ Retry budget │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 錯誤分類

### LLM 錯誤類型

```python
class LLMErrorType(Enum):
    # Transient (retry may help)
    RATE_LIMITED = "rate_limited"           # 429
    TIMEOUT = "timeout"                     # Request timeout
    SERVICE_UNAVAILABLE = "unavailable"     # 503
    SERVER_ERROR = "server_error"           # 500
    NETWORK_ERROR = "network"               # Connection failure
    
    # Permanent (retry won't help)
    AUTHENTICATION_ERROR = "auth"           # 401
    INVALID_REQUEST = "invalid_request"     # 400
    CONTENT_FILTERED = "content_filtered"   # Policy violation
    CONTEXT_LENGTH = "context_too_long"     # 400
    MODEL_NOT_FOUND = "model_not_found"     # 404
    NOT_FOUND = "not_found"                # 404
    
    # Partial failure (may have partial output)
    PARTIAL_RESPONSE = "partial"            # Stream interrupted
    TRUNCATED = "truncated"                # Max tokens reached

def classify_error(response: Response) -> LLMErrorType:
    """Classify error to determine retry strategy."""
    
    if response.status == 429:
        return LLMErrorType.RATE_LIMITED
    elif response.status == 400:
        if "context" in response.error.lower():
            return LLMErrorType.CONTEXT_LENGTH
        return LLMErrorType.INVALID_REQUEST
    elif response.status == 401:
        return LLMErrorType.AUTHENTICATION_ERROR
    elif response.status >= 500:
        return LLMErrorType.SERVER_ERROR
    elif response.status == 503:
        return LLMErrorType.SERVICE_UNAVAILABLE
    elif response.timeout:
        return LLMErrorType.TIMEOUT
    else:
        return LLMErrorType.UNKNOWN
```

### 錯誤決策樹

```
Error occurred
    │
    ├── Is it transient? (rate limit, timeout, server error)
    │   └── YES → Retry with backoff
    │
    ├── Is it permanent? (auth, invalid request)
    │   └── YES → Fail immediately, fix request
    │
    └── Is it partial? (truncated, interrupted)
        └── YES → Attempt to use partial or retry
```

---

## 備用模型與多重提供者

### 多提供者客戶端

```python
class MultiProviderClient:
    """
    Production multi-provider implementation with fallback.
    
    Key principles:
    1. Providers tried in order of preference
    2. Each provider tracks its own health
    3. Latency budgets prevent slow providers blocking
    """
    
    def __init__(self, providers: list[Provider], default_provider: str):
        self.providers = {p.name: p for p in providers}
        self.default_provider = default_provider
        self.health_tracker = HealthTracker()
    
    async def generate(
        self,
        prompt: str,
        model: str = None,
        timeout: float = 30.0,
        fallback_enabled: bool = True
    ) -> GenerationResult:
        start_time = time.time()
        attempted_providers = []
        
        # Try providers in order
        provider_order = self._get_provider_order(model)
        
        for provider_name in provider_order:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Exhausted {len(attempted_providers)} providers within {timeout}s")
            
            provider = self.providers[provider_name]
            attempted_providers.append(provider_name)
            
            try:
                result = await provider.generate(prompt, model=model)
                self.health_tracker.record_success(provider_name)
                return result
                
            except RateLimitError as e:
                # Record failure, try next provider
                self.health_tracker.record_failure(provider_name)
                wait_time = e.retry_after or 1.0
                await asyncio.sleep(wait_time)
                continue
                
            except ServiceError as e:
                self.health_tracker.record_failure(provider_name)
                continue  # Try next provider
                
            except (AuthenticationError, InvalidRequestError) as e:
                # Permanent errors - don't retry with another provider
                raise
        
        # All providers failed
        raise AllProvidersFailedError(
            attempted=attempted_providers,
            last_error=e
        )
    
    def _get_provider_order(self, model: str) -> list[str]:
        """Determine provider priority order."""
        
        # Check model availability
        available = [
            name for name, p in self.providers.items()
            if model in p.available_models
        ]
        
        # Sort by health score (prefer healthier providers)
        scored = [
            (name, self.health_tracker.get_score(name))
            for name in available
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [name for name, _ in scored]
```

### 模型路由

```python
class ModelRouter:
    """
    Route requests to appropriate model based on task complexity.
    
    Key insight: Simple queries don't need frontier models.
    Route to cheapest sufficient model.
    """
    
    COMPLEXITY_CLASSIFIER = "gpt-4o-mini"
    
    async def route(self, query: str) -> str:
        complexity = await self._classify_complexity(query)
        
        if complexity == "simple":
            return "gpt-4o-mini"
        elif complexity == "medium":
            return "claude-3.5-haiku"
        elif complexity == "complex":
            return "gpt-4o"
        else:
            return "claude-3.5-sonnet"
    
    async def _classify_complexity(self, query: str) -> str:
        prompt = f"""
Classify this query complexity: {query}

Options:
- simple: Factual Q&A, simple transformations, short responses
- medium: Analysis, explanations, multi-step reasoning
- complex: Creative writing, code generation, multi-document synthesis

Respond with just one word.
"""
        result = await llm.generate(prompt)
        return result.lower().strip()
```

---

## 重試策略

### 指數退避與抖動

```python
async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True
) -> Any:
    """
    Exponential backoff with jitter prevents thundering herd.
    
    Formula: delay = min(base_delay * 2^attempt + random(0, delay/2), max_delay)
    """
    
    for attempt in range(max_attempts):
        try:
            return await func()
            
        except TransientError as e:
            if attempt == max_attempts - 1:
                raise  # Last attempt, propagate error
            
            # Calculate delay
            delay = min(base_delay * (2 ** attempt), max_delay)
            
            if jitter:
                # Add jitter: ±25% of delay
                delay = delay * (0.75 + random.random() * 0.5)
            
            logger.warning(
                f"Attempt {attempt + 1} failed: {e}. "
                f"Retrying in {delay:.2f}s"
            )
            await asyncio.sleep(delay)
        
        except PermanentError:
            raise  # Don't retry permanent errors

# Usage
result = await retry_with_backoff(
    lambda: llm.generate(prompt),
    max_attempts=3,
    base_delay=2.0
)
```

### 重試預算追蹤

```python
class RetryBudget:
    """
    Track retry budget per user/request to prevent runaway retry loops.
    
    Critical for:
    - Rate limit loops (user keeps retrying 429s)
    - Cost control (infinite retries = infinite cost)
    """
    
    def __init__(
        self,
        max_retries: int = 5,
        max_retry_cost: float = 1.00,
        window_seconds: int = 60
    ):
        self.max_retries = max_retries
        self.max_retry_cost = max_retry_cost
        self.window = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)
        self.costs: dict[str, list[float]] = defaultdict(list)
    
    def can_retry(self, request_id: str, estimated_cost: float = 0.01) -> bool:
        now = time.time()
        
        # Clean old entries
        self.attempts[request_id] = [
            t for t in self.attempts[request_id]
            if now - t < self.window
        ]
        self.costs[request_id] = [
            c for c in self.costs[request_id]
            if now - c < self.window
        ]
        
        # Check budget
        if len(self.attempts[request_id]) >= self.max_retries:
            return False
        
        if sum(self.costs[request_id]) + estimated_cost > self.max_retry_cost:
            return False
        
        return True
    
    def record_attempt(self, request_id: str, cost: float):
        self.attempts[request_id].append(time.time())
        self.costs[request_id].append(cost)
```

---

## 斷路器模式

### 斷路器實現

```python
class CircuitBreaker:
    """
    Circuit breaker prevents cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 3,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.half_open_max_calls = half_open_max_calls
        
        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
    
    async def call(self, func: Callable) -> Any:
        # Check if circuit should transition
        self._check_transition()
        
        if self.state == self.OPEN:
            raise CircuitOpenError(
                f"Circuit open. Retry after {self.recovery_timeout}s"
            )
        
        if self.state == self.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitOpenError("Half-open call limit reached")
            self.half_open_calls += 1
        
        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _check_transition(self):
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit transitioned: OPEN -> HALF_OPEN")
    
    def _on_success(self):
        self.failure_count = 0
        
        if self.state == self.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = self.CLOSED
                self.success_count = 0
                logger.info("Circuit transitioned: HALF_OPEN -> CLOSED")
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
            logger.warning("Circuit transitioned: HALF_OPEN -> OPEN")
        elif self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning("Circuit transitioned: CLOSED -> OPEN")
```

### 生產斷路器配置

```yaml
circuit_breakers:
  gpt-4o:
    failure_threshold: 5      # Open after 5 failures
    recovery_timeout: 30      # Try again after 30s
    success_threshold: 3      # Need 3 successes to close
    half_open_max_calls: 3    # Allow 3 test calls
    
  claude-3.5-sonnet:
    failure_threshold: 3
    recovery_timeout: 60
    success_threshold: 2
    half_open_max_calls: 2
    
  rate_limit_strategy:
    strategy: "exponential_backoff"  # or "queue" or "drop"
    initial_delay: 1.0
    max_delay: 60.0
```

---

## 隔離模式

### 隔板模式

隔離不同優先級的工作負載：

```
┌─────────────────────────────────────────────────────────────────┐
│                    BULKHEAD PATTERN                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Priority Traffic:                                              │
│  ┌──────────────────────────────────────────────────┐          │
│  │ Pool A (max 10 concurrent)                       │          │
│  │ - Enterprise customers                            │          │
│  │ - Critical operations                             │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                  │
│  Standard Traffic:                                              │
│  ┌──────────────────────────────────────────────────┐          │
│  │ Pool B (max 50 concurrent)                       │          │
│  │ - Regular customers                              │          │
│  │ - Non-critical operations                         │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                  │
│  Best Effort Traffic:                                          │
│  ┌──────────────────────────────────────────────────┐          │
│  │ Pool C (max 100 concurrent)                      │          │
│  │ - Analytics, batch                               │          │
│  │ - Can be deprioritized                           │          │
│  └──────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

```python
class BulkheadExecutor:
    """
    Bulkhead pattern with semaphore-based concurrency control.
    """
    
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self.rejected_count = 0
    
    async def execute(self, func: Callable) -> Any:
        if not self.semaphore.locked():
            async with self.semaphore:
                self.active_count += 1
                try:
                    return await func()
                finally:
                    self.active_count -= 1
        else:
            self.rejected_count += 1
            raise RejectedExecutionError("Bulkhead pool exhausted")
```

---

## 驗證模式

### 輸出驗證

```python
class OutputValidator:
    """
    Validate LLM outputs before returning to users.
    
    Checks:
    - Format (JSON if expected)
    - Schema compliance
    - Content safety
    - Relevance to query
    """
    
    def __init__(self):
        self.schema_validator = SchemaValidator()
        self.safety_checker = SafetyChecker()
        self.relevance_checker = RelevanceChecker()
    
    async def validate(
        self,
        output: str,
        expected_format: str,
        query: str,
        context: list[str]
    ) -> ValidationResult:
        
        # Check format
        if expected_format == "json":
            try:
                parsed = json.loads(output)
            except json.JSONDecodeError as e:
                return ValidationResult(
                    valid=False,
                    reason=f"Invalid JSON: {e}",
                    should_retry=True
                )
        
        # Check schema
        schema_result = self.schema_validator.validate(parsed)
        if not schema_result.valid:
            return ValidationResult(
                valid=False,
                reason=f"Schema violation: {schema_result.errors}",
                should_retry=True
            )
        
        # Check safety
        safety_result = await self.safety_checker.check(output)
        if not safety_result.safe:
            return ValidationResult(
                valid=False,
                reason=f"Safety concern: {safety_result.reason}",
                should_retry=False  # Don't retry unsafe content
            )
        
        # Check relevance
        relevance_result = await self.relevance_checker.check(query, output, context)
        if relevance_result.score < 0.5:
            return ValidationResult(
                valid=False,
                reason=f"Low relevance: {relevance_result.score}",
                should_retry=True
            )
        
        return ValidationResult(valid=True)
```

---

## 健康檢查

### 詳細的健康檢查

```python
class LLMHealthCheck:
    """
    Comprehensive health check for LLM providers.
    """
    
    PROBE_PROMPT = "Respond with exactly: OK"
    EXPECTED_RESPONSE = "OK"
    
    async def check_provider(self, provider: Provider) -> HealthStatus:
        start = time.time()
        
        try:
            # Check latency
            response = await provider.generate(
                self.PROBE_PROMPT,
                timeout=5.0
            )
            latency = time.time() - start
            
            # Verify response
            if self.EXPECTED_RESPONSE not in response:
                return HealthStatus(
                    healthy=False,
                    latency=latency,
                    error="Unexpected response content"
                )
            
            return HealthStatus(
                healthy=True,
                latency=latency,
                error=None
            )
            
        except TimeoutError:
            return HealthStatus(
                healthy=False,
                latency=5.0,
                error="Timeout"
            )
        except Exception as e:
            return HealthStatus(
                healthy=False,
                latency=time.time() - start,
                error=str(e)
            )
```

### 健康檢查路由

```python
# Kubernetes readiness probe integration
@app.get("/ready")
async def readiness():
    results = await asyncio.gather(*[
        health_check.check_provider(p) for p in providers
    ])
    
    healthy = [r for r in results if r.healthy]
    
    if not healthy:
        return JSONResponse(
            status=503,
            content={"status": "unhealthy", "providers": results}
        )
    
    return {"status": "ready", "providers": results}
```

---

## 混沌工程

### 故障注入

```python
class ChaosEngine:
    """
    Inject failures to test system resilience.
    """
    
    def inject_latency(self, delay_ms: int):
        """Test timeout handling."""
        time.sleep(delay_ms / 1000)
    
    def inject_error(self, error_rate: float):
        """Randomly inject errors."""
        if random.random() < error_rate:
            raise InjectedError("Chaos injection")
    
    def inject_rate_limit(self, provider: str):
        """Simulate rate limiting."""
        raise RateLimitError("Chaos injection", retry_after=1.0)
    
    async def run_chaos_scenario(
        self,
        scenario: str,
        duration_seconds: int
    ):
        """Execute chaos scenario."""
        logger.warning(f"Starting chaos scenario: {scenario}")
        
        start = time.time()
        while time.time() - start < duration_seconds:
            if scenario == "provider_down":
                raise InjectedError("Provider chaos")
            elif scenario == "high_latency":
                self.inject_latency(5000)  # 5s delay
            elif scenario == "rate_limit":
                self.inject_rate_limit("openai")
            
            await asyncio.sleep(1)
```

---

## 面試問題

### Q: LLM 系統的重試策略應該考慮什麼？

**理想回答：**

「LLM 重試策略的關鍵考量：

**錯誤分類：**
- 瞬態錯誤（429、503、逾時）：應該重試
- 永久錯誤（401、400）：不重試，直接失敗
- 部分失敗（截斷）：取決於截斷多少

**退避策略：**
- 指數退避：delay = base * 2^attempt
- 抖動：delay *= (0.75 + random * 0.5)
- 防止雷鳴 herd：所有客戶同時重試是最糟糕的

**成本控制：**
- 重試預算：每請求最多 N 次重試
- 成本上限：總重試成本不超過某金額
- 時間窗口：滾動窗口內追蹤

**斷路器：**
- 連續失敗 N 次後打開
- 等待一段時間後進入半開狀態
- 測試幾次成功後關閉

**我對大多數 LLM 系統使用：**
- 最多 3 次重試，指數退避，base=1s，max=30s
- 429 錯誤特殊處理（尊重 Retry-After header）
- 不重試內容安全錯誤（無濟於事）」

### Q: 如何構建零當機的 LLM 服務切換？

**理想回答：**

「零當機切換的關鍵：

**健康追蹤：**
- 每個提供者維護健康分數
- 追蹤成功率、延遲、錯誤率
- 緩慢的提供者權重降低

**漸進式遷移：**
- 不要一次切換所有流量
- 1% → 5% → 25% → 100%
- 每個階段監控錯誤率和延遲

**預留實例：**
- 新提供者部署後先空跑
- 驗證輸出品質
- 然後開始轉移流量

**快速回滾：**
- 監控錯誤率飆升
- 自動回滾到上一個穩定提供者
- 設定明確的觸發條件

**斷路器防護：**
- 每個提供者有自己的斷路器
- 避免級聯故障
- 半開狀態測試恢復

核心原則：永遠不同時改變所有內容。漸進式變更、快速回滾、持續監控。」

---

*前一篇：[集成方法](02-ensemble-methods.md)*
