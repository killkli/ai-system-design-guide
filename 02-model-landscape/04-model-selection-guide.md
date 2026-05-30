# 模型選擇指南

一個選擇正確 LLM 的實務框架，綜合考量能力、成本、延遲與營運因素。

## 目錄

- [選擇框架](#選擇框架)
- [能力比較](#能力比較)
- [使用場景映射](#使用場景映射)
- [成本分析](#成本分析)
- [營運考量](#營運考量)
- [多模型策略](#多模型策略)
- [面試問題](#面試問題)
- [參考資料](#參考資料)

---

## 選擇框架

### 決策樹（2025 年 12 月）

```
起點
    │
    ├── 需要自主代理/長期規劃？
    │   └── 是 ─────────────────────────────────────────┐
    │   └── 否 ──┐                                       │
    │            │                                       ▼
    │            │                              ┌─────────────────┐
    │            │                              │ Claude Opus 4.8 │
    │            │                              │ GPT-5.5 reasoning │
    │            │                              └─────────────────┘
    │            │
    ├── 需要最佳軟體工程/編碼？
    │   └── 是 ─────────────────────────────────────────┐
    │   └── 否 ──┐                                       │
    │            │                                       ▼
    │            │                              ┌─────────────────┐
    │            │                              │ GPT-5.5 88.7% / │
    │            │                              │ Opus 4.8 88.6%  │
    │            │                              │ Sonnet 4.6 低成本│
    │            │                              └─────────────────┘
    │            │
    ├── 需要處理大規模上下文（>1M）？
    │   └── 是 ─────────────────────────────────────────┐
    │   └── 否 ──┐                                       │
    │            │                                       ▼
    │            │                              ┌─────────────────┐
    │            │                              │ Gemini 3.0 Pro  │
    │            │                              │ (2.5M 上下文)   │
    │            │                              └─────────────────┘
    │            │
    ├── 成本敏感的高流量？
    │   └── 是 ─────────────────────────────────────────┐
    │   └── 否 ──┐                                       │
    │            │                                       ▼
    │            │                              ┌─────────────────┐
    │            │                              │ Gemini 3 Flash /│
    │            │                              │ o4-mini         │
    │            │                              └─────────────────┘
    │            │
    └── 預設：生產選擇
                 ▼
        ┌─────────────────┐
        │ Claude Sonnet 4.6│
        │ GPT-5.5-mini    │
        └─────────────────┘
```

### 關鍵選擇因素

| 因素 | 權重 | 考量 |
|--------|--------|----------------|
| **代理可靠性** | 高 | 工具呼叫準確度、多步驟規劃 |
| **上下文召回** | 高 | 1M+ 的海底撈針效能 |
| **速率限制天花板** | 高 | **（原則細節）**：供應商能否在 P99 吞吐量下處理你的負載而不至於 429 錯誤？ |
| **生態系統成熟度** | 高 | 生產追蹤記錄、SDK 支援、企業 SLA |
| **成本 / 輸出 Token** | 中 | 代理迴圈消耗 5-10 倍更多 tokens |

---

## 能力比較

### 前沿模型比較（2026 年 5 月）

| 模型 | 優勢 | 劣勢 | 上下文 | 最適用途 |
|-------|-----------|------|---------|----------|
| **Claude Opus 4.8** | 長時間代理編碼（SWE-bench 88.6%）、動態工作流與平行子代理、$10/$50 fast mode | 標準定價與 4.7 相同（$5/$25）；GPT-5.5 以些微差距領先單次 SWE-bench | 1M | 程式碼庫規模遷移、自主編碼迴圈 |
| **GPT-5.5** | SWE-bench Verified 榜首（88.7%）、Terminal-Bench 榜首（78.2%）、原生全方位多模態 | 高成本（$5/$30） | 1M | 多代理系統、單次編碼 |
| **Claude Opus 4.7** | 前代旗艦（SWE-bench 87.6%、SWE-Bench Pro 64.3%） | 被 4.8 以相同價格取代 | 1M | 無遷移壓力的現有 4.7 部署 |
| **Claude Sonnet 4.6** | 強大性價比、全面 1M 標準定價 | 目前尚無 Sonnet 4.8 發布 | 1M | 通用生產主力 |
| **Gemini 3.1 Pro** | GPQA Diamond 榜首（94.3%）、1M 多模態、Deep Think 模式 | Deep Think 延遲峰值 | 1M | 科學推理、多模態 |
| **DeepSeek-R1** | 開源推理、具競爭力的數學 | 僅推理用；非前沿通用 | 128K | 數學、複雜偵錯、開源權重推理 |

### 經濟模型比較

| 模型 | 成本（每百萬輸入/輸出） | 品質 | 上下文 | 最適用途 |
|------|----------------------------|---------|--------|----------|
| **Gemini 3 Flash** | $0.05 / $0.20 | 前沿級 | 1M | 高容量 RAG |
| **o4-mini** | $0.10 / $0.40 | 極佳 | 128K | 快速推理任務 |
| **Llama 4 8B** | 自託管（H100/L40） | 強大 | 128K | 設備端、私有 |

### 開源模型

| 模型 | 參數 | 品質 | 最適用途 |
|------|------------|--------|----------|
| **Llama 4 70B** | 70B | 前沿具競爭力 | 通用開源選擇 |
| **Nemotron 3 Ultra** | 500B MoE | 代理精通 | 可擴展開源代理 |
| **DeepSeek V3.2** | 671B MoE | 超高效能 | 前沿品質最低 TCO |

---

## 使用場景映射

### 按應用類型（2026 年 5 月）

| 使用場景 | 推薦模型 | 理由 |
|----------|-------------------|-----------|
| **自主開發** | Claude Opus 4.8 動態工作流、Claude Sonnet 4.6 | Claude Code 中平行子代理執行；SWE-Bench Pro 以 69.2% 領先 |
| **企業 RAG** | Gemini 3.1 Pro、Gemini 3.1 Flash、DeepSeek V4 Flash | 1M 上下文與積極快取折扣消除檢索複雜性 |
| **客服支援** | Gemini 3.1 Flash、GPT-5.5-mini、Claude Haiku 4.5 | 近零延遲搭配強大推理 |
| **推理/偵錯** | GPT-5.5 reasoning、Claude Opus 4.8 (thinking)、DeepSeek-R1 | 代碼與邏輯最佳隱藏 CoT |
| **影片/多模態** | Gemini 3.1 Pro、GPT-5.5、Claude Opus 4.8 | 原生交錯式多模態處理 |
| **私有代理** | Llama 4 Maverick、DeepSeek V4 Pro（開源權重） | 最強開源權重代理規劃 |

### 按約束條件

| 約束條件 | 方案 |
|------------|------|
| **最大延遲 < 100ms** | Gemini 3.1 Flash、GPT-5.5-mini、Claude Haiku 4.5、或自託管 Nano 模型 |
| **上下文 > 1M tokens** | Claude Opus 4.8 / 4.7 / 4.6、Gemini 3.1 Pro、GPT-5.5、Llama 4 Scout（10M） |
| **零資料洩漏** | Llama 4 70B、在內部 VPC 上的 DeepSeek V4 Pro |
| **複雜工具使用** | Claude Opus 4.8 或 GPT-5.5（最佳規劃準確度） |

---

## 成本分析

### 成本建模（2026 年 5 月）

| 模型 | 輸入 / 每百萬 | 輸出 / 每百萬 | 備註 |
|------|-------------|-------------|-------|
| **Claude Opus 4.8** | $5.00 | $25.00 | 前沿編碼與代理；可選 fast mode $10 / $50 |
| **Claude Opus 4.7** | $5.00 | $25.00 | 相同標準定價；fast mode 為較貴的 $30 / $150 |
| **GPT-5.5** | $5.00 | $30.00 | 單次 SWE-bench 榜首 |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | 平衡選擇；目前尚無 Sonnet 4.8 發布 |
| **Gemini 3.1 Pro** | $2.00 | $12.00 | 最佳價值前沿；多模態 |
| **DeepSeek V4 Pro** | $0.435 | $0.87 | 75% 折扣於 5 月 22 日永久化 |
| **Gemini 3.1 Flash** | $0.10 | $3.00 | RAG 規模化；快取折扣 |
| **DeepSeek V4 Flash** | $0.14 | $0.28 | 最便宜前沿級 1M 上下文 |

### 成本比較範例

假設每月 100 萬次查詢，每次 1K 輸入 tokens + 500 輸出 tokens：

| 流量 | GPT-5.5 | Claude Sonnet | Gemini 3 Pro | Gemini 3 Flash |
|--------|---------|---------------|--------------|----------------|
| 10K 查詢/月 | $150 | $105 | $37.50 | $1.50 |
| 100 萬查詢/月 | $15,000 | $10,500 | $3,750 | $150 |

*洞察：DeepSeek V4 Flash（$0.14 / $0.28）與 Gemini 3.1 Flash（$0.10 / $3.00）實際上已將 RAG 商品化，使大規模長上下文處理比傳統向量搜尋基礎設施更便宜。*

---

## 營運考量

### 速率限制與配額

| 供應商 | 層級 | RPM | TPM |
|----------|------|-----|-----|
| OpenAI（第一層） | 基本 | 500 | 30K |
| OpenAI（第五層） | 企業 | 10K | 10M |
| Anthropic（第一層） | 基本 | 50 | 40K |
| Anthropic（第四層） | 企業 | 4K | 400K |

### 可靠性模式

```python
class ReliableModelClient:
    def __init__(self):
        self.providers = {
            "primary": OpenAIClient(),
            "fallback1": AnthropicClient(),
            "fallback2": GoogleClient()
        }
    
    async def generate(self, prompt: str) -> str:
        for name, client in self.providers.items():
            try:
                return await client.generate(prompt)
            except RateLimitError:
                continue
            except ServiceError:
                continue
        
        raise AllProvidersUnavailable()
```

### 抽象層

```python
class LLMClient:
    """多供應商的統一介面。"""
    
    def __init__(self, config: dict):
        self.default_model = config["default_model"]
        self.clients = self._init_clients(config)
    
    async def generate(
        self,
        messages: list[dict],
        model: str = None,
        **kwargs
    ) -> str:
        model = model or self.default_model
        client = self._get_client(model)
        
        # 標準化請求格式
        normalized = self._normalize_request(messages, kwargs)
        
        # 呼叫供應商
        response = await client.generate(**normalized)
        
        # 標準化回應
        return self._normalize_response(response)
    
    def _normalize_request(self, messages: list[dict], kwargs: dict) -> dict:
        # 處理供應商之間的差異
        # OpenAI 使用 'messages'，Anthropic 使用不同格式
        pass
```

---

## 多模型策略

### 模型路由

```python
class ModelRouter:
    def __init__(self):
        self.classifier = QueryClassifier()
        self.models = {
            "simple": "gpt-4o-mini",
            "complex": "claude-3.5-sonnet",
            "code": "claude-3.5-sonnet",
            "long_context": "gemini-1.5-pro",
            "reasoning": "o1-mini"
        }
    
    async def route(self, query: str, context_length: int) -> str:
        # 分類查詢複雜度
        query_type = await self.classifier.classify(query)
        
        # 覆寫長上下文
        if context_length > 100_000:
            return self.models["long_context"]
        
        return self.models[query_type]
```

### 串聯模式（2025 年改良）

**邏輯：** 不要用 70B 模型處理 1B 模型就能完成的任務。使用「路由器」對信心評分。

```python
class ModelCascade:
    """「效率優先」模式。"""
    
    async def generate_optimized(self, query: str):
        # 1. 草稿檢查（SLM / 分類器）
        if is_simple_intent(query):
            return await gpt4o_mini.generate(query)
            
        # 2. 主要生成（高效模型）
        response = await claude_sonnet.generate(query)
        
        # 3. 驗證 / 升級
        if needs_verification(response):
            return await o3.generate(f"驗證這個：{response}")
            
        return response
```

**原則級提示：** 實作「語義回退」，在錯誤時不僅僅在同一模型上重試，而是立即跳轉至更大模型或不同供應商（OpenAI → Anthropic）以避免相關性失敗。

---

## 面試問題

### Q：如何為生產應用選擇 GPT-4o、Claude 與 Gemini？

**最佳答案：**

「我的選擇取決於具體需求：

**對於大多數生產工作負載**，我預設使用 Claude 3.5 Sonnet 或 GPT-4o。兩者都是出色的通用模型。Sonnet 在編碼上略有優勢，GPT-4o 有更好的生態系統整合。

**對於長上下文應用**，Gemini 1.5 Pro 以 1-2 百萬 token 上下文是明顯贏家。如果需要處理整個程式碼庫或非常長的文件，Gemini 是我的選擇。

**對於成本敏感的高流量**，GPT-4o-mini 或 Claude Haiku。這些便宜 10-20 倍，能良好處理簡單任務。

**我的實務方法：**
1. 用 Sonnet 或 GPT-4o 原型化以驗證使用場景
2. 在我的特定任務上評估，而非僅看基準
3. 建立抽象層以便輕鬆切換
4. 透過將較簡單請求路由至便宜模型來優化成本

我從不僅依賴基準測試分數。在 MMLU 上排名較低的模型可能在我的領域表現優異。」

### Q：何時自託管與使用 API 供應商？

**最佳答案：**

「這是控制與營運負擔之間的權衡。

**使用 API 的時機：**
- 流量低於 100 萬查詢/月（成本交叉點）
- 需要立即使用最新模型
- 團隊缺乏 GPU 基礎設施專業知識
- 工作負載多變，難以容量規劃
- 上市時間是關鍵

**自託管的時機：**
- 資料不能離開基礎設施（合規）
- 流量超過 1000 萬查詢/月（成本節省）
- 需要 P99 延遲低於 100ms
- 需要自訂模型權重或微調
- 需要對模型行為的完全控制

**混合方式通常效果最佳：**
- 自託管處理高流量可預測的工作負載
- API 處理峰值和專業模型
- API 作為自託管故障時的回退

自託管的隱藏成本：GPU 採購、工程人力、模型更新、監控。將 1-2 名專職工程師負責基礎設施計入成本。」

---

## 參考資料

- OpenAI API：https://platform.openai.com/
- Anthropic API：https://docs.anthropic.com/
- Google AI：https://ai.google.dev/
- LMSys 排行榜：https://chat.lmsys.org/

---

*前一篇：[定價與成本](03-pricing-and-costs.md) | 下一篇：[微調指南](../03-training-and-adaptation/01-pretraining-basics.md)*
