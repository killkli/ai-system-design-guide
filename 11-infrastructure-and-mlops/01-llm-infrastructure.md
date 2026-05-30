# LLM 基礎設施

建構生產 LLM 系統需要了解部署選項、擴展模式和營運考量。本章涵蓋基礎設施層。

## 目錄

- [部署選項](#deployment-options)
- [服務架構](#serving-architecture)
- [擴展模式](#scaling-patterns)
- [成本管理](#cost-management)
- [監控和警報](#monitoring-and-alerting)
- [災難復原](#disaster-recovery)
- [2026 年 5 月 AI 加速器景觀](#may-2026-ai-accelerator-landscape)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## 部署選項

### API 對比 自託管

| 因素 | API 提供者 | 自託管 |
|--------|---------------|-------------|
| 設定時間 | 分鐘 | 天到週 |
| 操作負擔 | 無 | 顯著 |
| 低容量成本 | 較低 | 較高（固定成本） |
| 高容量成本 | 較高 | 較低（規模經濟） |
| 延遲控制 | 有限 | 完全控制 |
| 資料隱私 | 資料離開您的基礎設施 | 資料留在本地 |
| 模型選擇 | 提供者的模型 | 任何開源模型 |
| 自訂 | 透過 API 微調 | 完全控制 |

### 何時使用 API 提供者

```python
# 決策框架
def should_use_api(requirements: dict) -> bool:
    # API 的強信號
    if requirements["time_to_market"] == "urgent":
        return True
    if requirements["query_volume"] < 100_000_per_month:
        return True
    if requirements["team_ml_expertise"] == "low":
        return True
    
    # 自託管的強信號
    if requirements["data_residency"] == "strict":
        return False
    if requirements["latency_p99_ms"] < 100:
        return False
    if requirements["query_volume"] > 10_000_000_per_month:
        return False
    
    # 預設為 API 以保持簡單
    return True
```

### 自託管選項

| 選項 | 複雜度 | 效能 | 使用案例 |
|--------|------------|-------------|----------|
| vLLM | 中 | 優秀 | 生產服務 |
| TGI (HuggingFace) | 中 | 非常好 | HuggingFace 生態系統 |
| TensorRT-LLM | 高 | 最佳（NVIDIA） | 最大效能 |
| Ollama | 低 | 良好 | 開發、小規模 |
| llama.cpp | 低 | 良好 | CPU 推論、邊緣 |

---

## 服務架構

### 單一模型服務

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   Gateway   │────▶│  LLM Server │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Cache    │
                    └─────────────┘
```

### 多模型服務

```
                    ┌─────────────────────────────── │
                    │         Load Balancer          │
                    └───────────────┬────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
    │  GPT-4 Pool   │       │  Claude Pool  │       │ Llama 70B Pool│
    │  (API calls)  │       │  (API calls)  │       │ (self-hosted) │
    └───────────────┘       └───────────────┘       └───────────────┘
```

### 模型路由器模式

```python
class ModelRouter:
    def __init__(self):
        self.models = {
            "simple": GPT4oMini(),
            "complex": Claude35Sonnet(),
            "code": Claude35Sonnet(),
            "long_context": Gemini15Pro(),
            "vision": GPT4o()
        }
        self.classifier = QueryClassifier()
    
    async def route(self, request: Request) -> Response:
        # 分類請求類型
        request_type = self.classifier.classify(request)
        
        # 路由到適當的模型
        model = self.models[request_type]
        
        # 使用備用執行
        try:
            return await model.generate(request)
        except RateLimitError:
            return await self.fallback(request, request_type)
    
    async def fallback(self, request: Request, original_type: str) -> Response:
        # 定義備用順序
        fallbacks = {
            "simple": ["complex", "long_context"],
            "complex": ["simple"],
            "code": ["complex"]
        }
        
        for fallback_type in fallbacks.get(original_type, []):
            try:
                return await self.models[fallback_type].generate(request)
            except Exception:
                continue
        
        raise ServiceUnavailableError("All models unavailable")
```

---

## 擴展模式

### 水平擴展

```python
# Kubernetes HPA 配置用於 LLM 服務
hpa_config = """
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: llm-service
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: requests_per_second
      target:
        type: AverageValue
        averageValue: 100
"""
```

### 自託管的 GPU 擴展

| 規模 | GPU | 建議設定 |
|-------|------|-----------------|
| 開發/測試 | 1 | 單一 A10G 或 L4 |
| 小型生產 | 2-4 | 2x A100 搭配張量並行 |
| 中型生產 | 4-8 | 4x H100 搭配張量並行 |
| 大型生產 | 8+ | 多節點搭配管線並行 |

### 基於佇列的架構

用於高吞吐量非同步工作負載：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Producers  │────▶│    Queue    │────▶│  Consumers  │
└─────────────┘     │  (Redis/    │     │  (LLM       │
                    │   SQS)      │     │   Workers)  │
                    └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  Results    │
                                        │  Store      │
                                        └─────────────┘
```

```python
class AsyncLLMProcessor:
    def __init__(self):
        self.queue = RedisQueue("llm_requests")
        self.results = RedisResults("llm_results")
    
    async def submit(self, request: Request) -> str:
        request_id = generate_id()
        await self.queue.enqueue({
            "id": request_id,
            "request": request.to_dict()
        })
        return request_id
    
    async def get_result(self, request_id: str, timeout: int = 300) -> Response:
        return await self.results.wait_for(request_id, timeout)
    
    # 工作者處理序
    async def worker_loop(self):
        while True:
            job = await self.queue.dequeue()
            try:
                result = await self.llm.generate(job["request"])
                await self.results.store(job["id"], result)
            except Exception as e:
                await self.results.store_error(job["id"], str(e))
```

---

## 成本管理

### 成本追蹤

```python
class CostTracker:
    # 截至 2025 年 12 月的定價（驗證當前費率）
    PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00},  # 每 1M token
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3.5-haiku": {"input": 0.25, "output": 1.25},
    }
    
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        pricing = self.PRICING[model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def track(self, request_id: str, model: str, tokens: dict):
        cost = self.calculate_cost(
            model,
            tokens["input"],
            tokens["output"]
        )
        
        self.metrics.record(
            "llm_cost",
            cost,
            tags={"model": model, "request_id": request_id}
        )
        
        return cost
```

### 成本優化策略

| 策略 | 節省 | 實施 |
|----------|---------|----------------|
| 模型路由 | 50-80% | 將簡單查詢路由到便宜模型 |
| 快取 | 30-70% | 快取常見查詢 |
| 提示優化 | 10-30% | 更短的提示、結構化輸出 |
| 批次 API | 50% | 使用批次端點用於非同步工作 |
| 自託管 | 可變 | 在規模上可能更便宜 |

### 預算警報

```python
class BudgetManager:
    def __init__(self, daily_budget: float, alert_threshold: float = 0.8):
        self.daily_budget = daily_budget
        self.alert_threshold = alert_threshold
    
    async def check_and_alert(self):
        today_cost = await self.get_today_cost()
        utilization = today_cost / self.daily_budget
        
        if utilization >= 1.0:
            await self.alert("CRITICAL: Daily budget exceeded", today_cost)
            # 考慮啟用成本控制
            await self.enable_rate_limiting()
        elif utilization >= self.alert_threshold:
            await self.alert("WARNING: Approaching daily budget", today_cost)
    
    async def enable_rate_limiting(self):
        # 減少吞吐量以保持在預算內
        self.rate_limiter.set_rate(
            requests_per_minute=self.calculate_safe_rate()
        )
```

---

## 監控和警報

### 關鍵指標

```python
LLM_METRICS = {
    # 延遲
    "ttft_seconds": "Time to first token",
    "total_latency_seconds": "Total request time",
    
    # 吞吐量
    "requests_per_second": "Request rate",
    "tokens_per_second": "Token generation rate",
    
    # 資源
    "gpu_utilization": "GPU compute usage",
    "gpu_memory_utilization": "GPU memory usage",
    "kv_cache_utilization": "KV cache usage",
    
    # 品質（抽樣）
    "quality_score": "LLM-as-judge score",
    "faithfulness_score": "RAG faithfulness",
    
    # 錯誤
    "error_rate": "Failed requests percentage",
    "rate_limit_hits": "Rate limit rejections",
    
    # 成本
    "cost_per_request": "Average cost per request",
    "daily_cost": "Total daily spend"
}
```

### 警報配置

```yaml
alerts:
  - name: high_error_rate
    condition: error_rate > 0.05
    for: 5m
    severity: critical
    
  - name: high_latency
    condition: p99_latency > 10s
    for: 5m
    severity: warning
    
  - name: cost_spike
    condition: hourly_cost > 2 * avg_hourly_cost
    for: 1h
    severity: warning
    
  - name: quality_degradation
    condition: avg_quality_score < 3.5
    for: 30m
    severity: warning
    
  - name: gpu_memory_pressure
    condition: gpu_memory_utilization > 0.95
    for: 5m
    severity: warning
```

---

## 災難復原

### 多提供者故障轉移

```python
class MultiProviderClient:
    def __init__(self):
        self.providers = [
            OpenAIClient(),
            AnthropicClient(),
            GoogleClient()
        ]
        self.primary = 0
    
    async def generate(self, request: Request) -> Response:
        # 首先嘗試主要提供者
        try:
            return await self.providers[self.primary].generate(request)
        except (RateLimitError, ServiceError) as e:
            return await self.failover(request, e)
    
    async def failover(self, request: Request, original_error: Exception) -> Response:
        for i, provider in enumerate(self.providers):
            if i == self.primary:
                continue
            try:
                response = await provider.generate(request)
                # 記錄故障轉移以進行監控
                self.log_failover(self.primary, i, original_error)
                return response
            except Exception:
                continue
        
        raise AllProvidersUnavailable("All LLM providers failed")
```

### 優雅降級

```python
class GracefulDegradation:
    def __init__(self):
        self.cache = ResponseCache()
        self.fallback_responses = FallbackResponses()
    
    async def handle_outage(self, request: Request) -> Response:
        # 等級 1：嘗試快取
        cached = await self.cache.get_similar(request.query)
        if cached and cached.similarity > 0.9:
            return Response(
                content=cached.response,
                metadata={"source": "cache", "degraded": True}
            )
        
        # 等級 2：嘗試備用回應
        fallback = self.fallback_responses.get(request.intent)
        if fallback:
            return Response(
                content=fallback,
                metadata={"source": "fallback", "degraded": True}
            )
        
        # 等級 3：優雅錯誤
        return Response(
            content="I am currently experiencing issues. Please try again later or contact support.",
            metadata={"source": "error", "degraded": True}
        )
```

---

## 2026 年 5 月 AI 加速器景觀

硬體畫面在 2026 年 1 月到 5 月之間比 AI 建構過程中任何早期時刻都變化得更快。產能公告合計超過**一兆美元承諾的雲端支出**，供應鏈不再是單一供應商。本節是資深架構師在 2026 年 5 月進行產能規劃對話時應攜帶的快照。

### NVIDIA Blackwell Ultra（B300 / GB300 NVL72）

旗艦是 **B300**（「Blackwell Ultra」），自 2026 年 1 月起大量出貨（[NVIDIA 新聞室公告](https://nvidianews.nvidia.com/news/nvidia-blackwell-ultra-ai-factory-platform-paves-way-for-age-of-ai-reasoning)）。

| 規格 | B300 / GB300 NVL72 |
|------|---------------------|
| 每 GPU HBM3e | 288 GB |
| 峰值 FP4（稀疏） | ~15 PFLOPS |
| 外形規格 | NVL72 機架：72 個 Blackwell Ultra GPU + 36 個 Grace CPU |
| NVL72 中 aggregate NVLink 頻寬 | ~130 TB/s |
| 每 NVL72 總 HBM | ~20 TB |
| 2026 年預計出貨機架數 | ~60,000（Jensen Huang，GTC 2026 主題演講） |

策略定位是「AI 工廠」：NVL72 作為相干的、NVLink 領域推論/訓練細胞的最小單位出售，而不是作為個人卡。對於前沿模型訓練（Anthropic、OpenAI、Google 的外部工作）和最大的推理模型推論工作負載，這在 2026 年 5 月仍是預設值。

權衡保持不變：最高絕對效能、最高絕對價格、最深軟體鎖定。CUDA、NCCL 和 TensorRT-LLM 都假設 NVIDIA。如果您围绕它们進行架構，您就已經承諾了。

### AMD MI400 和 Helios Rack

[AMD 的 MI400](https://ir.amd.com/news-events/press-releases/detail/1252/amd-introduces-fifth-generation-instinct-mi400-series)（2025 年 Q4 宣布，2026 年 Q1 取樣，2026 年中 GA）是可信的第二來源。

| 規格 | MI400 |
|------|-------|
| 記憶體 | HBM4，每 GPU **432 GB** |
| 記憶體頻寬 | ~20 TB/s |
| 峰值 FP4 | ~13 PFLOPS |
| 機架解決方案 | **Helios**：EPYC Venice CPU、MI400 GPU、Pensando Vulcano 800Gb NIC |
| 軟體 | ROCm 7.x，PyTorch / vLLM / SGLang 一級支援 |

每 GPU 432 GB 是標題：比 B300 的 288 GB 高出 50% 以上。對於 MoE 服務（限制因素是保持專家權重駐留）和 KV 快取密集的長上下文工作負載，每 GPU 記憶體優勢是真實的。AMD 也關閉了大部分軟體差距；ROCm 7.x 不再是 2023 年的棄權因素。開源服務框架通常在兩者上進行測試。

陷阱：**生產部署成熟度**。NVIDIA 已經連續兩代向每個超大規模提供者大量出貨；AMD 仍在增加供應鏈量方面。超大規模提供者（Meta、Microsoft、Oracle Cloud，以及值得注意的是用於非 Trainium 工作負載的 AWS Trainium 機隊）正在運行混合機群。

### AWS Trainium3 和 Anthropic $100B+ 協議

2025 年 11 月，Anthropic 和 AWS 宣布擴展到**高達 5 吉瓦**的計算容量，透過 2026 年，錨定在 Trainium 晶片上，描述為**「$100B+」協議**（[AWS 新聞稿](https://press.aboutamazon.com/2025/11/anthropic-and-aws-announce-100-billion-strategic-partnership-investment-to-expand-trainium-compute-and-collaborate-on-ai-frontier-research)）。

關鍵數字：

| 規格 | Trainium3 |
|------|-----------|
| 製程節點 | 3nm |
| 配置 | **Trn3 UltraServer**，每系統 **144 晶片** |