# 定價與成本

理解 LLM 定價結構對於構建經濟永續的 AI 系統至關重要。本章提供截至 2026 年 5 月的全面定價概覽、成本計算方法與優化策略。

> **最後更新：2026 年 5 月 29 日。** 模型定價變化頻繁——在做出財務承諾前，請務必查核供應商官方定價頁面。

## 目錄

- [前沿模型定價](#前沿模型定價)
- [快速/經濟模型定價](#快速經濟模型定價)
- [開源模型 API 定價](#開源模型-api-定價)
- [嵌入模型定價](#嵌入模型定價)
- [成本計算](#成本計算)
- [成本優化策略](#成本優化策略)
- [上下文快取經濟學](#上下文快取經濟學)
- [自託管與 GPU 雲端套利](#自託管與-gpu-雲端套利)
- [總持有成本](#總持有成本)
- [面試問題](#面試問題)
- [參考資料](#參考資料)

---

## 前沿模型定價

### 前沿層級（2026 年 5 月）

| 模型 | 輸入 / 每百萬 | 輸出 / 每百萬 | 上下文 | 特色 |
|------|-------------|-------------|--------|------|
| **Claude Opus 4.8** | $5.00 | $25.00 | 1M | 動態工作流；擴展思維 |
| **Claude Opus 4.7** | $5.00 | $25.00 | 1M | 較舊版本 |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | 1M | 性價比最佳 |
| **GPT-5.5** | $5.00 | $30.00 | 1M | SWE-bench 榜首 |
| **GPT-5.4** | $2.50 | $15.00 | 272K | 電腦使用 |
| **Gemini 3.1 Pro** | $2.00 | $12.00 | 1M | 多模態 |
| **Grok 4** | $3.00 | $15.00 | 256K | 原生工具使用 |
| **Grok 4.1 Fast** | $0.20 | $0.50 | 2M | 高容量、低成本 |

### 快取定價（前沿模型）

Claude 與 OpenAI 提供輸入快取，大幅降低重複上下文場景的成本：

| 模型 | 快取寫入（每百萬） | 快取命中（每百萬） |
|------|------------------|------------------|
| Claude Opus 4.8（5 分鐘） | $6.25 | $0.50 |
| Claude Opus 4.8（1 小時） | $10.00 | $0.50 |
| Claude Sonnet 4.6（5 分鐘） | $3.75 | $0.30 |
| Claude Sonnet 4.6（1 小時） | $6.00 | $0.30 |
| GPT-5.5（快取命中） | — | $1.25（75% 折扣） |

> [!IMPORTANT]
> **推論時間計算成本：** 對於帶有「擴展思維」或推理模式的模型（GPT-5.4 Pro、Claude Opus 4.6），即使不向使用者顯示，也會對**內部思維 token**收費。這可能使邏輯密集任務的總請求成本增加 2-10 倍。生產環境務必設定 `budget_tokens` 上限。

---

## 快速/經濟模型定價

| 模型 | 輸入 / 每百萬 | 輸出 / 每百萬 | 上下文 | 最佳用途 |
|------|-------------|-------------|--------|----------|
| **Gemini 3.1 Flash** | $0.10 | $3.00 | 1M | 高容量 RAG |
| **GPT-5.5-mini** | 待查 | 待查 | 272K | 高容量即時 |
| **Claude Haiku 4.5** | $0.10 | $0.50 | 200K | 低延遲 |
| **DeepSeek V4 Flash** | $0.14 | $0.28 | 1M | 最便宜前沿級 1M 上下文 |
| **o4-mini** | $0.10 | $0.40 | 128K | 快速推理 |
| **Gemini 2.5 Flash** | $0.075 | $0.30 | 1M | 高容量 |
| **Mistral Small 4** | $0.10 | $0.30 | 256K | 高效率 |

---

## 開源模型 API 定價

#### 開權重模型透過 API（2026 年 5 月）

| 模型 | 輸入 / 每百萬 | 輸出 / 每百萬 | 上下文 | 提供者範例 |
|-------|-------------|-------------|---------|-------------------|
| **DeepSeek-V3.2** | $0.28 | $0.42 | 128K | DeepSeek API。98% 快取命中折扣。有效費率可透過路由降低 10-30 倍。 |
| **DeepSeek V4 Pro** ⭐ 新 | $0.435 | $0.87 | 1M | DeepSeek API。75% 促銷折扣永久化：**自 2026 年 6 月 1 日起，新定價為 $1.74 / $3.48 的 25%**。快取命中輸入：$0.003625/M。~27% 計算資源 / 10% 記憶體相較 V3.2 在 1M token。 |
| **DeepSeek V4 Flash** ⭐ 新 | $0.14 | $0.28 | 1M | DeepSeek API。快取命中輸入：$0.0028/M（98% 折扣）。13B 活躍專家混合。目前最便宜的前沿級 1M 上下文 API。 |
| **Mistral Medium 3.5** ⭐ 新 | $1.50 | 待查 | 256K | Mistral API。統一 chat/reasoning/coding/vision；77.6% SWE-bench Verified。 |
| **Kimi K2.6** ⭐ 新 | 待查 | 待查 | — | Moonshot API。1T MoE / 32B 活躍；代理蜂群達 300 子代理。 |
| **Qwen 3.6-35B-A3B** ⭐ 新 | 待查 | 待查 | — | Apache 2.0 權重；可自託管或透過 API 提供者。 |
| **Llama 4 Scout** | $0.11 | $0.34 | 10M | Together AI、Groq、Fireworks。備註：有效上下文在 32K 後快速下降。 |
| **Llama 4 Maverick** | $0.27 | $0.85 | 1M | Together AI、Groq、Fireworks。需要 MoE 感知服務。 |
| **DeepSeek-V3** | $0.25 | $1.10 | 128K | DeepSeek API、Together AI |
| **DeepSeek-R1** | $0.55 | $2.19 | 128K | DeepSeek API |
| **Mistral Large 3** | $0.50 | $1.50 | 256K | Mistral API、AWS Bedrock |
| **Llama 3.3 70B** | 約 $0.10-0.20 | 約 $0.30-0.60 | 128K | Groq、Together AI |
| **Qwen2.5-Coder-32B** | 約 $0.50 | 約 $1.00 | 32K | Together AI |
| **Gemma 4（31B / 26B-A4B MoE / E4B / E2B）** ⭐ 新 | 自託管 | 自託管 | 256K | Apache 2.0。140+ 語言；原生活動/音訊；函式呼叫。 |

#### 嵌入模型（2026 年 5 月）

| 模型 | 每百萬 token 成本 | 維度 |
|-------|------------------|------|
| **Cohere Embed 4** ⭐ 新 | $0.10 | 256 / 512 / 1024 / 1536（Matryoshka） |
| **text-embedding-3-large** | $0.13 | 3072 |
| **text-embedding-3-small** | $0.02 | 1536 |
| **Voyage-3** | $0.06 | 1024 |
| **Cohere embed-v3** | $0.10 | 1024 |

---

## 成本計算

### 基本成本公式

```python
def calculate_request_cost(
    input_tokens: int,
    output_tokens: int,
    model: str
) -> float:
    pricing = {
        "gpt-5.4": {"input": 2.50, "output": 15.00},
        "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
        "claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
        "claude-opus-4.6": {"input": 5.00, "output": 25.00},
        "gemini-3.1-flash": {"input": 0.10, "output": 3.00},
    }
    
    rates = pricing[model]
    cost = (
        (input_tokens / 1_000_000) * rates["input"] +
        (output_tokens / 1_000_000) * rates["output"]
    )
    return cost
```

### 成本計算範例

**情境 1：RAG 聊天機器人**
```
每次請求：
- 系統提示：500 tokens
- 檢索上下文：2,000 tokens
- 使用者訊息：100 tokens
- 回應：300 tokens

輸入：2,600 tokens、輸出：300 tokens

GPT-5.4 成本：(2600 × $2.50 + 300 × $15) / 1M = $0.0110 每次請求

每日 10,000 次請求：
每日：$95
每月：$2,850
```

**情境 2：文件摘要**
```
每份文件：
- 文件：8,000 tokens
- 摘要：500 tokens

GPT-5.4 成本：(8000 × $2.50 + 500 × $15) / 1M = $0.0275

1,000 份文件：$27.50
10,000 份文件：$275
```

### 月度成本預估

```python
def project_monthly_cost(
    requests_per_day: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
    model: str
) -> dict:
    per_request = calculate_request_cost(
        avg_input_tokens, avg_output_tokens, model
    )
    
    daily = per_request * requests_per_day
    monthly = daily * 30
    yearly = monthly * 12
    
    return {
        "per_request": per_request,
        "daily": daily,
        "monthly": monthly,
        "yearly": yearly
    }

# 範例
costs = project_monthly_cost(
    requests_per_day=50000,
    avg_input_tokens=2000,
    avg_output_tokens=400,
    model="gpt-5.4"
)
# 輸出：約 $18,750/月
```

---

## 成本優化策略

### 策略 1：模型路由

將請求路由至適當的模型層級：

```python
class ModelRouter:
    def __init__(self):
        self.classifier = load_complexity_classifier()
    
    def route(self, query: str, context: str) -> str:
        complexity = self.classifier.predict(query)
        
        if complexity < 0.3:
            return "gpt-5.4-mini"  # 簡單查詢
        elif complexity < 0.7:
            return "gpt-5.4-mini"  # 中等，先嘗試便宜的
        else:
            return "gpt-5.4"  # 複雜查詢

    def route_with_fallback(self, query: str, context: str) -> str:
        # 先嘗試便宜模型
        response = self.try_model("gpt-5.4-mini", query, context)

        if self.is_quality_sufficient(response):
            return response

        # 失敗回退至昂貴模型
        return self.try_model("gpt-5.4", query, context)
```

**節省潛力：** 在品質影響最小的情況下節省 50-70%

### 策略 2：提示優化

在不改變品質的情況下減少 token 數量：

```python
# 之前：2,500 tokens
system_prompt = """
You are a helpful customer support assistant for Acme Corp. 
You have access to our product documentation and should answer 
questions accurately and helpfully. Always be polite and professional.
If you don't know something, say so rather than making things up.
Format your responses clearly with bullet points when listing items.
[... 更多冗長指令 ...]
"""

# 之後：800 tokens
system_prompt = """
You are Acme Corp's support assistant.
Rules:
- Answer from provided context only
- Admit uncertainty
- Use bullet points for lists
- Be concise
"""

# 節省：1,700 tokens × $2.50/1M = $0.00425 每次請求
# 每日 10K 請求：$42.50/日 = $1,275/月
```

### 策略 3：快取

為重複或相似查詢快取回應：

```python
class ResponseCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.exact_cache = TTLCache(maxsize=10000, ttl=ttl_seconds)
        self.semantic_cache = SemanticCache(threshold=0.95)
    
    def get_or_generate(self, query: str, context: str) -> tuple[str, bool]:
        # 檢查精確快取
        cache_key = self.make_key(query, context)
        if cache_key in self.exact_cache:
            return self.exact_cache[cache_key], True  # 快取命中
        
        # 檢查語義快取
        similar = self.semantic_cache.find_similar(query)
        if similar:
            return similar.response, True  # 語義命中
        
        # 生成新回應
        response = self.generate(query, context)
        self.exact_cache[cache_key] = response
        self.semantic_cache.add(query, response)
        
        return response, False  # 快取未命中

# 30% 快取命中率的成本：
# 基線：$3,000/月
# 啟用快取：$2,100/月
# 節省：$900/月
```

### 策略 4：批次處理

批次處理多個請求以提高效率：

```python
# 即時：全額付費
for query in queries:
    response = model.generate(query)

# 批次 API（OpenAI 提供五折）：
batch_responses = model.batch_generate(queries)
# 成本：即時定價的 50%
```

### 策略 5：輸出長度控制

適當限制回應長度：

```python
# 減少不必要的輸出
response = model.generate(
    prompt=prompt,
    max_tokens=300,  # 限制輸出
    stop=["\n\n"]    # 在自然斷點停止
)

# 成本影響：
# 之前：平均 500 輸出 tokens = $0.0075 每次請求（GPT-5.4）
# 之後：平均 250 輸出 tokens = $0.00375 每次請求
# 節省：輸出成本降低 50%
```

### 成本優化總結

| 策略 | 難度 | 潛在節省 |
|----------|--------|-----------------|
| 模型路由 | 中 | 50-70% |
| **上下文快取** | 低 | **60-90%（輸入）** |
| 提示優化 | 低 | 20-40% |
| 回應快取 | 中 | 20-40% |
| 批次處理 | 低 | 50%（OpenAI/Anthropic） |

---

## 上下文快取經濟學

**RAG 的「黃金法則」（2026 年仍然成立）。**

如果你有一個大於 10,000 tokens 的固定系統提示或共享知識庫（前綴），**上下文快取**是必備的。

**損益平衡分析（Claude Sonnet 4.6）：**
- **標準輸入**：$3.00 / 百萬 tokens
- **快取輸入**：$0.30 / 百萬 tokens（九折）
- **快取寫入費用**：$3.75 / 百萬 tokens（5 分鐘 TTL，1.25 倍）；$6.00（1 小時 TTL，2 倍）

`損益平衡 =（寫入費用）/（標準費率 - 快取費率）≈ 1.4 次請求（5 分鐘）或 2.2 次請求（1 小時）`

如果你的長前綴被**超過 2 個使用者**使用，快取絕對比每次直接發送更便宜。OpenAI 和 Anthropic 現在都提供批次 API 折扣（五折），可與快取疊加使用。

---

## 自託管與 GPU 雲端套利

**預留與無伺服器的權衡：**

| 模型大小 | 無伺服器（RunPod/Together） | 預留（Lambda/AWS） |
|------------|-----------------------------|-----------------------|
| **突發容量** | 無限（冷啟動） | 固定 |
| **利用率** | 僅按計算時間付費 | 24/7 固定成本 |
| **TCO 損益平衡**| **低於 40% 利用率時具成本效益** | **高於 40% 利用率時具成本效益** |

**原則層面細節：**「GPU 雲端套利」涉及根據**spot 執行個體可用性**在供應商之間移動生產工作負載。**Skypilot** 等工具透過全球追蹤「低需求」區域來自動化此操作，可節省高達 60% 的自託管成本。專家混合模型的興起（Llama 4 Scout 可容納於單張 H100、Maverick 約需 2 張 H100、DeepSeek V4 Flash 約需 4 張 H100）相較密集模型進一步降低了自託管的 GPU 需求。

### 何時自託管有意義

```
損益平衡分析：

API 成本（規模化）：
- 每月 100 萬次請求
- 平均 2,500 tokens
- GPT-5.4：約 $37,500/月
- Claude Sonnet 4.6：約 $30,000/月

自託管等效（Llama 4 Maverick，透過 MoE）：
- 2x H100 80GB：約 $6/小時 × 730 = $4,380/月
- 工程人力：$5,000/月（0.5 FTE）
- 營運間接成本：$2,000/月
- 總計：約 $11,380/月

與 GPT-5.4 相比節省：$26,120/月 = 70%
與 Claude Sonnet 4.6 相比節省：$18,620/月 = 62%
```

### 自託管成本組成

| 組成部分 | 月度成本 | 備註 |
|-----------|--------------|-------|
| GPU 計算 | $5K-20K | 取決於模型大小 |
| 儲存 | $200-500 | 模型權重、日誌 |
| 網路 | $100-500 | 輸出、負載平衡 |
| 工程人力 | $5K-15K | 部分 FTE 負責營運 |
| 監控 | $100-500 | 可觀測性工具 |

### GPU 需求（按模型大小）

| 模型大小 | GPU 配置 | 預估月度成本 |
|------------|-------------|---------------------|
| 7B（INT4） | 1x A10G | $500-800 |
| 7B（FP16） | 1x A100 40GB | $1,500-2,500 |
| 70B（INT4） | 2x A100 80GB | $5,000-8,000 |
| 70B（FP16） | 4x A100 80GB | $10,000-15,000 |
| 405B（INT4） | 8x H100 | $20,000-30,000 |

### 決策框架

```
選擇 API 的時機：
- 請求量 < 100K/月
- 無 ML 營運專業知識
- 需要最高品質（前沿模型）
- 需要快速疊代

選擇自託管的時機：
- 請求量 > 500K/月
- 有 ML 基礎設施團隊
- 有資料隱私要求
- 工作負載可預測、穩定
- 需要自訂微調
```

---

## 總持有成本

### TCO 組成部分

```python
def calculate_tco(scenario: dict) -> dict:
    # 直接成本
    api_or_compute = scenario["monthly_api_cost"]
    
    # 工程成本
    development = scenario["dev_hours"] * scenario["engineer_rate"]
    maintenance = scenario["maintenance_hours"] * scenario["engineer_rate"]
    
    # 基礎設施
    vector_db = scenario["vector_db_cost"]
    monitoring = scenario["monitoring_cost"]
    
    # 間接成本
    downtime_risk = scenario["expected_downtime_hours"] * scenario["revenue_per_hour"]
    
    monthly_tco = (
        api_or_compute +
        development / 12 +  # 按年攤銷
        maintenance +
        vector_db +
        monitoring +
        downtime_risk
    )
    
    return {
        "monthly_tco": monthly_tco,
        "yearly_tco": monthly_tco * 12,
        "breakdown": {
            "llm": api_or_compute,
            "engineering": development / 12 + maintenance,
            "infrastructure": vector_db + monitoring,
            "risk": downtime_risk
        }
    }
```

### TCO 比較範例

**情境：客服機器人（每月 50K 請求）**

| 成本組成部分 | API 型 | 自託管 |
|----------------|-----------|-------------|
| LLM 成本 | $5,000 | $3,000 |
| 向量資料庫 | $70 | $200 |
| 工程（每月） | $500 | $3,000 |
| 監控 | $100 | $200 |
| **月度總計** | **$5,670** | **$6,400** |

*此規模下，API 因工程間接成本較低而更便宜。*

**情境：大規模 RAG（每月 200 萬請求）**

| 成本組成部分 | API 型 | 自託管 |
|----------------|-----------|-------------|
| LLM 成本 | $50,000 | $15,000 |
| 向量資料庫 | $500 | $1,000 |
| 工程（每月） | $1,000 | $8,000 |
| 監控 | $200 | $500 |
| **月度總計** | **$51,700** | **$24,500** |

*此規模下，自託管明顯更便宜。*

---

## 面試問題

### Q：如何優化高容量 RAG 應用的成本？

**最佳答案：**

「我會分層處理成本優化：

**1. 架構優化：**
- 模型路由：對簡單查詢使用便宜模型
- 快取：30-40% 的查詢可能可快取
- 提示壓縮：最小化系統提示 tokens

**2. 模型選擇：**
```
簡單查詢（60%）：GPT-5.4-mini，$0.003/請求
複雜查詢（40%）：GPT-5.4，$0.011/請求
加權平均：$0.0062/請求（相較全部 GPT-5.4 節省 44%）
```

**3. 基礎設施：**
- 批次嵌入更新（五折）
- 正確調整向量資料庫大小
- 盡可能使用 spot 執行個體

**4. 監控：**
- 按查詢類型追蹤成本
- 異常警報
- 定期成本審查

### Q：何時建議自託管而非使用 API？

**最佳答案：**

「決策取決於多個因素：

**數量閾值：**
- 低於 100K/月：幾乎總是 API
- 100K-500K：個案評估
- 高於 500K：通常自託管勝出

**團隊能力：**
- 無 ML 營運：無論規模一律 API
- 強大基礎設施團隊：考慮較早自託管

**品質要求：**
- 需要絕對最佳：API（前沿模型）
- 足夠好即可：自託管開源模型

**其他因素：**
- 資料隱私：可能強制自託管
- 延遲控制：自託管提供更多控制
- 微調需求：自託管啟用更多自訂

**我的推薦流程：**
1. 先用 API 最快速疊代
2. 建立抽象層以便切換模型
3. 當支出超過 $10K/月 時評估自託管
4. 在承諾前先以影子部署試點」

---

## 參考資料

- OpenAI 定價：https://developers.openai.com/api/docs/pricing
- Anthropic 定價：https://platform.claude.com/docs/en/about-claude/pricing
- Google AI 定價：https://ai.google.dev/gemini-api/docs/pricing
- xAI 定價：https://docs.x.ai/developers/models
- Mistral 定價：https://docs.mistral.ai/getting-started/changelog
- Lambda Labs GPU 定價：https://lambdalabs.com/service/gpu-cloud
- RunPod 定價：https://www.runpod.io/pricing
- LLM 定價比較：https://pricepertoken.com/

---

*前一篇：[能力評估](02-capability-assessment.md) | 下一篇：[模型選擇指南](04-model-selection-guide.md)*
