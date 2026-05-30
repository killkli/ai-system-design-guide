# LLM 應用程式的 CI/CD

部署 LLM 應用程式需要調整傳統 CI/CD 實踐以適應 AI 特定關注，如模型評估、提示詞測試和品質閘道。

## 目錄

- [LLM CI/CD 挑戰](#llm-cicd-challenges)
- [管線架構](#pipeline-architecture)
- [測試階段](#testing-stages)
- [品質閘道](#quality-gates)
- [部署策略](#deployment-strategies)
- [回滾程序](#rollback-procedures)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## LLM CI/CD 挑戰

### 什麼使 LLM 部署與眾不同

| 傳統 CI/CD | LLM CI/CD |
|-------------------|-----------|
| 二元測試（通過/失敗） | 概率評估 |
| 快速測試 | 慢、昂貴的評估 |
| 確定性輸出 | 非確定性輸出 |
| 僅程式碼變更 | 提示 + 模型 + 資料變更 |
| 版本控制明顯 | 提示詞版本控制複雜 |

### 變更類型

| 變更類型 | 風險 | 需要的測試 |
|-------------|------|------------------|
| 提示文字 | 中 | 迴歸 + 品質評估 |
| 系統提示 | 高 | 完整評估套件 |
| 模型版本 | 高 | 全面基準測試 |
| RAG 索引 | 中 | 檢索 + 品質評估 |
| 參數（溫度等） | 低-中 | 品質抽樣 |

---

## 管線架構

### 完整管線

```
┌─────────────────────────────────────────────────────────────────┐
│                       LLM CI/CD PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                               │
│  │   Commit     │                                               │
│  │   Trigger    │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │   Validate   │ ─── Prompt syntax, config validation         │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ Unit Tests   │ ─── Fast, deterministic tests                │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │  Golden Set  │ ─── Known input/output pairs                 │
│  │    Tests     │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │   LLM Eval   │ ─── Quality scoring, regression detection    │
│  │   (Sampled)  │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ Quality Gate │ ─── Pass/fail based on thresholds            │
│  └──────┬───────┘                                               │
│         │                                                        │
│    ┌────┴────┐                                                  │
│    ▼         ▼                                                  │
│ ┌──────┐ ┌───────┐                                             │
│ │Canary│ │Blocked│                                             │
│ │Deploy│ │       │                                             │
│ └──┬───┘ └───────┘                                             │
│    │                                                            │
│    ▼                                                            │
│ ┌──────────────┐                                               │
│ │  Production  │                                               │
│ │  Monitoring  │                                               │
│ └──────────────┘                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 測試階段

### 階段 1：靜態驗證

```python
class PromptValidator:
    def validate(self, prompt_config: dict) -> ValidationResult:
        errors = []
        
        # 必填欄位
        if not prompt_config.get("system_prompt"):
            errors.append("Missing system_prompt")
        
        # 範本語法
        try:
            Template(prompt_config["user_template"]).substitute({})
        except KeyError:
            pass  # 對於帶有變數的範本是預期的
        except ValueError as e:
            errors.append(f"Invalid template syntax: {e}")
        
        # Token 限制
        system_tokens = count_tokens(prompt_config.get("system_prompt", ""))
        if system_tokens > 4000:
            errors.append(f"System prompt too long: {system_tokens} tokens")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )
```

### 階段 2：單元測試

```python
class PromptUnitTests:
    def test_template_rendering(self):
        prompt = PromptTemplate(SYSTEM_PROMPT, USER_TEMPLATE)
        
        rendered = prompt.render(
            query="test query",
            context="test context"
        )
        
        assert "test query" in rendered
        assert "test context" in rendered
        assert len(rendered) < 10000  # Token 限制
    
    def test_output_parsing(self):
        parser = OutputParser()
        
        valid_output = '{"answer": "test", "confidence": 0.9}'
        result = parser.parse(valid_output)
        assert result["answer"] == "test"
        
        invalid_output = "not json"
        with pytest.raises(ParseError):
            parser.parse(invalid_output)
```

### 階段 3：黃金集測試

```python
class GoldenSetRunner:
    def __init__(self, golden_set: list[dict]):
        self.golden_set = golden_set
    
    async def run(self, llm_client) -> TestResults:
        results = []
        
        for example in self.golden_set:
            response = await llm_client.generate(example["input"])
            
            # 確定性輸出的精確匹配
            if example.get("exact_match"):
                passed = response == example["expected"]
            # 靈活輸出的包含檢查
            elif example.get("must_contain"):
                passed = all(
                    phrase in response 
                    for phrase in example["must_contain"]
                )
            # 用於品質的 LLM judge
            else:
                passed = await self.judge_quality(
                    response, example["expected"]
                )
            
            results.append(TestResult(
                input=example["input"],
                expected=example["expected"],
                actual=response,
                passed=passed
            ))
        
        return TestResults(
            total=len(results),
            passed=sum(1 for r in results if r.passed),
            failed=[r for r in results if not r.passed]
        )
```

### 階段 4：LLM 評估

```python
class LLMEvaluationStage:
    def __init__(self, eval_set: list[dict], sample_rate: float = 0.1):
        self.eval_set = eval_set
        self.sample_rate = sample_rate
        self.evaluator = LLMEvaluator()
    
    async def run(self, llm_client) -> EvalResults:
        # 抽樣以提高成本效率
        sample = random.sample(
            self.eval_set,
            int(len(self.eval_set) * self.sample_rate)
        )
        
        scores = []
        for example in sample:
            response = await llm_client.generate(example["input"])
            
            score = await self.evaluator.evaluate(
                query=example["input"],
                response=response,
                reference=example.get("reference"),
                criteria=["relevance", "accuracy", "helpfulness"]
            )
            scores.append(score)
        
        return EvalResults(
            sample_size=len(sample),
            avg_relevance=np.mean([s["relevance"] for s in scores]),
            avg_accuracy=np.mean([s["accuracy"] for s in scores]),
            avg_helpfulness=np.mean([s["helpfulness"] for s in scores])
        )
```

---

## 品質閘道

### 閘道配置

```python
class QualityGate:
    def __init__(self, thresholds: dict):
        self.thresholds = thresholds
    
    def evaluate(self, results: dict) -> GateResult:
        failures = []
        
        # 黃金集通過率
        if results["golden_pass_rate"] < self.thresholds["golden_pass_rate"]:
            failures.append({
                "metric": "golden_pass_rate",
                "actual": results["golden_pass_rate"],
                "threshold": self.thresholds["golden_pass_rate"]
            })
        
        # 品質分數
        for metric in ["relevance", "accuracy", "helpfulness"]:
            if results.get(f"avg_{metric}", 0) < self.thresholds.get(metric, 0):
                failures.append({
                    "metric": metric,
                    "actual": results.get(f"avg_{metric}"),
                    "threshold": self.thresholds[metric]
                })
        
        # 迴歸偵測
        if results.get("regression_detected"):
            failures.append({
                "metric": "regression",
                "details": results["regression_details"]
            })
        
        return GateResult(
            passed=len(failures) == 0,
            failures=failures
        )

# 範例閾值
QUALITY_THRESHOLDS = {
    "golden_pass_rate": 0.95,  # 95% 的黃金測試必須通過
    "relevance": 4.0,          # 平均分數 >= 4.0/5.0
    "accuracy": 4.0,
    "helpfulness": 3.5
}
```

---

## 部署策略

### 金絲雀部署

```python
class CanaryDeployer:
    def __init__(
        self,
        initial_percentage: int = 5,
        increment: int = 10,
        bake_time_minutes: int = 30
    ):
        self.initial_percentage = initial_percentage
        self.increment = increment
        self.bake_time = bake_time_minutes
    
    async def deploy(self, new_version: str):
        # 啟動金絲雀
        await self.router.set_canary(new_version, self.initial_percentage)
        
        percentage = self.initial_percentage
        while percentage < 100:
            # 等待烘烤時間
            await asyncio.sleep(self.bake_time * 60)
            
            # 檢查金絲雀健康狀況
            metrics = await self.get_canary_metrics(new_version)
            
            if not self.is_healthy(metrics):
                await self.rollback(new_version)
                raise CanaryFailedError(metrics)
            
            # 增加流量
            percentage = min(100, percentage + self.increment)
            await self.router.set_canary(new_version, percentage)
        
        # 完整推出
        await self.router.promote_canary(new_version)
```

### 影子部署

```python
class ShadowDeployer:
    async def shadow_test(
        self,
        new_version: str,
        duration_hours: int = 24
    ):
        # 在影子模式下運行新版本
        await self.enable_shadow(new_version)
        
        # 收集比較資料
        start = datetime.now()
        while datetime.now() - start < timedelta(hours=duration_hours):
            await asyncio.sleep(60)
            
            comparison = await self.compare_outputs()
            if comparison["divergence_rate"] > 0.1:
                await self.alert("High divergence in shadow test", comparison)
        
        # 分析結果
        return await self.generate_comparison_report(new_version)
```

---

## 回滾程序

### 自動回滾

```python
class AutoRollback:
    def __init__(self, rollback_thresholds: dict):
        self.thresholds = rollback_thresholds
    
    async def monitor_and_rollback(self, version: str):
        while True:
            metrics = await self.get_live_metrics(version)
            
            # 檢查錯誤率
            if metrics["error_rate"] > self.thresholds["error_rate"]:
                await self.trigger_rollback(version, "error_rate_exceeded")
                return
            
            # 檢查延遲
            if metrics["p99_latency"] > self.thresholds["p99_latency"]:
                await self.trigger_rollback(version, "latency_exceeded")
                return
            
            # 檢查品質（抽樣）
            if metrics.get("quality_score", 5) < self.thresholds["quality_score"]:
                await self.trigger_rollback(version, "quality_degradation")
                return
            
            await asyncio.sleep(60)
    
    async def trigger_rollback(self, version: str, reason: str):
        previous = await self.get_previous_version()
        await self.router.rollback_to(previous)
        await self.alert(f"Auto-rollback from {version}: {reason}")
```

---

## 面試題目

### Q：在生產前如何測試提示詞變更？

**強烈回答：**

「我使用多階段測試管線：

**階段 1：靜態驗證。** 語法檢查、Token 限制、範本錯誤。快速且便宜。

**階段 2：單元測試。** 範本渲染、輸出解析、確定性行為。仍然快速。

**階段 3：黃金集測試。** 已知輸入/輸出配對必須通過。捕捉明顯迴歸。

**階段 4：LLM 評估。** 使用 LLM-as-judge 的抽樣評估。測量品質維度（相關性、準確性）。更昂貴但捕捉細微問題。

**品質閘道：** 所有階段必須通過閾值。黃金集 > 95% 通過率，品質分數 > 4.0/5.0。

**部署：** 金絲雀 5% 流量，烘烤 30 分鐘，監控指標，逐漸增加。

關鍵洞察是 LLM 輸出是非確定性的，因此測試必須是統計的。我無法保證 100% 正確性，但我可以確保品質保持在可接受的範圍內。」

### Q：什麼觸發條件應該導致自動回滾？

**強烈回答：**

「我配置多個回滾觸發條件：

**錯誤率：** 如果錯誤超過 5% 持續 5 分鐘，回滾。這捕捉整體失敗。

**延遲：** 如果 P99 延遲超過 SLA（例如 10 秒）持續 10 分鐘，回滾。這捕捉效能迴歸。

**品質分數：** 如果抽樣品質分數低於 3.5/5.0，回滾。這捕捉細微品質下降。

**使用者信號：** 如果負面回饋率飆升 2 倍基線，調查並可能回滾。

**實施：**
- Prometheus 警報觸發回滾腳本
- 自動通知團隊
- 回滾到最後已知良好版本
- 在調查完成前阻止進一步部署

關鍵是快速偵測和行動。生產中的錯誤提示 10 分鐘是可以接受的。10 小時是不可接受的。」

---

## 參考文獻

- ML Ops：https://ml-ops.org/
- LangSmith：https://docs.smith.langchain.com/

---

*上一篇：[LLM 基礎設施](01-llm-infrastructure.md)*