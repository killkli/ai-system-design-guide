# AI 系統設計面試常見陷阱

This chapter covers frequent mistakes candidates make in AI 系統設計 interviews, why they hurt your 評估, and how to avoid them.

## Table of Contents

- [Architecture Pitfalls](#architecture-pitfalls)
- [Technical Knowledge Pitfalls](#technical-knowledge-pitfalls)
- [Communication Pitfalls](#communication-pitfalls)
- [Interview Strategy Pitfalls](#interview-strategy-pitfalls)
- [AI-Specific Pitfalls](#ai-specific-pitfalls)
- [Checklists for Self-Review](#checklists-for-self-review)

---

## Architecture Pitfalls

### Pitfall 1: Skipping the Data Pipeline

**What goes wrong:**
Candidates design the inference path in detail but barely mention how 資料 gets into the system.

**Why it matters:**
Data quality drives AI system quality. A beautiful RAG（檢索增強生成） architecture is useless if the 文件 攝取 管線 produces garbage 區塊.

**What interviewers notice:**
- No mention of how 文件 are processed
- Assumes 嵌入 magically appear
- Ignores updates and deletions

**Better approach:**
```
"Before discussing retrieval, let me walk through the data pipeline:

1. Document ingestion: File upload, API integration, crawler
2. Preprocessing: Format conversion, cleaning, metadata extraction
3. Chunking: [Strategy] based on document structure
4. Embedding: Batch processing with [model]
5. Indexing: Upsert to vector database with metadata
6. Updates: Incremental re-indexing on document changes"
```

---

### Pitfall 2: One-Size-Fits-All Model Selection

**What goes wrong:**
Candidates say they would use GPT-4 (or any single model) for everything.

**Why it matters:**
Different tasks have different requirements. Using a 前沿模型 for classification is wasteful. Using a small model for complex reasoning fails.

**What interviewers notice:**
- No discussion of cost implications
- No consideration of 延遲 requirements
- No model cascade or routing

**Better approach:**
```
"Model selection varies by task:

- Intent classification: Fine-tuned BERT or GPT-4o-mini
- Simple responses: Claude Haiku or GPT-4o-mini  
- Complex reasoning: GPT-4o or Claude 3.5 Sonnet
- Code generation: Claude 3.5 Sonnet or Codestral

I would implement a router that classifies query complexity 
and routes to the appropriate model. This typically reduces 
costs 60-70% with minimal quality impact."
```

---

### Pitfall 3: Ignoring the Evaluation Layer

**What goes wrong:**
Candidates describe how to build the system but not how to know if it works.

**Why it matters:**
AI systems fail in subtle ways. Without 評估, you ship broken systems and never detect degradation.

**What interviewers notice:**
- No 測試集 mentioned
- No quality 指標 defined
- No 監控 for 生產環境 issues

**Better approach:**
```
"Evaluation has three layers:

1. Offline: Golden test set evaluated on every change
   - Retrieval: Precision@5, Recall@5, MRR
   - Generation: Faithfulness, relevance (RAGAS)
   - End-to-end: Answer correctness vs ground truth

2. Online: Sampled evaluation in production
   - LLM-as-judge on 5% of requests
   - User feedback (thumbs up/down)
   - Completion rate for task-oriented queries

3. Alerting: Automated detection
   - Quality score drops below threshold
   - Latency exceeds SLA
   - Error rate spikes"
```

---

### Pitfall 4: Underestimating Multi-Tenancy Complexity

**What goes wrong:**
Candidates treat 多租戶 RAG（檢索增強生成） as simply adding a "tenant_id" field.

**Why it matters:**
Multi-tenant AI systems have unique 失敗模式 around 資料 leakage, isolation, and fair resource allocation.

**What interviewers notice:**
- Post-檢索 filtering (major red flag)
- No discussion of 快取 isolation
- No consideration of noisy neighbor

**Better approach:**
```
"Multi-tenancy for RAG is harder than traditional systems:

1. Retrieval isolation: Filter BEFORE retrieval at the database level
   WRONG: retrieve(query, top_k=100) then filter by tenant
   RIGHT: retrieve(query, top_k=10, filter={tenant_id: X})

2. Context isolation: Never mix tenants in LLM context

3. Cache isolation: Scope all cache keys by tenant
   cache_key = f'{tenant_id}:{query_hash}'

4. Embedding isolation: Consider tenant-specific embedding spaces
   for highest security requirements

5. Audit: Log tenant context for all operations

I would also run regular isolation tests with adversarial 
queries designed to probe for cross-tenant leakage."
```

---

### Pitfall 5: No Graceful Degradation

**What goes wrong:**
The system has no 降級 when the LLM（大型語言模型） provider is down, rate-limited, or returning errors.

**Why it matters:**
LLM（大型語言模型） providers have outages. Rate limits get hit. Failure handling separates 生產環境-ready from prototype.

**What interviewers notice:**
- No mention of fallbacks
- No retry strategy
- Single provider dependency

**Better approach:**
```
"Reliability layers:

1. Retry with backoff: Transient errors get retried
   - Exponential backoff with jitter
   - Max 3 attempts

2. Fallback providers: If primary fails, try secondary
   - OpenAI → Anthropic → local model
   - Abstract the interface to enable swapping

3. Cached responses: Return cached results for known queries
   - Exact match cache for repeated questions
   - Semantic cache for similar questions

4. Graceful degradation: Partial functionality on failure
   - Retrieval fails → return direct LLM response with disclaimer
   - LLM fails → return relevant chunks without synthesis

5. Circuit breaker: Fail fast when provider is degraded
   - Prevents cascading latency issues"
```

---

## Technical Knowledge Pitfalls

### Pitfall 6: Confusing Embedding and Generation Models

**What goes wrong:**
Candidates talk about generating text with 嵌入 models or treating 生成 as 檢索.

**What to know:**
- **Embedding models:** Map text → vector. Used for search/檢索.
- **Generation models:** Produce text given a prompt. Used for responses.

**How they connect:**
RAG（檢索增強生成） uses 嵌入 models for 檢索, then passes retrieved 區塊 to a 生成模型.

---

### Pitfall 7: Misunderstanding Context Windows

**What goes wrong:**
- Assuming 128K 上下文 means 128K Token of useful 上下文
- Not accounting for system prompt, retrieved 區塊, and conversation history
- Ignoring the "中間遺失問題" phenomenon

**What to know:**
- Context window is the limit, not the target
- Attention degrades for middle content
- Practical useful 上下文 is much smaller than the limit

**Better framing:**
```
"While GPT-4o supports 128K tokens, I design for much smaller effective context:

- System prompt: ~500 tokens
- Retrieved context: 3-5 chunks × 500 tokens = 1.5-2.5K
- Conversation history: Last 5 turns × 300 tokens = 1.5K
- Buffer for output: ~2K

Total active context: ~7K tokens, well below limit.

This keeps the model focused on relevant information and 
avoids the lost-in-the-middle problem documented in Liu et al."
```

---

### Pitfall 8: Not Understanding Token Economics

**What goes wrong:**
Candidates discuss features without understanding cost implications.

**What to know:**
- Pricing is per Token, input vs output often priced differently
- Output Token cost 2-4x input Token for most providers
- Streaming does not change cost

**Quick reference (December 2025, verify current):**

| Model | Input/1M | Output/1M |
|-------|----------|-----------|
| GPT-4o | $2.50 | $10 |
| GPT-4o-mini | $0.15 | $0.60 |
| Claude 3.5 Sonnet | $3 | $15 |
| Claude 3.5 Haiku | $0.25 | $1.25 |
| Gemini 1.5 Pro | $1.25 | $5 |

**Cost calculation example:**
```
10,000 queries/day
Average: 2K input tokens, 500 output tokens
Model: GPT-4o

Daily cost = 10K × (2K × $2.50/1M + 500 × $10/1M)
          = 10K × ($0.005 + $0.005)
          = 10K × $0.01
          = $100/day = $3K/month
```

---

### Pitfall 9: Shallow Understanding of RAG（檢索增強生成） Components

**What goes wrong:**
Candidates can list the components (分塊, 嵌入, 檢索, 生成) but cannot explain the tradeoffs within each.

**Depth expected for 區塊:**
- Why 區塊 at all? (Context limits, 檢索 precision)
- Chunk size tradeoffs? (Smaller = more precise, larger = more 上下文)
- Overlap purpose? (Prevent losing 上下文 at boundaries)
- When to use semantic 分塊? (Complex 文件 with variable structure)

**Depth expected for 檢索:**
- Why 混合檢索? (Dense good at semantics, sparse good at keywords)
- What is 重新排序? (Two-stage: fast recall then accurate ranking)
- How to handle no results? (Fallback strategies)

---

### Pitfall 10: Treating Prompts as Magic

**What goes wrong:**
Candidates hand-wave "and then we prompt the model to..." without discussing prompt engineering.

**What interviewers want to see:**
- Prompt structure (system, 上下文, user)
- Instruction clarity
- Output format specification
- Few-shot examples if appropriate
- Defense against edge cases

**Better approach:**
```
"The generation prompt has this structure:

SYSTEM:
You are a support assistant for [Product]. Answer questions 
using ONLY the provided context. If the context does not 
contain the answer, say 'I don't have information about that.'
Always cite the source document.

CONTEXT:
[Retrieved chunks with source metadata]

USER:
[User's question]

I specify the output format explicitly and use few-shot 
examples for complex response structures. For this use case, 
I also include negative examples showing when to abstain."
```

---

## Communication Pitfalls

### Pitfall 11: Monologuing Without Interaction

**What goes wrong:**
Candidates talk for 10-15 minutes without checking in with the interviewer.

**Why it matters:**
Interviews are conversations. Monologuing misses signals about what the interviewer cares about.

**Better approach:**
Check in every 3-5 minutes:
- "Should I go deeper on 檢索 or move to 生成?"
- "Does this architecture make sense before I discuss details?"
- "Is there a specific component you would like me to focus on?"

---

### Pitfall 12: Not Leading with Structure

**What goes wrong:**
Candidates start talking without signaling what they will cover.

**Why it matters:**
Interviewers have mental models. If they cannot map your answer to their expectations, you seem disorganized.

**Better approach:**
Lead with a roadmap:
```
"I will structure my answer in four parts:
1. High-level architecture
2. Deep dive on the RAG pipeline
3. Scaling and reliability
4. Evaluation approach

Let me start with the high-level architecture..."
```

---

### Pitfall 13: Technical Jargon Without Explanation

**What goes wrong:**
Candidates drop terms like "分頁注意力機制" or "GQA" without explaining them.

**Why it matters:**
If the interviewer does not know the term, you seem like you are name-dropping. If they do know it, they might ask 追問 questions you cannot answer.

**Better approach:**
Brief explanation when introducing terms:
```
"I would use vLLM which implements PagedAttention. 
This manages the KV cache like virtual memory, reducing 
fragmentation and enabling higher throughput."
```

---

### Pitfall 14: Defending Wrong Answers

**What goes wrong:**
When the interviewer hints that an approach is wrong, candidates double down instead of reconsidering.

**Why it matters:**
Stubbornness is a red flag. Being coachable is valuable.

**Better approach:**
```
Interviewer: "What about the case where..."
You: "That is a good point. I had not considered [X]. 
Let me revise my approach..."
```

---

## Interview Strategy Pitfalls

### Pitfall 15: Solving a Different Problem

**What goes wrong:**
Candidates get excited about a particular technology and design for that instead of the stated requirements.

**Example:**
Asked to design a simple Q&A system, candidate designs a complex multi-代理 system with autonomous research capabilities.

**Better approach:**
Design to requirements, then offer extensions:
```
"This design meets the core requirements. If we wanted to 
extend it to handle more complex multi-step queries, we 
could add an agent layer, but I would not start there."
```

---

### Pitfall 16: Not Managing Time

**What goes wrong:**
Candidates spend 20 minutes on architecture and have no time for 評估, reliability, or scaling.

**Better approach:**
Allocate time explicitly:
- Clarification: 3-5 min
- High-level design: 5-7 min
- Deep dives: 10-15 min
- Evaluation/reliability: 5-7 min
- Questions/wrap-up: 3-5 min

Check the clock and adjust.

---

### Pitfall 17: Not Drawing

**What goes wrong:**
Candidates describe architecture verbally without diagramming.

**Why it matters:**
Visual communication is clearer and shows you can communicate with stakeholders.

**Better approach:**
Draw boxes and arrows as you explain. Label clearly. Use the diagram as a reference through the discussion.

---

## AI-Specific Pitfalls

### Pitfall 18: Treating AI Components as Black Boxes

**What goes wrong:**
Candidates treat "call the LLM（大型語言模型）" as an atomic operation without understanding what happens inside.

**Expectation for senior roles:**
- Understand 預填充 vs 解碼 phases
- Know what affects 延遲 (首 Token 到達時間 vs 每秒 Token 數)
- Understand KV 快取 implications
- Be aware of 批次處理 effects

---

### Pitfall 19: Ignoring Hallucination Risk

**What goes wrong:**
Candidates design systems that blindly trust LLM（大型語言模型） output.

**Why it matters:**
Hallucinations are inherent to LLM（大型語言模型）. Production systems must handle them.

**Better approach:**
```
"Hallucination mitigation has multiple layers:

1. Retrieval grounding: Answer from context only
2. Citation enforcement: Every claim cites a source
3. Abstention: Model says 'I don't know' when appropriate
4. Output validation: Check for impossible claims
5. Confidence display: Show users when to verify"
```

---

### Pitfall 20: Security as an Afterthought

**What goes wrong:**
Security considerations come at the end, if at all.

**Why it matters:**
AI systems have novel attack surfaces (提示注入, 資料 leakage). Security needs to be designed in.

**Better approach:**
Weave security into the design:
```
"For the retrieval layer, I use metadata filtering at the 
database level to ensure tenant isolation. The system prompt 
uses instruction hierarchy to resist injection. Output 
passes through a content filter before reaching the user."
```

---

## Checklists for Self-Review

### Before the Interview

- [ ] Reviewed RAG（檢索增強生成） architecture patterns
- [ ] Know current model pricing (ballpark)
- [ ] Can explain 分塊 strategies
- [ ] Understand 嵌入 vs 生成
- [ ] Know common 評估 指標
- [ ] Can discuss at least one 向量資料庫
- [ ] Understand 多租戶 challenges
- [ ] Can discuss prompt engineering techniques

### During the Interview

- [ ] Asked clarifying questions
- [ ] Stated priorities and tradeoffs
- [ ] Drew a diagram
- [ ] Mentioned 評估 approach
- [ ] Discussed 失敗模式
- [ ] Addressed security/isolation
- [ ] Checked in with interviewer
- [ ] Managed time across sections

### After Each Section

- [ ] Did I explain WHY, not just WHAT?
- [ ] Did I mention tradeoffs?
- [ ] Did I use concrete numbers where applicable?
- [ ] Did I avoid unnecessary complexity?

---

*See also: [Question Bank](01-question-bank.md) | [Answer Frameworks](02-answer-frameworks.md) | [Whiteboard Exercises](04-whiteboard-exercises.md)*
