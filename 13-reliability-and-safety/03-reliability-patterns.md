# 可靠性模式

<<<<<<< Updated upstream
生產 LLM 系統需要超越基本重試邏輯的穩健可靠性模式。本章涵蓋構建彈性 AI 應用程式的高級模式。
=======
生產 LLM 系統需要超越基本重試邏輯的強健可靠性模式。本章涵蓋用於構建彈性 AI 應用程式的進階模式。
>>>>>>> Stashed changes

## 目錄

- [可靠性挑戰](#可靠性挑戰)
- [重試模式](#重試模式)
<<<<<<< Updated upstream
- [熔斷器](#熔斷器)
- [隔離模式](#隔離模式)
- [超時策略](#超時策略)
- [優雅降級](#優雅降級)
- [多提供商故障轉移](#多提供商故障轉移)
- [面試題目](#面試題目)
=======
- [斷路器](#斷路器)
- [隔離模式](#隔離模式)
- [超時策略](#超時策略)
- [優雅降級](#優雅降級)
- [多提供者故障轉移](#多提供者故障轉移)
- [面試問題](#面試問題)
>>>>>>> Stashed changes
- [參考文獻](#參考文獻)

---

## 可靠性挑戰

<<<<<<< Updated upstream
### LLM 特定的失敗模式

| 失敗模式 | 原因 | 影響 |
|--------------|-------|--------|
| 速率限制 | 超過配額 | 請求被拒絕 |
| 超時 | 生成時間長、網路問題 | 緩慢/失敗的響應 |
| 提供商故障 | 基礎設施問題 | 完全失敗 |
| 品質下降 | 模型更新、負載 | 更差的輸出 |
| 上下文溢出 | 輸入過大 | 請求失敗 |
| 格式錯誤輸出 | 生成錯誤 | 解析失敗 |

### 可靠性目標

| 等級 | 可用性 | 延遲 p99 | 範例 |
|------|--------------|-------------|----------|
| 關鍵 | 99.99% | < 3秒 | 支付處理 |
| 標準 | 99.9% | < 10秒 | 客戶支援 |
| 最大努力 | 99% | < 30秒 | 後台任務 |
=======
### LLM 特有故障模式

| 故障模式 | 原因 | 影響 |
|----------|------|------|
| 速率限制 | 超過配額 | 請求拒絕 |
| 逾時 | 長時間生成、網路問題 | 回應緩慢/失敗 |
| 提供者中斷 | 基礎設施問題 | 完全失敗 |
| 品質下降 | 模型更新、負載 | 輸出變差 |
| 上下文溢出 | 輸入太大 | 請求失敗 |
| 格式錯誤的輸出 | 生成錯誤 | 解析失敗 |

### 可靠性目標

| 層級 | 可用性 | 延遲 p99 | 範例 |
|------|--------|----------|------|
| 關鍵 | 99.99% | < 3s | 付款處理 |
| 標準 | 99.9% | < 10s | 客戶支援 |
| 盡力而為 | 99% | < 30s | 背景任務 |
>>>>>>> Stashed changes

---

## 重試模式

<<<<<<< Updated upstream
### 帶抖動的指數退避
=======
### 指數退避與抖動
>>>>>>> Stashed changes

```python
import random
import asyncio
from typing import TypeVar, Callable

T = TypeVar("T")

class RetryConfig:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: float = 0.5
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        # 添加抖動以防止雷鳴 herd
        jitter_range = delay * self.jitter
        delay += random.uniform(-jitter_range, jitter_range)
        return max(0, delay)


async def retry_with_backoff(
    func: Callable[[], T],
    config: RetryConfig,
    retryable_exceptions: tuple = (Exception,)
) -> T:
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except retryable_exceptions as e:
            last_exception = e
            
            if attempt == config.max_retries:
                break
            
            delay = config.get_delay(attempt)
            await asyncio.sleep(delay)
    
    raise last_exception
```

<<<<<<< Updated upstream
### 可重試 vs 不可重試錯誤
=======
### 可重試與不可重試錯誤
>>>>>>> Stashed changes

```python
class LLMRetryPolicy:
    RETRYABLE = [
        RateLimitError,
        TimeoutError,
        ServiceUnavailableError,
        ConnectionError
    ]
    
    NOT_RETRYABLE = [
        AuthenticationError,
        InvalidRequestError,
        ContentPolicyViolation,
        ContextLengthExceeded
    ]
    
    @classmethod
    def should_retry(cls, error: Exception) -> bool:
        for retryable_type in cls.RETRYABLE:
            if isinstance(error, retryable_type):
                return True
        return False
    
    @classmethod
    def get_retry_after(cls, error: Exception) -> float | None:
        # 某些速率限制錯誤包含 retry-after 標頭
        if hasattr(error, "retry_after"):
            return error.retry_after
        return None
```

---

<<<<<<< Updated upstream
## 熔斷器

### 實現
=======
## 斷路器

### 實作
>>>>>>> Stashed changes

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"      # 正常操作
    OPEN = "open"          # 故障中，拒絕請求
    HALF_OPEN = "half_open"  # 測試恢復

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: timedelta = timedelta(seconds=30)
    half_open_max_calls: int = 3
    success_threshold: int = 2  # 關閉所需的成功次數

class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.half_open_calls = 0
    
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # 檢查恢復超時是否已過
            if self._recovery_timeout_elapsed():
                self._transition_to_half_open()
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # 在半開狀態允許有限呼叫
            return self.half_open_calls < self.config.half_open_max_calls
        
        return False
    
    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        else:
            self.failure_count = 0
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self.failure_count >= self.config.failure_threshold:
            self._transition_to_open()
    
    def _transition_to_open(self):
        self.state = CircuitState.OPEN
        self.success_count = 0
    
    def _transition_to_half_open(self):
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0
    
    def _transition_to_closed(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
    
    def _recovery_timeout_elapsed(self) -> bool:
        if self.last_failure_time is None:
            return True
        return datetime.now() - self.last_failure_time >= self.config.recovery_timeout
```

<<<<<<< Updated upstream
### 與 LLM 客戶端一起使用
=======
### 與 LLM 用戶端一起使用
>>>>>>> Stashed changes

```python
class ResilientLLMClient:
    def __init__(self):
        self.circuit_breakers = {
            "openai": CircuitBreaker("openai", CircuitBreakerConfig()),
            "anthropic": CircuitBreaker("anthropic", CircuitBreakerConfig()),
        }
    
    async def generate(self, prompt: str, provider: str = "openai") -> str:
        cb = self.circuit_breakers[provider]
        
        if not cb.can_execute():
            raise CircuitOpenError(f"熔斷器為 {provider} 開啟")
        
        try:
            result = await self._call_provider(provider, prompt)
            cb.record_success()
            return result
        except RetryableError as e:
            cb.record_failure()
            raise
```

---

## 隔離模式

### 隔離資源

```python
import asyncio
from contextlib import asynccontextmanager

class Bulkhead:
    """
    隔離資源以防止級聯故障。
    """
    
    def __init__(
        self,
        name: str,
        max_concurrent: int,
        max_queued: int = 100
    ):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue_semaphore = asyncio.Semaphore(max_queued)
    
    @asynccontextmanager
    async def acquire(self, timeout: float = 30.0):
        # 檢查佇列容量
        if not self.queue_semaphore.locked():
            await self.queue_semaphore.acquire()
        else:
            raise BulkheadFullError(f"隔離區 {self.name} 佇列已滿")
        
        try:
            # 等待執行槽位
            acquired = await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=timeout
            )
            self.queue_semaphore.release()
            
            try:
                yield
            finally:
                self.semaphore.release()
        except asyncio.TimeoutError:
            self.queue_semaphore.release()
            raise BulkheadTimeoutError(f"隔離區 {self.name} 超時")


class BulkheadedLLMClient:
    def __init__(self):
        # 為不同工作負載分離隔離區
        self.bulkheads = {
            "realtime": Bulkhead("realtime", max_concurrent=50),
            "batch": Bulkhead("batch", max_concurrent=200),
            "critical": Bulkhead("critical", max_concurrent=10)
        }
    
    async def generate(
        self,
        prompt: str,
        priority: str = "realtime"
    ) -> str:
        bulkhead = self.bulkheads[priority]
        
        async with bulkhead.acquire():
            return await self._call_llm(prompt)
```

---

## 超時策略

### 分層超時

```python
class TimeoutConfig:
    def __init__(
        self,
        connection_timeout: float = 5.0,
        read_timeout: float = 30.0,
        total_timeout: float = 60.0
    ):
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.total_timeout = total_timeout


class TimeoutManager:
    def __init__(self, config: TimeoutConfig):
        self.config = config
    
    async def execute_with_timeout(self, func, *args, **kwargs):
        try:
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.total_timeout
            )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"請求超時，耗時 {self.config.total_timeout} 秒"
            )
```

### 自適應超時

```python
class AdaptiveTimeout:
    """
    基於觀察到的延遲調整超時。
    """
    
    def __init__(
        self,
        initial_timeout: float = 30.0,
        min_timeout: float = 10.0,
        max_timeout: float = 120.0,
        percentile: float = 0.99
    ):
        self.min_timeout = min_timeout
        self.max_timeout = max_timeout
        self.percentile = percentile
        self.latencies: list[float] = []
        self.current_timeout = initial_timeout
    
    def record_latency(self, latency: float):
        self.latencies.append(latency)
        
        # 保持最近 1000 個觀察
        if len(self.latencies) > 1000:
            self.latencies = self.latencies[-1000:]
        
        # 更新超時為百分位 + 緩衝
        if len(self.latencies) >= 10:
            sorted_latencies = sorted(self.latencies)
            idx = int(len(sorted_latencies) * self.percentile)
            p99_latency = sorted_latencies[idx]
            
            # 添加 20% 緩衝
            new_timeout = p99_latency * 1.2
            self.current_timeout = max(
                self.min_timeout,
                min(self.max_timeout, new_timeout)
            )
    
    def get_timeout(self) -> float:
        return self.current_timeout
```

---

## 優雅降級

<<<<<<< Updated upstream
### 降級級別
=======
### 降級層級
>>>>>>> Stashed changes

```python
class DegradationLevel(Enum):
    FULL = "full"           # 所有功能
    REDUCED = "reduced"     # 較少功能
    MINIMAL = "minimal"     # 僅核心
    CACHED = "cached"       # 僅緩存響應
    OFFLINE = "offline"     # 錯誤消息

class GracefulDegrader:
    def __init__(self):
        self.current_level = DegradationLevel.FULL
        self.health_checker = HealthChecker()
    
    async def get_response(self, query: str) -> str:
        level = await self.health_checker.get_degradation_level()
        
        if level == DegradationLevel.FULL:
            return await self.full_pipeline(query)
        
        elif level == DegradationLevel.REDUCED:
            # 跳過昂貴操作
            return await self.reduced_pipeline(query)
        
        elif level == DegradationLevel.MINIMAL:
            # 簡單模型，無檢索
            return await self.minimal_pipeline(query)
        
        elif level == DegradationLevel.CACHED:
            # 僅返回緩存響應
            cached = await self.cache.get_similar(query)
            if cached:
                return cached
            return "我遇到問題了。請稍後再試。"
        
        else:
            return "服務暫時不可用。"
    
    async def full_pipeline(self, query: str) -> str:
        # RAG + 前沿模型 + 集成驗證
        context = await self.retrieve(query)
        response = await self.generate(query, context, model="gpt-4o")
        verified = await self.verify(response)
        return verified
    
    async def reduced_pipeline(self, query: str) -> str:
        # RAG + 較小模型，無驗證
        context = await self.retrieve(query)
        return await self.generate(query, context, model="gpt-4o-mini")
    
    async def minimal_pipeline(self, query: str) -> str:
        # 使用最小模型直接生成
        return await self.generate(query, None, model="gpt-4o-mini")
```

---

<<<<<<< Updated upstream
## 多提供商故障轉移

### 提供商管理器
=======
## 多提供者故障轉移

### 提供者管理器
>>>>>>> Stashed changes

```python
class ProviderManager:
    def __init__(self):
        self.providers = {
            "primary": OpenAIProvider(),
            "secondary": AnthropicProvider(),
            "tertiary": GoogleProvider()
        }
        self.health = {name: True for name in self.providers}
        self.priority_order = ["primary", "secondary", "tertiary"]
    
    async def generate(self, request: dict) -> str:
        for provider_name in self.priority_order:
            if not self.health[provider_name]:
                continue
            
            provider = self.providers[provider_name]
            
            try:
                result = await provider.generate(request)
                return result
            except RetryableError as e:
                # 標記為不健康但繼續下一個提供商
                self.health[provider_name] = False
                asyncio.create_task(
                    self._health_check_later(provider_name)
                )
                continue
        
        raise AllProvidersUnavailableError()
    
    async def _health_check_later(self, provider_name: str):
        await asyncio.sleep(30)  # 等待後重試
        try:
            await self.providers[provider_name].health_check()
            self.health[provider_name] = True
        except:
            # 安排另一個檢查
            asyncio.create_task(self._health_check_later(provider_name))
```

<<<<<<< Updated upstream
---
=======
### 請求對沖
>>>>>>> Stashed changes

## 面試題目

### Q：如何處理 LLM 提供商的速率限制？

**強烈回答：**

「處理速率限制需要多層方法：

1. **預防**：實施速率限制，防止請求達到限制
   - 客戶端速率限制
   - 佇列管理
   - 請求去重

2. **檢測**：識別何時接近限制
   - 監控使用量與限制的比率
   - 追蹤 429 響應

3. **響應**：當達到限制時
   - 指數退避（使用 jitter 防止叢集效應）
   - 切換到備用提供商
   - 緩存響應用於重複查詢

4. **長期策略**：
   - 請求定價以鼓勵節儉使用
   - 模型路由到更便宜的模型
   - 回退到更簡單的流程」

### Q：什麼是熔斷器模式？何時使用？

**強烈回答：**

「熔斷器模式防止級聯故障。當服務持續失敗時，熔斷器「打開」並立即拒絕請求，而不是讓它們排队等待並最終也失敗。

工作原理：
- **關閉**：正常操作，記錄失敗
- **打開**：快速失敗，拒絕所有請求
- **半開**：測試恢復，允許有限請求

何時使用：
- 當您的服務依賴多個外部 LLM 提供商時
- 當單一提供商的問題不應影響其他提供商時
- 當您需要保護下游系統免受上游故障影響時

對於 LLM，我為每個提供商維護一個熔斷器，並在熔斷器打開時自動切換到備用。」

---

<<<<<<< Updated upstream
## 參考文獻

- Circuit Breaker Pattern: Martin Fowler
- AWS Architecture: Reliability Patterns
- Azure: Retry and Circuit Breaker patterns

---

*上一篇：[集成方法](02-ensemble-methods.md)*
=======
## 面試問題

### Q: 如何為 LLM 系統設計高可用性？

**理想回答：**

「我使用多層可靠性：

**帶退避的重試：** 指數退避與抖動處理瞬態故障。重要的是區分可重試（速率限制、逾時）和不可重試（認證、錯誤請求）錯誤。

**斷路器：** 如果提供者重複失敗，停止嘗試一段冷卻時間。這防止在死去的提供者上浪費延遲，並給它時間恢復。

**多提供者故障轉移：** 永遠不要依賴單一提供者。我配置主要/次要/第三順位，帶自動故障轉移。每個提供者有自己的斷路器。

**優雅降級：** 定義當沒有提供者可用時會發生什麼。更好的做法是返回降級的回應（更簡單的模型、快取的結果），而不是完全失敗。

**隔離：** 隔離不同的工作負載。批量處理激增不應該讓即時查詢當機。

關鍵見解是假設失敗。LLM API 比傳統 API 不可靠。設計時假設提供者會當機，因為它會。」

### Q: 斷路器和重試有什麼區別？

**理想回答：**

「它們解決不同問題：

**重試**處理瞬態故障。如果單一請求失敗，再試一次。它假設故障是獨立的，下一次嘗試可能成功。

**斷路器**處理系統性故障。如果許多請求都失敗了，完全停止嘗試。它假設下游系統不健康，重複嘗試浪費資源並減慢恢復。

**它們如何一起工作：**
1. 請求失敗 → 帶退避重試（嘗試 1、2、3）
2. 如果所有重試都失敗 → 斷路器記錄故障
3. N 次失敗後 → 斷路器打開，立即拒絕請求
4. 逾時後 → 斷路器半開，允許有限的測試請求
5. 如果測試成功 → 斷路器關閉，正常操作恢復

沒有斷路器：在中斷期間，每個請求都會等待所有重試後才失敗。延遲飆升，資源耗盡。

有斷路器：在偵測到中斷後，請求快速失敗。系統保持回應，可以故障轉移到替代方案。」

---

## 參考文獻

- Microsoft Resilience Patterns: https://learn.microsoft.com/en-us/azure/architecture/patterns/
- Netflix Hystrix: https://github.com/Netflix/Hystrix

---

*上一篇：[集成方法](02-ensemble-methods.md)*
>>>>>>> Stashed changes
