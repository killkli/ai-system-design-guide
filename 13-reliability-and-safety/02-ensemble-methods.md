<<<<<<< Updated upstream
# LLM 可靠性集成方法

集成方法對於生產環境可靠性至關重要。本章涵蓋多模型協調模式，可提高準確性並減少幻覺。

## 目錄

- [為什麼需要集成](#為什麼需要集成)
- [評估集成](#評估集成)
- [生成集成](#生成集成)
- [多智慧體模式](#多智慧體模式)
- [集成與裁決](#集成與裁決)
- [成本與準確性取捨](#成本與準確性取捨)
- [面試題目](#面試題目)
=======
# LLM 可靠性的集成方法

集成方法對於生產可靠性至關重要。本章涵蓋提高準確性和減少幻覺的多模型協調模式。

## 目錄

- [為何集成重要](#為何集成重要)
- [評估集成](#評估集成)
- [生成集成](#生成集成)
- [多代理模式](#多代理模式)
- [集成與裁決](#集成與裁決)
- [成本-準確性權衡](#成本-準確性權衡)
- [面試問題](#面試問題)
>>>>>>> Stashed changes
- [參考文獻](#參考文獻)

---

<<<<<<< Updated upstream
## 為什麼需要集成

單一模型輸出在高風險應用中不可靠：
- 模型會產生幻覺事實
- 推理可能有缺陷
- 輸出隨溫度而變化
- 單一裁判評估有偏見
=======
## 為何集成重要

單模型輸出在高風險應用程式中不可靠：
- 模型會產生事實幻覺
- 推理可能有缺陷
- 輸出隨溫度變化
- 單一法官評估有偏見
>>>>>>> Stashed changes

集成通過冗餘和多樣性提高可靠性。

### 集成方法分類

| 類別 | 目的 | 方法 |
<<<<<<< Updated upstream
|----------|---------|---------|
| 評估 | 減少裁判偏見 | 裁判小組、成對比較 |
| 生成 | 提高輸出品質 | 自一致性、最佳選擇N |
| 驗證 | 減少幻覺 | 多智慧體辯論、事實核查 |
| 綜合 | 結合觀點 | 智慧體混合 |
=======
|------|------|------|
| 評估 | 減少法官偏見 | 法官小組、成對比較 |
| 生成 | 提高輸出品質 | 自我一致性、Best-of-N |
| 驗證 | 減少幻覺 | 多代理辯論、事實核查 |
| 綜合 | 結合觀點 | 混合代理 |
>>>>>>> Stashed changes

---

## 評估集成

<<<<<<< Updated upstream
### LLM 裁判小組 (PoLL)
=======
### LLM 法官小組（PoLL）
>>>>>>> Stashed changes

多個多樣化模型對同一輸出評分：

```python
class PanelOfJudges:
    """
    PoLL 模式的生產實現。
    關鍵洞見：裁判的多樣性比個別裁判品質更重要。
    """
    def __init__(self, judges: list, aggregation: str = "mean"):
        # 使用多樣化的模型家族，而不僅是不同的規模
        # 好：[Claude, GPT-4, Gemini, Llama-70B]
        # 差：[GPT-4, GPT-4-turbo, GPT-3.5] - 同一家族偏見
        self.judges = judges
        self.aggregation = aggregation
    
    async def evaluate(self, question: str, answer: str, rubric: str) -> dict:
        # 並行評估以降低延遲
        judgments = await asyncio.gather(*[
            judge.score(question, answer, rubric) 
            for judge in self.judges
        ])
        
        scores = [j["score"] for j in judgments]
        
        # 追蹤裁判間一致性以衡量信心
        agreement = 1 - (np.std(scores) / max(np.mean(scores), 0.01))
        
        if self.aggregation == "mean":
            final_score = np.mean(scores)
        elif self.aggregation == "median":  # 更能抵抗異常值
            final_score = np.median(scores)
        elif self.aggregation == "trimmed_mean":  # 去除最高和最低
            final_score = np.mean(sorted(scores)[1:-1])
        
        return {
            "score": final_score,
            "confidence": agreement,
            "individual_scores": scores,
            "needs_review": agreement < 0.7  # 標記需人工審查
        }
```

<<<<<<< Updated upstream
**使用時機：** 高風險評估、基準創建、當單一裁判偏見不可接受時。

### 帶位置去偏的成對比較

模型在 60-70% 的情況下偏好第一個選項。始終運行兩種順序：
=======
**何時使用：** 高風險評估、基準創建、單一法官偏見不可接受的情況。

### 帶位置去偏的成對比較

模型在 60-70% 的情況下偏愛第一個選項。始終運行兩個順序：
>>>>>>> Stashed changes

```python
async def pairwise_compare_debiased(model, response_a: str, response_b: str, criteria: str) -> dict:
    """
    關鍵：模型有顯著的位置偏見。
    始終運行兩種順序並聚合。
    """
    # 並行運行兩種順序
    result_ab, result_ba = await asyncio.gather(
        model.compare(first=response_a, second=response_b, criteria=criteria),
        model.compare(first=response_b, second=response_a, criteria=criteria)
    )
    
    # 如果 A 在兩種位置都獲勝 -> A 的強烈信號
    if result_ab["winner"] == "first" and result_ba["winner"] == "second":
        return {"winner": "A", "confidence": "high"}
    
    # 如果 B 在兩種位置都獲勝 -> B 的強烈信號
    elif result_ab["winner"] == "second" and result_ba["winner"] == "first":
        return {"winner": "B", "confidence": "high"}
    
    # 贏家取決於位置 -> 檢測到位置偏見
    else:
        return {
            "winner": "平局",
            "confidence": "低",
            "note": "檢測到位置偏見"
        }
```

---

## 生成集成

<<<<<<< Updated upstream
### 自一致性（多數投票）

生成多條推理路徑，對最終答案投票：
=======
### 自我一致性（多數投票）

生成多個推理路徑，對最終答案投票：
>>>>>>> Stashed changes

```python
class SelfConsistencyDecoder:
    """
    關鍵參數：
    - k（樣本數）：大多數任務 5-10，難數學 15-20
    - 溫度：推理任務 0.5-0.8
    
    溫度過低 = 多樣性不足
    溫度過高 = 噪音過多
    """
    
    def __init__(self, model, k: int = 7, temperature: float = 0.7):
        self.model = model
        self.k = k
        self.temperature = temperature
    
    async def generate_with_consistency(self, prompt: str) -> dict:
        # 並行生成 k 條推理路徑
        responses = await asyncio.gather(*[
            self.model.generate(prompt, temperature=self.temperature)
            for _ in range(self.k)
        ])
        
        # 提取最終答案（任務特定）
        answers = [self.extract_answer(r) for r in responses]
        
        # 多數投票
        answer_counts = Counter(answers)
        majority_answer, majority_count = answer_counts.most_common(1)[0]
        
        # 信心 = 贏家的投票比例
        confidence = majority_count / self.k
        
        # 獲取導致多數答案的最佳推理路徑
        best_reasoning = self.select_best_reasoning(
            responses, answers, majority_answer
        )
        
        return {
            "answer": majority_answer,
            "confidence": confidence,
            "num_paths": self.k,
            "reasoning": best_reasoning,
            "vote_distribution": dict(answer_counts)
        }
    
    def extract_answer(self, response: str) -> str:
        # 任務特定的答案提取
        # 數學：提取最終數字
        # 程式碼：提取函數
        # 基於您的任務實現
        pass
```

<<<<<<< Updated upstream
**最適用於：** 數學、邏輯、有可驗證答案的程式設計。準確率提升：5-15%。

### 帶獎勵模型的最佳選擇 N
=======
**最適合：** 數學、有可驗證答案的邏輯和編碼。準確性提升：5-15%。

### 帶獎勵模型的 Best-of-N
>>>>>>> Stashed changes

生成 N 個候選，用獎勵模型評分，返回最佳：

```python
class BestOfNSampler:
    """
    關鍵考量：
    1. N 選擇：互動式 N=4-8，批量 N=16-64
    2. 獎勵模型集成防止獎勵駭客攻擊
    3. 監控樣本多樣性 - 如果太相似，BoN 是浪費計算
    """
    
    def __init__(self, generator, reward_models: list, n: int = 8):
        self.generator = generator
        self.reward_models = reward_models  # 為稳健性使用集成
        self.n = n
    
    async def generate_best(self, prompt: str) -> dict:
        # 並行生成 N 個候選
        candidates = await asyncio.gather(*[
            self.generator.generate(prompt, temperature=0.8)
            for _ in range(self.n)
        ])
        
        # 用獎勵模型集成評分
        scored_candidates = []
        for candidate in candidates:
            rm_scores = await asyncio.gather(*[
                rm.score(prompt, candidate) for rm in self.reward_models
            ])
            
            # 保守聚合防止獎勵駭客攻擊
            # 使用第25百分位數而非平均值
            conservative_score = np.percentile(rm_scores, 25)
            
            scored_candidates.append({
                "response": candidate,
                "score": conservative_score,
                "rm_agreement": 1 - np.std(rm_scores) / np.mean(rm_scores)
            })
        
        # 按保守分數選擇最佳
        best = max(scored_candidates, key=lambda x: x["score"])
        
        # 計算多樣性指標
        diversity = self.compute_diversity(candidates)
        
        return {
            "response": best["response"],
            "score": best["score"],
            "n_sampled": self.n,
            "diversity_score": diversity,
            "low_diversity_warning": diversity < 0.3
        }
    
    def compute_diversity(self, candidates: list) -> float:
        # 嵌入候選並計算平均成對距離
        embeddings = [embed(c) for c in candidates]
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                similarities.append(cosine_similarity(embeddings[i], embeddings[j]))
        return 1 - np.mean(similarities)  # 越高 = 越多樣
```

<<<<<<< Updated upstream
**最適用於：** 開放式生成、創意任務。準確率提升：10-30%。

---

## 多智慧體模式

### 多智慧體辯論

多個模型迭代地互相批評：
=======
**最適合：** 開放式生成、創意任務。準確性提升：10-30%。

---

## 多代理模式

### 多代理辯論

多個模型迭代地相互批評：
>>>>>>> Stashed changes

```python
class MultiAgentDebate:
    """
    模式：多個模型辯論以減少幻覺。
    
    最有效時：
    1. 模型有不同的偏見（多樣化的模型家族）
    2. 2-3 輪是最優的（更多 = 邊際效益遞減）
    3. 明確的「魔鬼代言人」提示提高結果
    """
    
    def __init__(self, debaters: list, rounds: int = 2):
        self.debaters = debaters
        self.rounds = rounds
    
    async def debate(self, question: str) -> dict:
        # 第 0 輪：初始立場
        positions = await asyncio.gather(*[
            debater.generate(f"用推理回答這個問題：{question}")
            for debater in self.debaters
        ])
        
        debate_history = [{"round": 0, "positions": positions}]
        
        # 辯論輪次
        for round_num in range(1, self.rounds + 1):
            new_positions = []
            
            for i, debater in enumerate(self.debaters):
                other_positions = [p for j, p in enumerate(positions) if j != i]
                
                critique_prompt = f"""
問題：{question}

您之前的答案：{positions[i]}

其他觀點：
{self.format_positions(other_positions)}

考慮其他觀點。如果它們提出有效的點，更新您的答案。
如果您仍然不同意，用具體推理解釋為什麼。
提供您的最終答案。
"""
                new_position = await debater.generate(critique_prompt)
                new_positions.append(new_position)
            
            positions = new_positions
            debate_history.append({"round": round_num, "positions": positions})
        
        # 最終綜合
        final_answer = await self.synthesize(question, debate_history)
        
        return {
            "answer": final_answer,
            "rounds": self.rounds,
            "consensus_reached": self.check_consensus(positions),
            "debate_history": debate_history
        }
```

<<<<<<< Updated upstream
**最適用於：** 事實核查、減少複雜答案中的幻覺。

### 智慧體混合 (MoA)

分層架構，多個模型餵入聚合器：
=======
**最適合：** 事實驗證、減少複雜答案中的幻覺。

### 混合代理（MoA）

多個模型饋入聚合器的分層架構：
>>>>>>> Stashed changes

```
┌─────────────────────────────────────────────────────────────────┐
│                    智慧體混合 (MoA)                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  第 1 層（提議者）：                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ Claude  │  │  GPT-4  │  │ Gemini  │  │ Llama   │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│       │            │            │            │                   │
│       └────────────┴─────┬──────┴────────────┘                  │
│                          │                                       │
│  第 2 層（聚合器）：    ▼                                      │
│  ┌──────────────────────────────────────────────────┐           │
│  │  「 given these perspectives: [R1, R2, R3, R4]    │           │
│  │   綜合最佳答案...」                               │           │
│  └────────────────────────┬─────────────────────────┘           │
│                           │                                      │
│                           ▼                                      │
│                    [最終輸出]                                    │
└─────────────────────────────────────────────────────────────────┘
```

```python
class MixtureOfAgents:
    def __init__(self, proposers: list, aggregator):
        self.proposers = proposers
        self.aggregator = aggregator
    
    async def generate(self, prompt: str) -> str:
        # 第 1 層：獲取多樣化提議
        proposals = await asyncio.gather(*[
            proposer.generate(prompt) for proposer in self.proposers
        ])
        
        # 第 2 層：聚合
        aggregation_prompt = f"""
給定以下問題和多個專家回應，
綜合出最佳可能的答案。

問題：{prompt}

專家回應：
{self.format_proposals(proposals)}

綜合最佳答案，結合每個回應中最強的元素。
"""
        
        final_answer = await self.aggregator.generate(aggregation_prompt)
        return final_answer
```

<<<<<<< Updated upstream
**最適用於：** 複雜綜合、報告生成、多領域問題。
=======
**最適合：** 複雜綜合、報告生成、多領域問題。
>>>>>>> Stashed changes

---

## 集成與裁決

### 概念區分

<<<<<<< Updated upstream
| 方面 | 集成學習 | 模型裁決 |
|--------|------------------|-------------------|
| **目標** | 結合所有輸出 | 選擇單一最佳輸出 |
| **機制** | 聚合（投票、平均） | 選擇（評分、排名） |
| **關係** | 協作 | 競爭 |
| **最終輸出** | 所有模型的複合 | 單一贏家的輸出 |
| **使用時機** | 想要稳健性、減少方差 | 想要最佳品質 |
=======
| 面向 | 集成學習 | 模型裁決 |
|------|----------|----------|
| **目標** | 結合所有輸出 | 選擇單一最佳輸出 |
| **機制** | 聚合（投票、平均） | 選擇（評分、排名） |
| **關係** | 協作 | 競爭 |
| **最終輸出** | 所有模型的組合 | 單一獲勝者的輸出 |
| **何時使用** | 想要穩健性、減少變異 | 想要最佳品質 |
>>>>>>> Stashed changes

### 決策框架

```
是否存在單一「正確」答案格式？
├── 是（分類、數學）
│   └── 使用集成（投票/平均）
│
└── 否（創意寫作、開放式問答）
    └── 使用裁決（最佳選擇 N）
        └── 您有可靠的評分嗎？
            ├── 是 → 獎勵模型選擇
            └── 否 → LLM 作為裁判或人工
```

---

<<<<<<< Updated upstream
## 成本與準確性取捨

### 集成成本矩陣

| 方法 | 成本倍數 | 延遲 | 準確率提升 | 使用時機 |
|--------|-----------------|---------|---------------|-------------|
| 單一模型 | 1x | 1x | 基線 | 低風險、高容量 |
| 自一致性 k=3 | 3x | 1x（並行） | +5-8% | 推理、延遲敏感 |
| 自一致性 k=10 | 10x | 1x（並行） | +10-15% | 數學、準確性關鍵 |
| 最佳選擇 N (N=8) | 8x + 評分 | 1x（並行） | +15-25% | 創意生成 |
| 裁判小組 (3) | 3x 評估 | 1x（並行） | 偏見減少 | 評估任務 |
| 多智慧體辯論 | 6x | 3x | 幻覺 ↓ | 事實關鍵 |
| 智慧體混合 | 5-8x | 2x | 更好的綜合 | 複雜報告 |

### 何時不使用集成

| 情況 | 為什麼不 | 替代方案 |
|-----------|---------|-------------|
| 簡單的事實查詢 | 無多樣性收益 | 單一 RAG 調用 |
| 延遲要求 < 500ms | 集成增加延遲 | 單一模型 + 緩存 |
| 成本是主要約束 | 集成倍增成本 | 模型蒸餾 |
| 模型高度相關 | 無多樣性 = 無收益 | 首先獲取多樣化模型 |

---

## 面試題目

### Q：何時使用自一致性 vs 最佳選擇 N？

**強烈回答：**

「這兩者服務不同目的：

**自一致性**適用於可提取、可驗證答案的任務：
- 數學問題：提取最終數字，多數投票
- 分類：對標籤投票
- 短格式問答：對答案投票

關鍵是您可以比較答案是否相等。溫度 0.5-0.8 在保持一致性的同時提供多樣性。我對大多數任務使用 k=5-10。

**最佳選擇 N**適用於開放式生成，其中沒有單一正確答案：
- 創意寫作
- 解釋
- 可以有多種編寫方式的程式碼

這裡我需要獎勵模型或裁判來評分候選，因為我不能僅僅比較是否相等。通常 N=8-16。挑戰是避免獎勵駭客攻擊，所以我使用獎勵模型集成與保守聚合。

我不會將自一致性用於創意寫作（無可提取答案）或將最佳選擇 N 用於數學（只需使用投票，更簡單）。」

### Q：如何防止最佳選擇 N 中的獎勵駭客攻擊？

**強烈回答：**

「獎勵駭客攻擊是當模型利用獎勵模型的弱點而非真正提高品質時。

**我的緩解措施：**

1. **獎勵模型集成**：使用 3+ 個多樣化獎勵模型。一個樣本駭掉一個 RM 的可能性很低能駭掉所有。

2. **保守聚合**：不要使用平均分數，而是使用第 25 百分位數或最小值。這選擇在所有 RM 上都表現良好的樣本，而不僅僅是一個。

3. **多樣性監控**：追蹤樣本多樣性。如果多樣性下降過低，模型可能正在利用狹窄的獎勵駭客攻擊。我調整溫度或使用不同提示。

4. **人工校準**：定期驗證 RM 選擇的樣本確實符合人類偏好。

5. **多維度**：在多個標準（品質、安全性、相關性）上評分，並要求在所有標準上都表現良好，而不僅僅是複合分數。

關鍵洞見是任何單一獎勵信號都可以被玩弄。集成使玩弄變得更加困難。」
=======
## 成本-準確性權衡

### 集成成本矩陣

| 方法 | 成本倍數 | 延遲 | 準確性提升 | 何時使用 |
|------|----------|------|------------|----------|
| 單模型 | 1x | 1x | 基線 | 低風險、高容量 |
| 自我一致性 k=3 | 3x | 1x（並行） | +5-8% | 推理、延遲敏感 |
| 自我一致性 k=10 | 10x | 1x（並行） | +10-15% | 數學、準確性關鍵 |
| Best-of-N (N=8) | 8x + 評分 | 1x（並行） | +15-25% | 創意生成 |
| 法官小組（3） | 3x 評估 | 1x（並行） | 偏見減少 | 評估任務 |
| 多代理辯論 | 6x | 3x | 幻覺 ↓ | 事實關鍵 |
| 混合代理 | 5-8x | 2x | 更好的綜合 | 複雜報告 |

### 何時不使用集成

| 情況 | 為何不 | 替代方案 |
|------|--------|----------|
| 簡單事實查詢 | 無多樣性 benefit | 單一 RAG 呼叫 |
| 需要 <500ms 延遲 | 集成增加延遲 | 單模型 + 快取 |
| 成本是主要約束 | 集成倍增成本 | 模型蒸餾 |
| 模型高度相關 | 無多樣性 = 無 benefit | 先獲取多樣模型 |

---

## 面試問題

### Q: 何時使用自我一致性與 Best-of-N？

**理想回答：**

「這些服務不同目的：

**自我一致性**適用於有可提取、可驗證答案的任務：
- 數學問題：提取最終數字，多數投票
- 分類：對標籤投票
- 簡短形式問答：對答案投票

關鍵是你可以比較答案是否相等。溫度 0.5-0.8 在保持連貫性的同時提供多樣性。我對大多數任務使用 k=5-10。

**Best-of-N** 適用於沒有單一正確答案是開放式生成：
- 創意寫作
- 解釋
- 可以有多種寫法的程式碼

在這裡我需要獎勵模型或法官來評分候選，因為我不能只是比較是否相等。通常 N=8-16。挑戰是避免獎勵駭客，所以我使用帶保守聚合的獎勵模型集成。

我不會對創意寫作使用自我一致性（無可提取答案）或對數學使用 Best-of-N（只需投票，更簡單）。」

### Q: 如何防止 Best-of-N 中的獎勵駭客？

**理想回答：**

「獎勵駭客是模型利用獎勵模型的弱點而不是真正提高品質的時候。

**我的緩解措施：**

1. **獎勵模型集成**：使用 3+ 多樣獎勵模型。一個樣本駭掉一個 RM 不太可能同時駭掉所有。

2. **保守聚合**：不使用平均分數，而是使用第 25 百分位或最小值。這選擇在所有 RM 上都表現良好的樣本，而不只是一個。

3. **多樣性監控**：追蹤樣本多樣性。如果多樣性降得太低，模型可能在利用狹窄的獎勵駭客。我調整溫度或使用不同 prompt。

4. **人工校準**：定期驗證 RM 選擇的樣本實際上符合人類偏好。

5. **多維度**：在多個標準（品質、安全性、相關性）上評分，並要求所有標準都好，而不僅僅是複合分數。

關鍵見解是任何單一獎勵信號都可以被玩弄。集成使玩弄變得更加困難。」
>>>>>>> Stashed changes

---

## 參考文獻

- Verga et al. 「用多樣化模型小組替換裁判：評估 LLM 生成」（2024）
- Wang et al. 「自一致性改進鏈式思維推理」（2023）
- Du et al. 「通過多智慧體辯論提高語言模型的事實性和推理」（2023）

---

<<<<<<< Updated upstream
*下一篇：[可靠性模式擴展](02-reliability-patterns.md)*
=======
*下一篇：[可靠性模式擴展](02-reliability-patterns.md)*
>>>>>>> Stashed changes
