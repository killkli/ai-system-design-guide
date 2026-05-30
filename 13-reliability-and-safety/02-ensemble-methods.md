# LLM 可靠性集成方法

集成方法是生產可靠性的關鍵。本章涵蓋提高準確性並減少幻覺的多模型協調模式。

## 目錄

- [為何集成很重要](#為何集成很重要)
- [評估集成](#評估集成)
- [生成集成](#生成集成)
- [多代理模式](#多代理模式)
- [集成與仲裁](#集成與仲裁)
- [成本與準確性權衡](#成本與準確性權衡)
- [面試問題](#面試問題)
- [參考資料](#參考資料)

---

## 為何集成很重要

單一模型輸出在關鍵應用中不可靠：
- 模型會產生事實幻覺
- 推理可能有缺陷
- 輸出隨溫度變化
- 單一裁判評估有偏差

集成透過冗餘和多樣性提高可靠性。

### 集成方法分類

| 類別 | 目的 | 方法 |
|------|------|------|
| 評估 | 減少裁判偏差 | 裁判小組、成對比較 |
| 生成 | 提高輸出品質 | 自我一致性、Best-of-N |
| 驗證 | 減少幻覺 | 多代理辯論、事實檢查 |
| 合成 | 結合觀點 | 代理混合 |

---

## 評估集成

### LLM 裁判小組（PoLL）

多個多樣化模型對相同輸出評分：

```python
class PanelOfJudges:
    """
    Production implementation of PoLL pattern.
    Key insight: Diversity of judges matters more than individual judge quality.
    """
    def __init__(self, judges: list, aggregation: str = "mean"):
        # Use diverse model families, not just different sizes
        # Good: [Claude, GPT-4, Gemini, Llama-70B]
        # Bad: [GPT-4, GPT-4-turbo, GPT-3.5] - same family bias
        self.judges = judges
        self.aggregation = aggregation
    
    async def evaluate(self, question: str, answer: str, rubric: str) -> dict:
        # Parallel evaluation for latency
        judgments = await asyncio.gather(*[
            judge.score(question, answer, rubric) 
            for judge in self.judges
        ])
        
        scores = [j["score"] for j in judgments]
        
        # Track inter-judge agreement for confidence
        agreement = 1 - (np.std(scores) / max(np.mean(scores), 0.01))
        
        if self.aggregation == "mean":
            final_score = np.mean(scores)
        elif self.aggregation == "median":  # More robust to outliers
            final_score = np.median(scores)
        elif self.aggregation == "trimmed_mean":  # Drop highest and lowest
            final_score = np.mean(sorted(scores)[1:-1])
        
        return {
            "score": final_score,
            "confidence": agreement,
            "individual_scores": scores,
            "needs_review": agreement < 0.7  # Flag for human review
        }
```

**使用時機：** 關鍵評估、基準建立、單一裁判偏差不可接受的情況。

### 带位置去偏的成對比較

模型有 60-70% 的機率偏愛第一個選項。務必執行兩種順序：

```python
async def pairwise_compare_debiased(model, response_a: str, response_b: str, criteria: str) -> dict:
    """
    Critical: Models have significant positional bias.
    Always run both orderings and aggregate.
    """
    # Run both orderings in parallel
    result_ab, result_ba = await asyncio.gather(
        model.compare(first=response_a, second=response_b, criteria=criteria),
        model.compare(first=response_b, second=response_a, criteria=criteria)
    )
    
    # If A wins in both positions -> Strong signal for A
    if result_ab["winner"] == "first" and result_ba["winner"] == "second":
        return {"winner": "A", "confidence": "high"}
    
    # If B wins in both positions -> Strong signal for B
    elif result_ab["winner"] == "second" and result_ba["winner"] == "first":
        return {"winner": "B", "confidence": "high"}
    
    # Winner depends on position -> Positional bias detected
    else:
        return {
            "winner": "tie",
            "confidence": "low",
            "note": "Positional bias detected"
        }
```

---

## 生成集成

### 自我一致性（多數投票）

產生多條推理路徑，對最終答案投票：

```python
class SelfConsistencyDecoder:
    """
    Key parameters:
    - k (sample count): 5-10 for most tasks, 15-20 for hard math
    - temperature: 0.5-0.8 for reasoning tasks
    
    Too low temperature = not enough diversity
    Too high temperature = too much noise
    """
    
    def __init__(self, model, k: int = 7, temperature: float = 0.7):
        self.model = model
        self.k = k
        self.temperature = temperature
    
    async def generate_with_consistency(self, prompt: str) -> dict:
        # Generate k reasoning paths in parallel
        responses = await asyncio.gather(*[
            self.model.generate(prompt, temperature=self.temperature)
            for _ in range(self.k)
        ])
        
        # Extract final answers (task-specific)
        answers = [self.extract_answer(r) for r in responses]
        
        # Majority voting
        answer_counts = Counter(answers)
        majority_answer, majority_count = answer_counts.most_common(1)[0]
        
        # Confidence = proportion of votes for winner
        confidence = majority_count / self.k
        
        # Get best reasoning path that led to majority answer
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
        # Task-specific answer extraction
        # For math: extract the final number
        # For code: extract the function
        # Implement based on your task
        pass
```

**最適合：** 具有可驗證答案的數學、邏輯、編碼。準確度提升：5-15%。

### 帶獎勵模型的 Best-of-N

產生 N 個候選，用獎勵模型評分，返回最佳：

```python
class BestOfNSampler:
    """
    Key considerations:
    1. N selection: N=4-8 for interactive, N=16-64 for batch
    2. Reward model ensemble prevents reward hacking
    3. Monitor sample diversity - if too similar, BoN is wasted compute
    """
    
    def __init__(self, generator, reward_models: list, n: int = 8):
        self.generator = generator
        self.reward_models = reward_models  # Ensemble for robustness
        self.n = n
    
    async def generate_best(self, prompt: str) -> dict:
        # Generate N candidates in parallel
        candidates = await asyncio.gather(*[
            self.generator.generate(prompt, temperature=0.8)
            for _ in range(self.n)
        ])
        
        # Score with reward model ensemble
        scored_candidates = []
        for candidate in candidates:
            rm_scores = await asyncio.gather(*[
                rm.score(prompt, candidate) for rm in self.reward_models
            ])
            
            # Conservative aggregation prevents reward hacking
            # Use 25th percentile instead of mean
            conservative_score = np.percentile(rm_scores, 25)
            
            scored_candidates.append({
                "response": candidate,
                "score": conservative_score,
                "rm_agreement": 1 - np.std(rm_scores) / np.mean(rm_scores)
            })
        
        # Select best by conservative score
        best = max(scored_candidates, key=lambda x: x["score"])
        
        # Compute diversity metric
        diversity = self.compute_diversity(candidates)
        
        return {
            "response": best["response"],
            "score": best["score"],
            "n_sampled": self.n,
            "diversity_score": diversity,
            "low_diversity_warning": diversity < 0.3
        }
    
    def compute_diversity(self, candidates: list) -> float:
        # Embed candidates and compute average pairwise distance
        embeddings = [embed(c) for c in candidates]
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                similarities.append(cosine_similarity(embeddings[i], embeddings[j]))
        return 1 - np.mean(similarities)  # Higher = more diverse
```

**最適合：** 開放式生成、創意任務。準確度提升：10-30%。

---

## 多代理模式

### 多代理辯論

多個模型迭代地互相批評：

```python
class MultiAgentDebate:
    """
    Pattern: Multiple models debate to reduce hallucinations.
    
    Most effective when:
    1. Models have different biases (diverse model families)
    2. 2-3 rounds is optimal (more = diminishing returns)
    3. Explicit "devil's advocate" prompting improves results
    """
    
    def __init__(self, debaters: list, rounds: int = 2):
        self.debaters = debaters
        self.rounds = rounds
    
    async def debate(self, question: str) -> dict:
        # Round 0: Initial positions
        positions = await asyncio.gather(*[
            debater.generate(f"Answer this question with reasoning: {question}")
            for debater in self.debaters
        ])
        
        debate_history = [{"round": 0, "positions": positions}]
        
        # Debate rounds
        for round_num in range(1, self.rounds + 1):
            new_positions = []
            
            for i, debater in enumerate(self.debaters):
                other_positions = [p for j, p in enumerate(positions) if j != i]
                
                critique_prompt = f"""
Question: {question}

Your previous answer: {positions[i]}

Other perspectives:
{self.format_positions(other_positions)}

Consider the other perspectives. If they raise valid points, update your answer.
If you still disagree, explain why with specific reasoning.
Provide your final answer.
"""
                new_position = await debater.generate(critique_prompt)
                new_positions.append(new_position)
            
            positions = new_positions
            debate_history.append({"round": round_num, "positions": positions})
        
        # Final synthesis
        final_answer = await self.synthesize(question, debate_history)
        
        return {
            "answer": final_answer,
            "rounds": self.rounds,
            "consensus_reached": self.check_consensus(positions),
            "debate_history": debate_history
        }
```

**最適合：** 事實驗證、減少複雜答案中的幻覺。

### 代理混合（MoA）

多個模型餽入聚合器的分層架構：

```
┌─────────────────────────────────────────────────────────────────┐
│                    MIXTURE OF AGENTS (MoA)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1 (Proposers):                                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ Claude  │  │  GPT-4  │  │ Gemini  │  │ Llama   │            │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │
│       │            │            │            │                   │
│       └────────────┴─────┬──────┴────────────┘                  │
│                          │                                       │
│  Layer 2 (Aggregator):   ▼                                      │
│  ┌──────────────────────────────────────────────────┐           │
│  │  "Given these perspectives: [R1, R2, R3, R4]    │           │
│  │   Synthesize the best answer..."                 │           │
│  └────────────────────────┬─────────────────────────┘           │
│                           │                                      │
│                           ▼                                      │
│                    [Final Output]                                │
└─────────────────────────────────────────────────────────────────┘
```

```python
class MixtureOfAgents:
    def __init__(self, proposers: list, aggregator):
        self.proposers = proposers
        self.aggregator = aggregator
    
    async def generate(self, prompt: str) -> str:
        # Layer 1: Get diverse proposals
        proposals = await asyncio.gather(*[
            proposer.generate(prompt) for proposer in self.proposers
        ])
        
        # Layer 2: Aggregate
        aggregation_prompt = f"""
Given the following question and multiple expert responses, 
synthesize the best possible answer.

Question: {prompt}

Expert responses:
{self.format_proposals(proposals)}

Synthesize the best answer, combining the strongest elements from each response.
"""
        
        final_answer = await self.aggregator.generate(aggregation_prompt)
        return final_answer
```

**最適合：** 複雜綜合、報告生成、多領域問題。

---

## 集成與仲裁

### 概念區別

| 面向 | 集成學習 | 模型仲裁 |
|------|----------|----------|
| **目標** | 合併所有輸出 | 選擇單一最佳輸出 |
| **機制** | 聚合（投票、平均） | 選擇（評分、排名） |
| **關係** | 協作 | 競爭 |
| **最終輸出** | 來自所有模型的組合 | 單一獲勝者的輸出 |
| **使用時機** | 想要穩健性、減少變異 | 想要最佳品質 |

### 決策框架

```
Is there a single "correct" answer format?
├── Yes (classification, math)
│   └── Use Ensemble (voting/averaging)
│
└── No (creative writing, open QA)
    └── Use Arbitration (best-of-N)
        └── Do you have reliable scoring?
            ├── Yes → Reward model selection
            └── No → LLM-as-judge or human
```

---

## 成本與準確性權衡

### 集成成本矩陣

| 方法 | 成本倍數 | 延遲 | 準確度提升 | 使用時機 |
|------|----------|------|------------|----------|
| 單一模型 | 1x | 1x | 基準線 | 低風險、高容量 |
| 自我一致性 k=3 | 3x | 1x（並行） | +5-8% | 推理、延遲敏感 |
| 自我一致性 k=10 | 10x | 1x（並行） | +10-15% | 數學、準確性關鍵 |
| Best-of-N（N=8） | 8x + 評分 | 1x（並行） | +15-25% | 創意生成 |
| 裁判小組（3個） | 3x 評估 | 1x（並行） | 偏差減少 | 評估任務 |
| 多代理辯論 | 6x | 3x | 幻覺↓ | 事實關鍵 |
| 代理混合 | 5-8x | 2x | 更好綜合 | 複雜報告 |

### 何時不使用集成

| 情況 | 原因 | 替代方案 |
|------|------|----------|
| 簡單事實查詢 | 無多樣性優勢 | 單一 RAG 呼叫 |
| 需要 <500ms 延遲 | 集成增加延遲 | 單一模型 + 快取 |
| 成本是主要約束 | 集成倍增成本 | 模型蒸餾 |
| 模型高度相關 | 無多樣性 = 無收益 | 先取得多樣模型 |

---

## 面試問題

### Q: 何時使用自我一致性 vs Best-of-N？

**理想回答：**

「這兩者服務不同目的：

**自我一致性**適用於具有可提取、可驗證答案的任務：
- 數學問題：提取最終數字，多數投票
- 分類：對標籤投票
- 簡答 QA：對答案投票

關鍵是你可以比較答案是否相等。溫度 0.5-0.8 在保持一致性的同時提供多樣性。我對大多數任務使用 k=5-10。

**Best-of-N**適用於沒有單一正確答案的開放式生成：
- 創意寫作
- 解釋
- 可以有多種寫法的程式碼

在這裡我需要獎勵模型或裁判來評分候選，因為我無法只比較是否相等。通常 N=8-16。挑戰是避免獎勵破解，所以我使用帶有保守聚合的獎勵模型集成。

我不會對創意寫作使用自我一致性（無法提取答案）或對數學使用 Best-of-N（直接用投票，更簡單）。」

### Q: 如何防止 Best-of-N 中的獎勾破解？

**理想回答：**

「獎勵破解是模型利用獎勵模型的弱點而非真正提高品質的情況。

**我的緩解措施：**

1. **獎勵模型集成**：使用 3+ 多樣獎勵模型。一個樣本能破解一個 RM 不太可能同時破解所有。

2. **保守聚合**：不使用平均值，而是使用第 25 百分位數或最小值。這選擇在所有 RM 上都表現良好的樣本，而不僅僅是一個。

3. **多樣性監控**：追蹤樣本多樣性。如果多樣性降得太低，模型可能在利用狹窄的獎勵破解。我調整溫度或使用不同提示。

4. **人類校準**：定期驗證 RM 選擇的樣本確實符合人類偏好。

5. **多維度**：在多個標準（品質、安全性、相關性）上評分，並要求所有標準都表現良好，而非僅僅複合分數。

核心見解是任何單一獎勵信號都可以被操縱。集成使操縱變得困難得多。」

---

## 參考資料

- Verga et al. "Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models" (2024)
- Wang et al. "Self-Consistency Improves Chain of Thought Reasoning" (2023)
- Du et al. "Improving Factuality and Reasoning in Language Models through Multiagent Debate" (2023)

---

*前一篇：[防護欄與安全](01-guardrails.md)*
*下一篇：[可靠性模式](03-reliability-patterns.md)*
