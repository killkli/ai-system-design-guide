---
title: "常見問題：AI 工程、RAG（檢索增強生成）與代理"
description: "AI 工程、RAG（檢索增強生成）與代理的常見問題快速解答，每個答案均連結至深入說明的章節。"
---

# 常見問題：AI 工程、RAG（檢索增強生成） 與代理

Short, direct answers to the questions people ask most about modern AI 系統設計. Each answer points to the chapter where the topic is covered in depth.

## Table of Contents

- [General: AI Engineering Role](#general)
- [RAG（檢索增強生成） and Retrieval](#rag)
- [Agents and 工具使用](#代理)
- [Models and Selection](#models)
- [Evaluation and 可觀測性](#評估)
- [Inference and Cost](#inference)
- [Memory and State](#memory)
- [Security and Safety](#security)

---

## General

### What is an AI engineer?

An AI engineer builds 生產環境 systems on top of large language models. The role sits between traditional software engineering and machine learning research: less model training, more 系統設計 around models that already exist. Day-to-day work covers prompt and 上下文 engineering, 檢索 管線, 代理 loops, 評估 harnesses, and the infrastructure that keeps it all online. See [AI Job Market Trends](06-job-market-trends-2026.md).

### What is the difference between an AI engineer and an ML engineer?

ML engineers train, 微調, and ship models. AI engineers compose existing models (usually via APIs) into products. ML engineers spend their time on datasets and training loops. AI engineers spend their time on prompts, RAG（檢索增強生成）, 代理, 評估, and 延遲. The boundary blurs at large companies that do both. See [Transition Guide](../TRANSITION_GUIDE.md).

### How do I become an AI engineer?

If you already write 生產環境 code, the gap is small: learn how LLM（大型語言模型） behave, learn RAG（檢索增強生成） and 代理 patterns, learn 評估, and learn one inference stack. The [Transition Guide](../TRANSITION_GUIDE.md) maps your current role (backend, frontend, QA, PM, 資料, DevOps) to the AI roles that fit and the specific skills to close.

### What programming language should I learn for AI engineering?

Python is the default for AI work. TypeScript is the most common second language because frontend and edge 代理 stacks live there. C# and Go show up in enterprise infrastructure roles. Most 生產環境 AI code reads as ordinary application code: HTTP clients, queue consumers, database calls, plus calls to a model provider.

### Is AI engineering a good career?

Demand is strong and pay tracks senior software engineering, often higher at 前沿 labs. The risk is that the stack changes fast: a framework that mattered last year may be deprecated today. The skills that compound across releases are 評估, 系統設計, and 接地 debugging. See [Job Market Trends](06-job-market-trends-2026.md).

---

## RAG（檢索增強生成）

### What is RAG（檢索增強生成）?

檢索增強生成（Retrieval-Augmented Generation，RAG（檢索增強生成）） is the pattern of fetching external 上下文 (文件, rows, code, images) at query time and putting it in the LLM（大型語言模型）'s prompt so the model can ground its answer instead of 產生幻覺 from 訓練資料. It is the most common 生產環境 pattern for any LLM（大型語言模型） that needs to know things outside its training cutoff. See [RAG（檢索增強生成） Fundamentals](../06-檢索-systems/01-rag-fundamentals.md).

### How does RAG（檢索增強生成） work?

A user query is converted into a search request, the system retrieves the most relevant 區塊 from a knowledge store (vector DB, keyword index, graph, or a mix), reranks them, and passes the top results to the LLM（大型語言模型） as 上下文 for 生成. The two failure points are 檢索 (the right 區塊 was not returned) and 生成 (the model ignored or misused the 區塊). Most RAG（檢索增強生成） 失敗 are 檢索 失敗.

### Is RAG（檢索增強生成） dead because of long 上下文 windows?

No. Even with 1M-2M Token 上下文 windows on Claude Opus 4.7, Claude Sonnet 4.6, GPT-5.5, and Gemini 3.1 Pro, RAG（檢索增強生成） wins on cost, 延遲, freshness, and corpus scale. Enterprise datasets (SharePoint, log archives, code monorepos) exceed any 上下文窗口. RAG（檢索增強生成） acts as the filter that finds the 0.01% of 資料 worth putting into that high-value window. See [RAG（檢索增強生成） vs Long Context](../06-檢索-systems/14-生產環境-rag-at-scale.md).

### What is the difference between RAG（檢索增強生成） and 微調?

RAG（檢索增強生成） injects knowledge at query time through 上下文. 微調 bakes behavior into the weights. The rule of thumb: **RAG（檢索增強生成） for facts, 微調 for form**. Use RAG（檢索增強生成） when the knowledge changes, when you need citations, or when 資料 must stay outside the model. Use 微調 when you want a consistent tone, a strict output format, or lower 延遲 on repeated tasks. See [Fine-Tuning Strategies](../03-training-and-adaptation/02-微調-strategies.md).

### What is the best 向量資料庫?

There is no single best. Pinecone wins on managed scale and SLAs. Qdrant leads open-source speed (roughly 12ms p99 at 10M vectors). Weaviate has the strongest native hybrid (BM25（最佳匹配排序算法） + dense + metadata in one query). Milvus is the choice once you need distributed scale beyond 50M vectors. pgvector is the right answer if you are already on Postgres and your index is under 10M vectors. See [Vector Databases](../06-檢索-systems/04-vector-databases.md).

### What is contextual 檢索?

Contextual 檢索 is an Anthropic technique that prepends a short LLM（大型語言模型）-generated 上下文 summary to each 區塊 before 嵌入 and 索引 it, so the 區塊 carries its place in the 文件 with it. Anthropic reports a 49% reduction in 檢索 失敗 with 混合檢索, and 67% when combined with a reranker. See [Contextual Retrieval](../06-檢索-systems/10-contextual-檢索.md).

### What is 混合檢索?

Hybrid search combines sparse keyword 檢索 (typically BM25（最佳匹配排序算法）) with dense vector 檢索 and fuses the two ranked lists into one, usually with 倒序排名融合. The sparse arm catches exact Token (product codes, function names, rare nouns); the dense arm catches synonyms and intent. Every modern vector DB ships hybrid out of the box. See [Hybrid Search](../06-檢索-systems/05-hybrid-search.md).

### What is GraphRAG?

GraphRAG extracts entities and relationships from a corpus, builds a knowledge graph, and queries by traversal instead of (or alongside) vector similarity. It is the right pattern for **aggregative questions** ("summarize all legal risks across these 50 contracts") where vector RAG（檢索增強生成） returns related-but-disconnected 區塊. Microsoft's LazyGraphRAG defers expensive community summarization to query time, cutting 攝取 cost. See [GraphRAG](../06-檢索-systems/07-graph-rag.md).

### What is the best 區塊 size for RAG（檢索增強生成）?

There is no universal answer. 300-500 Token 區塊 with 50-Token overlap is a reasonable default for prose. Code and structured 資料 want larger 區塊 (1000-2000 Token). The bigger wins come from **structure-aware 分塊** (split at headers, paragraphs, code blocks), **contextual 分塊** (prepend a summary), and **hierarchical 分塊** (index small 區塊, return the parent 上下文). See [Chunking Strategies](../06-檢索-systems/02-分塊-strategies.md).

---

## Agents

### What is an AI 代理?

An AI 代理 is a system where an LLM（大型語言模型） decides what to do next, runs a tool, observes the result, and decides again, all in a loop. The simplest 代理 is the ReAct（推理與行動結合） pattern: Thought → Action → Observation → repeat. Modern 代理 (Claude Opus 4.7, GPT-5.5 reasoning, DeepSeek-R2) bake the reasoning step into the model itself. See [Agent Fundamentals](../07-agentic-systems/01-代理-fundamentals.md).

### What is the difference between an 代理 and a chatbot?

A chatbot responds to a message. An 代理 **takes actions** in the world: runs code, calls APIs, reads files, sends messages, books appointments. That distinction matters because actions are hard to roll back, so 代理 need very different 護欄, 沙箱化, and human-in-the-loop patterns. See [Agentic Security](../07-agentic-systems/09-agentic-security-and-沙箱化.md).

### What is MCP（模型上下文協議） (模型上下文協議（Model Context Protocol，MCP）)?

MCP（模型上下文協議） is an open protocol that lets LLM（大型語言模型） applications connect to tools and 資料 sources through a standard interface. Anthropic launched it in November 2024. Governance moved to the Linux Foundation's Agentic AI Foundation in December 2025. Adoption is universal: Anthropic, OpenAI, Google, Microsoft, AWS all support it. As of May 2026 there are over 2,300 public MCP（模型上下文協議） servers. See [工具使用 and MCP（模型上下文協議）](../07-agentic-systems/03-tool-use-and-mcp.md).

### What is the best 代理 framework?

The big three cover most 生產環境 needs. **LangGraph** (graph-based, surpassed CrewAI in stars in early 2026) is the default for stateful multi-代理 control flow with checkpointing. **CrewAI** (now v1.13, used in 60%+ of the Fortune 500) is the choice for role-based business automation. **Microsoft Agent Framework** (RC 1.0 February 2026, GA Q2 2026) is the consolidated successor to AutoGen and Semantic Kernel for enterprise .NET and Python. See [Framework Selection Guide](../09-frameworks-and-tools/08-framework-selection-guide.md).

### What is 代理 RAG（檢索增強生成）?

Agentic RAG（檢索增強生成） replaces the linear retrieve-then-generate 管線 with a loop where the 代理 decides what to retrieve, evaluates whether the results are good enough, and re-queries if not. Patterns include 自我 RAG（檢索增強生成） (model emits 反思 Token), 修正型 RAG（檢索增強生成） (separate grader), 自適應 RAG（檢索增強生成） (classifier picks the depth), and multi-hop decomposition. Budget for 8-12 seconds per query at three to four iterations. See [Agentic RAG（檢索增強生成）](../06-檢索-systems/08-agentic-rag.md).

### How do computer-use 代理 work?

A computer-use 代理 takes screenshots of a desktop or browser, decides on a mouse and keyboard action, executes it, and takes another screenshot. The three 生產環境 options are Claude Computer Use (OS-portable via screenshots), Google Gemini Computer Use (browser-optimized via DOM awareness), and OpenAI Operator (web-task focused). Claude Sonnet 4.6 reaches 72.5% on OSWorld-Verified, up from 14.9% at the October 2024 launch. See [Computer-Use Agents](../17-tool-use-and-computer-代理/04-computer-use-代理.md).

---

## Models

### What is the best LLM（大型語言模型） right now?

There is no single best model in May 2026. The leaderboard has fractured by task. **Claude Opus 4.7** leads SWE-bench Pro at 64.3% for complex coding. **GPT-5.5** leads Terminal-Bench 2.0 at 82.7% for agentic terminal work. **Gemini 3.1 Pro** leads GPQA Diamond at 94.3% for scientific reasoning. **Claude Sonnet 4.6** delivers around 90% of Opus 4.7's quality at 40% of the price. See [Model Taxonomy](../02-model-landscape/01-model-taxonomy.md).

### How much does Claude / GPT / Gemini / DeepSeek cost?

Pricing changes monthly. As of May 2026, 前沿-tier closed models run roughly $3-15 per million input Token and $15-75 per million output Token, with 快取 cutting that 75-90% on repeated prefixes. Mid-tier models (Claude Sonnet 4.6, GPT-5.5-mini, Gemini 3.1 Flash) run roughly $0.30-3 / $1-15 per million. **DeepSeek reset the floor**: V4 Pro is $0.435 / $0.87 per 1M (75% discount made permanent May 22, 2026), and V4 Flash is $0.14 / $0.28 per 1M with a 1M 上下文窗口, roughly 10x cheaper than the closed 前沿 for many tasks. Always cross-check the provider pricing pages for current rates. See [Pricing and Costs](../02-model-landscape/03-pricing-and-成本.md).

### What is the difference between Claude Opus and Claude Sonnet?

Opus is Anthropic's 前沿 tier: smartest, slowest, most expensive. Sonnet is the 生產環境 workhorse: roughly 90% of Opus quality at 40% of the price. Haiku is the fast tier: cheap, low-延遲, good for routing and classification. The right pattern is to route easy queries to Haiku, mid queries to Sonnet, and only hard ones to Opus. See [Model Selection](../02-model-landscape/04-model-selection-guide.md).

### Should I use an open-source model?

Yes for cost-per-query at high volume, 資料 residency, or 微調 needs. Open-weight quality has closed to within 5-15 points of the closed 前沿 (Qwen3-Embedding-8B leads MTEB Multilingual, Llama 4 Maverick and DeepSeek V4 Pro are competitive 前沿 picks). The tradeoff is operational: you own the inference stack, the GPU bill, and the security patches. See [Model Landscape](../02-model-landscape/01-model-taxonomy.md).

### What is 提示快取?

Prompt 快取 keeps the KV 快取 for a fixed prompt prefix warm on the inference server so subsequent calls only pay for the new Token. All major providers support it. Cache reads are 75-90% cheaper than fresh Token. The catch: 快取 writes typically cost 25% more, so 快取 only pays off if you reuse the same prefix at least 3-5 times within the TTL (usually 5 minutes). See [KV Cache and Context Caching](../04-inference-optimization/02-kv-快取-and-上下文-快取.md).

---

## Evaluation

### How do you evaluate an LLM（大型語言模型）?

LLM（大型語言模型） 評估 is layered: **reference-free 指標** (忠實度, relevance, coherence via LLM（大型語言模型）-as-judge) for rapid iteration, **golden test sets** for 回歸, and **task-specific 指標** (exact match for QA, BLEU for translation, pass@k for code). For RAG（檢索增強生成） specifically, use the RAG（檢索增強生成） Triad: 上下文相關性, 忠實度, 答案相關性. See [LLM（大型語言模型） Evaluation](../14-評估-and-可觀測性/01-llm-評估.md).

### What is LLM（大型語言模型）-as-judge?

LLM（大型語言模型）-as-judge uses one LLM（大型語言模型） to score the output of another against a rubric (correctness, helpfulness, safety). It scales where human 評估 cannot, but has known biases: position bias, verbosity bias, self-preference bias. The standard practice is to use a stronger model as judge (Claude Opus 4.7 or GPT-5.5 reasoning), randomize positions, and validate against a small human-labeled sample.

### What is the best LLM（大型語言模型） 可觀測性 tool?

The leading platforms are **Langfuse** (best self-hosted open-source, acquired by ClickHouse in January 2026), **Braintrust** (best for 評估-driven CI/CD with 品質門檻), **LangWatch** (best for 代理 simulation), **LangSmith** (LangChain-native), and **Arize Phoenix** (OTel-native). Pick based on 部署 model (SaaS vs self-hosted), whether you need CI/CD gating, and how heavily you use a specific framework. See [可觀測性](../14-評估-and-可觀測性/02-可觀測性.md).

### What is RAGAS（RAG 評估框架）?

RAGAS（RAG 評估框架） (Retrieval Augmented Generation Assessment) is a Python library for RAG（檢索增強生成） 評估. It provides reference-free 指標 (忠實度, 答案相關性, 上下文相關性) and reference-based 指標 (上下文召回率, 上下文 precision) computed with LLM（大型語言模型）-as-judge. It is the de facto starting point for any RAG（檢索增強生成） 評估 管線. See [RAG（檢索增強生成） Evaluation](../06-檢索-systems/13-rag-評估-patterns.md).

---

## Inference

### What is vLLM?

vLLM is an open-source LLM（大型語言模型） inference engine that pioneered 分頁注意力機制 (virtual-memory-style allocation of the KV 快取). It is the default open inference engine when the workload is "Llama, Mistral, Qwen, or DeepSeek under continuous 批次處理." It is the easiest to operate and best-patched of the major engines. Multimodal deployments must run v0.18.2+ due to a February 2026 CVE. See [Serving Infrastructure](../04-inference-optimization/06-serving-infrastructure.md).

### What is the difference between vLLM and SGLang?

Both are open-source inference engines. vLLM has broader model coverage and operational maturity. SGLang has roughly 29% higher 吞吐量 on structured-output and function-calling workloads thanks to async constrained decoding, and best-in-class prefix-快取 reuse via RadixAttention. Important caveat: SGLang's multimodal path has unpatched CVEs as of May 2026, so multimodal traffic should run on vLLM v0.18.2+ instead.

### What is TensorRT-LLM（大型語言模型）?

NVIDIA's inference engine. Delivers 2-4x higher 吞吐量 than vLLM and TGI on H100/H200/B200, but at the cost of 1-2 weeks of setup and a hard NVIDIA lock-in. The right choice when you have committed NVIDIA capacity and the 吞吐量 delta pays for the operational tax.

### How do you optimize LLM（大型語言模型） inference cost?

Five high-leverage moves: **model cascading** (route easy queries to small models, hard ones to 前沿), **提示快取** (75-90% off repeated prefixes), **semantic 快取** (skip the LLM（大型語言模型） call entirely for similar queries), **量化** (FP8 or 4-bit weights to fit more on a GPU), and **continuous 批次處理** (vLLM/SGLang batch at the iteration level). Together they routinely cut inference cost by 10x without losing quality. See [Cost Optimization](../04-inference-optimization/07-cost-optimization-playbook.md).

### What is 推測解碼?

Speculative decoding lets an LLM（大型語言模型） generate multiple Token per forward pass by having a cheaper "draft" model (or extra heads on the main model, like Medusa) predict the next few Token, then verifying them all in a single parallel pass on the target model. The win is 2-3x faster wall-clock 生成 with zero quality loss. Built into vLLM and TensorRT-LLM（大型語言模型）. See [Speculative Decoding](../04-inference-optimization/03-speculative-decoding.md).

---

## Memory

### What is the best AI 代理 memory framework?

The four mature options as of May 2026 are **Mem0** (broadest standalone memory layer, scores 92.5 on LoCoMo and 94.4 on LongMemEval), **Zep** (temporal-aware 生產環境 管線 with native conversation summarization), **Letta** (OS-style paging for long-running 代理 with unbounded memory), and **Cognee** (knowledge-graph-first for RAG（檢索增強生成）-heavy workflows). Pick by use case: chatbot personalization → Mem0; 生產環境 代理 at scale → Zep; long-horizon task 代理 → Letta; KG-接地 RAG（檢索增強生成） → Cognee. See [Agentic Memory](../08-memory-and-state/04-agentic-memory-mem0.md).

### What is the difference between short-term and long-term memory in 代理?

Short-term memory lives in the LLM（大型語言模型）'s 上下文窗口 (the current turn, tool outputs, scratchpad). Long-term memory persists across sessions in a vector DB, graph, or relational store. Memory architectures split further: **episodic** (past trajectories), **semantic** (extracted facts about the user/world), **procedural** (learned skills, playbooks). Picking the right tier for a given fact matters: a session preference promoted to long-term memory leaks across sessions. See [Memory Architectures](../08-memory-and-state/01-memory-architectures.md).

### How does a knowledge graph help an AI 代理?

A knowledge graph stores entities and relationships explicitly (User → OWNER_OF → Project_A). It gives the 代理 **deterministic** 檢索 over structured relationships, which vector search cannot. The strongest pattern is hybrid: vector search finds the entry node by similarity, graph traversal expands relevant 上下文. Used for compliance, multi-hop reasoning, and any domain where relationships are first-class (legal, biomedical, finance). See [Long-Term Memory](../08-memory-and-state/03-long-term-memory.md).

---

## Security

### What is 提示注入?

Prompt injection is the LLM（大型語言模型）-era version of SQL injection: malicious content in a user input or a retrieved 文件 overrides the system instructions and makes the model do something it should not. **Direct injection** is in the user prompt. **Indirect injection** is hidden in a 文件 the model reads (a webpage, an email, a PDF). The OWASP LLM（大型語言模型） Top 10 lists it as the #1 LLM（大型語言模型） risk. See [Prompt Injection Defense](../05-prompting-and-上下文/08-prompt-injection-defense.md).

### How do you prevent 提示注入?

There is no silver bullet: 提示注入 cannot be fully "escaped" the way SQL can. The 生產環境 defense stack combines: **input isolation** (XML tags marking untrusted content), **dual-LLM（大型語言模型） patterns** (small guard model classifies intent before the main model sees the input), **canary Token** (detect if the model leaked its system prompt), **least-privilege tool scopes**, and **human-in-the-loop** on destructive tool calls. See [Agentic Security](../07-agentic-systems/09-agentic-security-and-沙箱化.md).

### What is OWASP LLM（大型語言模型） Top 10?

The OWASP Top 10 for LLM（大型語言模型） Applications (v2.0, released 2025) is the canonical list of LLM（大型語言模型） security risks. Top entries: 提示注入, insecure output handling, 訓練資料 poisoning, model denial of service, supply chain vulnerabilities, sensitive information disclosure, insecure plugin design, excessive agency, overreliance, and model theft. The 2026 update for agentic apps adds goal hijacking, identity abuse, and cascading 失敗 as top risks. See [LLM（大型語言模型） Security](../12-security-and-access/01-llm-security.md).

### What is 沙箱化 in AI 代理?

Sandboxing isolates the code an 代理 generates and runs from the host system. The standard pattern uses ephemeral micro-VMs (E2B, Docker, Firecracker) that spin up in under 10ms, run the code, and get destroyed. Without 沙箱化, a prompt-injected 代理 can `rm -rf /` or exfiltrate secrets. With 沙箱化, the worst case is a destroyed throwaway container.

---

## Related Reading

- [Question Bank (110 senior interview questions)](01-question-bank.md)
- [Answer Frameworks](02-answer-frameworks.md)
- [Common Pitfalls](03-common-pitfalls.md)
- [Whiteboard Exercises](04-whiteboard-exercises.md)
- [AI Job Market Trends](06-job-market-trends-2026.md)

---

*Have a question that should be here? Open an issue or PR on the repo.*
