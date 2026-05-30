#!/usr/bin/env python3
"""Translate AI System Design Guide files to Traditional Chinese (Taiwan)"""
import re, sys

# Glossary-based translation dictionary (en -> zh-TW)
GLOSSARY = {
    # Core terms
    "Large Language Model": "大型語言模型（Large Language Model，LLM）",
    "LLM": "LLM（大型語言模型）",
    "LLMs": "LLM（大型語言模型）",
    "RAG": "RAG（檢索增強生成）",
    "Retrieval-Augmented Generation": "檢索增強生成（Retrieval-Augmented Generation，RAG）",
    
    # Agentic / Agents
    "agentic": "代理系統",
    "agentic system": "代理系統",
    "agentic systems": "代理系統",
    "Agentic": "代理系統",
    "AI agent": "AI 代理",
    "AI agents": "AI 代理",
    "agent": "代理",
    "agents": "代理",
    "multi-agent": "多代理",
    "multi-agent": "多代理",
    "multi-agent": "多代理",
    "agentic coding": "代理程式編碼",
    "agentic RAG": "代理 RAG",
    
    # Tool use / MCP
    "tool use": "工具使用",
    "Tool Use": "工具使用",
    "MCP": "MCP（模型上下文協議）",
    "Model Context Protocol": "模型上下文協議（Model Context Protocol，MCP）",
    "function calling": "函式呼叫",
    "Function Calling": "函式呼叫",
    
    # RAG components
    "embedding": "嵌入",
    "embeddings": "嵌入",
    "embedding model": "嵌入模型",
    "embedding models": "嵌入模型",
    "vector database": "向量資料庫",
    "vector databases": "向量資料庫",
    "chunking": "分塊",
    "hybrid search": "混合檢索",
    "hybrid search": "混合檢索",
    "reranking": "重新排序",
    "rerank": "重新排序",
    "reciprocal rank fusion": "倒序排名融合",
    "BM25": "BM25（最佳匹配排序算法）",
    "sparse retrieval": "稀疏檢索",
    "dense retrieval": "密集檢索",
    
    # Model / Training
    "fine-tuning": "微調",
    "Fine-tuning": "微調",
    "fine-tune": "微調",
    "Fine-tune": "微調",
    "LoRA": "LoRA（低秩適配）",
    "QLoRA": "QLoRA（量化低秩適配）",
    "RLHF": "RLHF（人類回饋強化學習）",
    "DPO": "DPO（直接偏好優化）",
    "training data": "訓練資料",
    "quantization": "量化",
    "Quantization": "量化",
    
    # Inference / Optimization
    "KV cache": "KV 快取",
    "KV Cache": "KV 快取",
    "PagedAttention": "分頁注意力機制",
    "speculative decoding": "推測解碼",
    "batching": "批次處理",
    "Continuous batching": "連續批次處理",
    "prefill": "預填充",
    "decode": "解碼",
    "prefill vs decode": "預填充與解碼",
    "TTFT": "首 Token 到達時間",
    "TPS": "每秒 Token 數",
    "prefix caching": "前綴快取",
    "prompt caching": "提示快取",
    
    # Evaluation
    "LLM-as-judge": "LLM 擔任評判",
    "LLM-as-judge": "LLM 擔任評判",
    "RAGAS": "RAGAS（RAG 評估框架）",
    "faithfulness": "忠實度",
    "answer relevance": "答案相關性",
    "context relevance": "上下文相關性",
    "context recall": "上下文召回率",
    "evaluation": "評估",
    "evaluation": "評估",
    "eval": "評估",
    "evals": "評估",
    "observability": "可觀測性",
    
    # Model types
    "frontier model": "前沿模型",
    "frontier models": "前沿模型",
    "SLM": "小型語言模型（SLM）",
    "small language model": "小型語言模型",
    "reasoning model": "推理模型",
    "reasoning models": "推理模型",
    "embedding model": "嵌入模型",
    "generation model": "生成模型",
    
    # System design
    "multi-tenancy": "多租戶",
    "multi-tenant": "多租戶",
    "Context Window": "上下文窗口",
    "context window": "上下文窗口",
    "lost in the middle": "中間遺失問題",
    "hallucination": "幻覺",
    "hallucinations": "幻覺",
    "grounding": "接地",
    "context stuffing": "上下文填充",
    "pipeline": "管線",
    "pipelines": "管線",
    
    # Agent patterns
    "ReAct": "ReAct（推理與行動結合）",
    "Self-RAG": "自我 RAG",
    "Corrective RAG": "修正型 RAG",
    "Adaptive RAG": "自適應 RAG",
    "reflection tokens": "反思 Token",
    
    # Security
    "prompt injection": "提示注入",
    "prompt injection": "提示注入",
    "jailbreak": "越獄攻擊",
    "prompt injection defense": "提示注入防禦",
    "guardrails": "護欄",
    "sandboxing": "沙箱化",
    
    # Other technical
    "attention mechanism": "注意力機制",
    "self-attention": "自注意力機制",
    "transformer": "Transformer（變壓器）",
    "token": "Token",
    "tokens": "Token",
    "HNSW": "HNSW（分層可導航小世界圖）",
    "ANN": "近似最近鄰（ANN）",
    "inverted file index": "倒排檔索引",
    "product quantization": "乘積量化",
    "cosine similarity": "餘弦相似度",
    "semantic search": "語義檢索",
    
    # Frameworks
    "LangChain": "LangChain",
    "LangGraph": "LangGraph",
    "LangSmith": "LangSmith",
    "Langfuse": "Langfuse",
    "LlamaIndex": "LlamaIndex",
    "CrewAI": "CrewAI",
    
    # Inference engines
    "vLLM": "vLLM",
    "SGLang": "SGLang",
    "TensorRT-LLM": "TensorRT-LLM",
    "PagedAttention": "分頁注意力機制",
    
    # Companies / Models
    "Anthropic": "Anthropic",
    "OpenAI": "OpenAI",
    "Claude": "Claude",
    "GPT-4o": "GPT-4o",
    "GPT-5.5": "GPT-5.5",
    "Gemini": "Gemini",
    "DeepSeek": "DeepSeek",
    
    # Interview / Career
    "system design": "系統設計",
    "whiteboard exercise": "白板演練",
    "behavioral interview": "行為面試",
    "STAR-L": "STAR-L（情境、任務、行動、結果、學習）",
    
    # General
    "production": "生產環境",
    "production-grade": "生產級",
    "retrieval": "檢索",
    "generation": "生成",
    "latency": "延遲",
    "throughput": "吞吐量",
    "caching": "快取",
    "cache": "快取",
    "costs": "成本",
    "SLA": "服務等級協議",
}

def translate_file(content, filepath):
    """Translate English content to Traditional Chinese"""
    lines = content.split('\n')
    translated_lines = []
    
    for line in lines:
        # Skip code blocks, mermaid diagrams, tables
        if line.startswith('```') or line.startswith('│') or line.startswith('|'):
            translated_lines.append(line)
            continue
        
        # Skip if line is mostly code/config
        if re.match(r'^\s*[\$\#\>\:]', line):
            translated_lines.append(line)
            continue
        
        # Skip URLs
        if re.match(r'^\s*https?://', line):
            translated_lines.append(line)
            continue
        
        # Translate the line
        for en, zh in GLOSSARY.items():
            # Only translate complete terms (with word boundaries)
            pattern = r'\b' + re.escape(en) + r'\b'
            line = re.sub(pattern, zh, line)
        
        translated_lines.append(line)
    
    return '\n'.join(translated_lines)

if __name__ == '__main__':
    import sys
    filepath = sys.argv[1]
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    translated = translate_file(content, filepath)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(translated)
    print(f"Translated: {filepath}")
