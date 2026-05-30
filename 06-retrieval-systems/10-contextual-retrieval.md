# 上下文檢索

上下文檢索是一種攝取時間（ingestion-time）技術，用於解決 RAG 失敗的首要原因：**文本區塊在脫離原始文件後失去意義**。此技術由 Anthropic 在 2024 年末首創，現已成為高精度檢索的生產標準。Anthropic 自身的測量顯示，僅使用混合搜索即可減少 49% 的檢索失敗，搭配重新排序（reranking）更可減少 67%。

## 目錄

- [問題所在：上下文稀釋](#context-dilution)
- [上下文檢索如何運作](#how-it-works)
- [上下文嵌入](#contextual-embeddings)
- [上下文 BM25](#contextual-bm25)
- [完整流程：混合搜索 + 重新排序](#full-pipeline)
- [實作模式](#implementation)
- [成本考量](#cost)
- [上下文檢索與其他方法的比較](#comparison)
- [生產架構](#production)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 問題所在：上下文稀釋

當我們對文件進行 RAG 區塊化時，個別區塊會失去周圍的上下文，而這些上下文正是赋予它們意義的元素。

**上下文稀釋範例：**

```
原始文件："Acme Corp Q3 2025 財務報告"
  第 4 節：產品定價

  「Standard 方案每月費用 $200。Enterprise
   方案包含 SSO 與稽核日誌，每月 $800。」

-------- 區塊化後 --------

區塊 17：「每月費用 $200。」
區塊 18：「Enterprise 方案包含 SSO 與稽核日誌，
           每月 $800。」
```

**區塊 17 的問題**：當使用者搜尋「Acme Standard 方案多少錢？」時，很可能會錯過這個區塊，因為它沒有提及「Acme」、「Standard」或「方案」。「每月費用 $200」的嵌入向量在語義上與查詢相去甚遠。

**洞見**：Anthropic 的研究顯示，傳統區塊化在前 20 名檢索區塊中造成 **5.7% 的檢索失敗率**。這意味著大約每 18 次查詢就有 1 次無法檢索到存在的相關資訊。

---

## 上下文檢索如何運作

核心概念很簡單：**在嵌入區塊之前，先附加一個簡短的上下文字串，說明該區塊在完整文件中的角色**。

```
┌──────────────────────────────────────────────────┐
│              傳統區塊化                           │
│                                                  │
│  文件 ──► 切割 ──► 區塊 ──► 嵌入 ──► 資料庫        │
│                                                  │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│              上下文檢索                                      │
│                                                              │
│  文件 ──► 切割 ──► 區塊 ──┐                                   │
│                           ├──► 上下文化 ──►                   │
│  文件（完整） ────────────┘     （每區塊一次 LLM 呼叫）        │
│                                                              │
│  ──► 上下文區塊 ──► 嵌入 ──► 資料庫                           │
│                            + BM25 索引                        │
└──────────────────────────────────────────────────────────────┘
```

**上下文化步驟**會將完整文件 + 個別區塊傳送給 LLM，並使用以下提示：

```
<document>
{{WHOLE_DOCUMENT}}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{{CHUNK_CONTENT}}
</chunk>

Please give a short succinct context to situate this chunk
within the overall document for the purposes of improving
search retrieval of the chunk. Answer only with the succinct
context and nothing else.
```

**區塊 17 的結果**：

```
前置：「每月費用 $200。」

後置：「此區塊來自 Acme Corp Q3 2025 財務報告，
         第 4 節產品定價。描述 Standard 方案的費用。
         每月費用 $200。」
```

現在此區塊的嵌入向量包含「Acme」、「Standard 方案」和「產品定價」——全部是使用者自然會搜尋的詞彙。

---

## 上下文嵌入

上下文嵌入是第一個子技術：嵌入經過上下文化的區塊，而非原始區塊。

### 如何改善檢索

| 情境 | 原始區塊嵌入 | 上下文嵌入 |
|------|-------------|-------------|
| 使用者詢問「Acme 定價」 | 錯過「每月費用 $200」 | 匹配「Acme...Standard 方案...費用 $200」 |
| 使用者詢問「SSO 功能」 | 匹配「SSO 與稽核日誌」 | 透過附加的「Enterprise 方案」上下文匹配 |
| 使用者詢問「Q3 財務」 | 無匹配（未提及 Q3） | 透過附加的「Q3 2025 財務報告」匹配 |

**效能**：僅使用上下文嵌入即可將前 20 名檢索失敗率從 **5.7% 降至 3.7%**——減少 **35%** 的檢索失敗。

### 向量空間的轉變

```
                    ▲ 維度 2
                    │
                    │    ● 「Acme 定價」（查詢）
                    │         \
                    │          \  接近（上下文化）
                    │           \
                    │            ● 上下文化區塊
                    │
                    │                          ● 原始區塊「每月費用 $200」
                    │                            （離查詢很遠）
                    │
                    └─────────────────────────────► 維度 1
```

---

## 上下文 BM25

第二個子技術將相同的上下文化應用於建立**經過豐富化的區塊上的 BM25 關鍵字索引**。

### 為何 BM25 仍然重要

密集嵌入在語義相似性方面表現優異，但在以下情況表現不佳：
- **精確詞彙**：產品 ID、版本號碼、縮寫
- **罕見詞彙**：嵌入模型代表性不足的領域特定術語
- **專有名詞**：公司名稱、人名、地點

**範例**：使用者搜尋「Widget-X 定價」時，在原始區塊「每月費用 $200」上會得到零 BM25 匹配，因為「Widget-X」從未出現。使用上下文 BM25 時，附加的上下文會將「Widget-X」作為關鍵字包含，使 BM25 匹配成為可能。

### 效能提升（累積）

| 設定 | 失敗率 | 與基準相比的減少幅度 |
|------|--------|---------------------|
| 傳統嵌入（基準） | 5.7% | -- |
| 僅使用上下文嵌入 | 3.7% | 35% |
| 上下文嵌入 + 上下文 BM25 | 2.9% | **49%** |
| 上下文嵌入 + 上下文 BM25 + 重新排序 | 1.9% | **67%** |

**要點**：上下文嵌入 + 上下文 BM25 的組合是對 RAG 流程最高槓桿的單一改變。在此基礎上加入重新排序器可達到減少 67% 的失敗率。

---

## 完整流程：混合搜索 + 重新排序

生產級上下文檢索流程有四個階段：

```
┌─────────────────────────────────────────────────────────────────┐
│                     攝取流程                                      │
│                                                                 │
│  1. 區塊化文件（遞歸式，300-500 tokens）                          │
│  2. 對每個區塊：                                                  │
│     a. 傳送（full_doc + chunk）至 LLM                             │
│     b. 取得上下文字串（50-100 tokens）                            │
│     c. 將上下文附加至區塊前方                                      │
│  3. 嵌入上下文化區塊 ──► 向量資料庫                                │
│  4. 索引上下文化區塊 ──► BM25 索引                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     查詢流程                                      │
│                                                                 │
│  使用者查詢                                                       │
│      │                                                          │
│      ├──► 向量搜索（前 50 名） ──┐                               │
│      │                            ├──► RRF 融合（前 25 名）       │
│      └──► BM25 搜索（前 50 名） ──┘         │                    │
│                                             ▼                    │
│                                      重新排序器（前 5 名）        │
│                                             │                    │
│                                             ▼                    │
│                                     LLM 生成                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 用於結合結果的倒數排名融合（RRF）

與標準混合搜索相同的 RRF 技術同樣適用於此：

```
RRF_Score(doc) = sum( 1 / (k + rank_in_list) )
                 for each list where doc appears

k = 60（標準平滑常數）
```

---

## 實作模式

### 模式 1：基本上下文檢索（Python）

```python
import anthropic
from typing import List

client = anthropic.Anthropic()

CONTEXT_PROMPT = """<document>
{document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>

Please give a short succinct context to situate this chunk
within the overall document for the purposes of improving
search retrieval of the chunk. Answer only with the succinct
context and nothing else."""


def contextualize_chunk(
    full_document: str,
    chunk: str,
    model: str = "claude-sonnet-4-20250514"
) -> str:
    """Generate context for a single chunk."""
    response = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": CONTEXT_PROMPT.format(
                document=full_document,
                chunk=chunk
            )
        }]
    )
    context = response.content[0].text
    return f"{context}\n\n{chunk}"


def process_document(document: str, chunks: List[str]) -> List[str]:
    """Contextualize all chunks in a document."""
    contextualized = []
    for chunk in chunks:
        ctx_chunk = contextualize_chunk(document, chunk)
        contextualized.append(ctx_chunk)
    return contextualized
```

### 模式 2：使用提示快取優化成本

最大的成本驅動因素是每次處理區塊時都傳送完整文件。**提示快取**解決了這個問題：

```python
def contextualize_with_caching(
    full_document: str,
    chunks: List[str],
    model: str = "claude-sonnet-4-20250514"
) -> List[str]:
    """
    Use prompt caching so the full document is only
    processed once across all chunks.
    """
    results = []

    for chunk in chunks:
        response = client.messages.create(
            model=model,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"<document>\n{full_document}\n</document>",
                        "cache_control": {"type": "ephemeral"}
                    },
                    {
                        "type": "text",
                        "text": (
                            f"<chunk>\n{chunk}\n</chunk>\n\n"
                            "Please give a short succinct context to "
                            "situate this chunk within the overall "
                            "document for the purposes of improving "
                            "search retrieval of the chunk. Answer "
                            "only with the succinct context and "
                            "nothing else."
                        )
                    }
                ]
            }]
        )
        context = response.content[0].text
        results.append(f"{context}\n\n{chunk}")

    return results
```

**提示快取的成本影響**：對於一個分割成 30 個區塊的 10,000 token 文件，提示快取可將上下文化成本降低最高 **90%**，因為文件前置內容在第一次呼叫後就會被快取。

### 模式 3：上下文區塊標題（輕量級替代方案）

如果基於 LLM 的上下文化太昂貴，可以使用**上下文區塊標題（CCH）**作為確定性的替代方案：

```python
def add_chunk_headers(
    document_title: str,
    section_hierarchy: List[str],
    chunk: str
) -> str:
    """
    Prepend document and section metadata to the chunk.
    No LLM call required -- purely structural.
    """
    header_parts = [f"Document: {document_title}"]

    for i, section in enumerate(section_hierarchy):
        prefix = "  " * i
        header_parts.append(f"{prefix}Section: {section}")

    header = "\n".join(header_parts)
    return f"{header}\n\n{chunk}"


# Example usage:
contextualized = add_chunk_headers(
    document_title="Acme Corp Q3 2025 Financial Report",
    section_hierarchy=["Finance", "Product Pricing", "Standard Plan"],
    chunk="It costs $200/month."
)

# Result:
# Document: Acme Corp Q3 2025 Financial Report
#   Section: Finance
#     Section: Product Pricing
#       Section: Standard Plan
#
# It costs $200/month.
```

**何時使用 CCH 與 LLM 上下文化：**

| 因素 | 區塊標題（CCH） | LLM 上下文化 |
|------|---------------|-------------|
| **成本** | 免費（無 LLM 呼叫） | 每百萬 tokens $1-5 |
| **品質** | 結構化文件佳 | 所有文件皆優秀 |
| **速度** | 瞬間 | 每區塊 50-200ms |
| **最適合** | 標題清晰的 Markdown、HTML、PDF | 非結構化文字、法律、醫療 |

---

## 成本考量

### 上下文化成本

對於 10,000 個區塊（每個平均 400 tokens）的知識庫：

| 模型 | 每區塊成本 | 總成本 | 品質 |
|------|-----------|--------|------|
| Claude Haiku（快速、便宜） | ~$0.0003 | ~$3 | 良好 |
| Claude Sonnet（平衡） | ~$0.002 | ~$20 | 非常好 |
| Claude Opus（最高品質） | ~$0.01 | ~$100 | 極佳 |

**最佳實踐**：使用 Haiku（或其他快速、便宜的模型）進行上下文化。上下文字串很短且是事實性的，不需要前沿模型。搭配提示快取可節省約 90% 的文件主體成本，該主體會在每次呼叫中重複傳送。

### 何時使用上下文檢索

**使用的情況：**
- 您的語料庫有碎片化文件，區塊在獨立存在時會失去意義
- 您有嵌入模型難以處理的領域特定術語
- 您的檢索失敗率超過 3-5%
- 您可以負擔一次性攝取成本

**跳過的情況：**
- 您的區塊已經是自包含的（例如：FAQ 配對、產品描述）
- 您的語料庫很小（< 100 個區塊）——直接使用長上下文即可
- 您需要即時攝取（每份文件 < 1 秒）且無法批次處理

---

## 上下文檢索與其他方法的比較

| 方法 | 運作方式 | 檢索改善 | 成本 | 複雜度 |
|------|---------|---------|------|--------|
| **朴素區塊化** | 固定大小切割，嵌入原始內容 | 基準 | 無 | 低 |
| **區塊標題（CCH）** | 附加文件/章節標題 | 10-20% | 無 | 低 |
| **上下文檢索** | 每區塊 LLM 生成上下文 | 35-49% | 每 10k 區塊 $3-20 | 中 |
| **上下文 + 重新排序** | 上述 + 交叉編碼器重新排序 | 67% | 每 10k 區塊 $5-30 | 中高 |
| **HyDE** | 查詢時生成假設文件 | 20-40% | 每查詢 LLM 成本 | 中 |
| **父子區塊化** | 嵌入子區塊，檢索父區塊 | 15-30% | 無 | 中 |

**關鍵區別**：上下文檢索是一種**攝取時間**技術（付費一次），而 HyDE 是一種**查詢時間**技術（每次查詢付費）。對於高流量系統，上下文檢索的分攤效果要好得多。

### 上下文檢索與晚期區塊化（Late Chunking）的比較

**晚期區塊化**（Jina，2024）是一種相關但不同的方法：

```
上下文檢索：
  區塊 ──► LLM 新增上下文 ──► 嵌入豐富化的區塊

晚期區塊化：
  完整文件 ──► 長上下文嵌入模型 ──► Token 嵌入
  ──► 然後對 token 嵌入進行區塊化（保留上下文）
```

晚期區塊化需要長上下文嵌入模型（例如 Jina v3），完全不需要 LLM 呼叫。它透過嵌入模型的注意力機制而非明確的文字附加來保留上下文。權衡是晚期區塊化對 BM25 搜索沒有幫助，僅對密集檢索有幫助。

---

## 生產架構

### 參考架構：規模化上下文 RAG

```
┌─────────────────────────────────────────────────────────────────────┐
│                     攝取服務                                         │
│                                                                     │
│  文件儲存 ──► 區塊化器 ──► 上下文化佇列                               │
│                       │              │                               │
│                       │         ┌────┴────┐                          │
│                       │         │ 工作者   │ （N 個平行 LLM 呼叫）     │
│                       │         │ + 快取   │                          │
│                       │         └────┬────┘                          │
│                       │              │                               │
│                       ▼              ▼                               │
│                  原始區塊         上下文化區塊                          │
│                       │              │                               │
│                       │         ┌────┴────┐                          │
│                       │         │ 嵌入 +  │                          │
│                       │         │ BM25    │                          │
│                       │         └────┬────┘                          │
│                       │              │                               │
│                       ▼              ▼                               │
│                  中繼資料資料庫      向量資料庫 + BM25 索引             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     查詢服務                                         │
│                                                                     │
│  查詢 ──► [向量搜索] + [BM25 搜索]                                   │
│                    │               │                                 │
│                    └───── RRF ─────┘                                 │
│                           │                                          │
│                      前 25 名區塊                                    │
│                           │                                          │
│                      重新排序器（Cohere、交叉編碼器）                  │
│                           │                                          │
│                      前 5 名區塊                                      │
│                           │                                          │
│                      LLM 生成                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 擴展考量

| 考量 | 解決方案 |
|------|---------|
| **攝取吞吐量** | 平行化 LLM 呼叫（50-100 個並行）搭配非同步工作者 |
| **文件更新** | 僅重新上下文化已變更的區塊；單獨儲存原始內容與上下文 |
| **規模化成本** | 使用 Haiku + 提示快取；按大小批次處理文件 |
| **品質監控** | 抽樣 1% 的區塊進行人工評估上下文品質 |
| **索引一致性** | 每份文件原子性更新向量資料庫 + BM25 索引 |

---

## 面試問題

### Q：解釋 Anthropic 的上下文檢索。何時使用，何時跳過？

**強而有力的回答：**
上下文檢索解決了 RAG 中的「上下文稀釋」問題。當文件被區塊化時，個別區塊會失去周圍的上下文，而這些上下文正是赋予它們意義的元素——一個說「費用 $200」的區塊，如果不知道*什麼*費用 $200，就毫無用處。該技術在攝取時使用 LLM 為每個區塊生成一個簡短的上下文字串（50-100 tokens），說明該區塊在文件中的角色。此上下文在嵌入和 BM25 索引之前附加到區塊前方。

關鍵結果：僅使用上下文嵌入即可減少 35% 的檢索失敗。加入上下文 BM25 可達到 49% 的減少。加上重新排序器可達到 67% 的減少。

我會在區塊經常在獨立存在時失去意義的情況下使用它——法律合約、財務報告、技術手冊。我會在區塊已經是自包含的（FAQ、產品卡）或語料庫小到足以使用長上下文 RAG 時跳過它。

### Q：一個包含 50,000 份文件的知識庫需要上下文檢索。您如何管理攝取成本？

**強而有力的回答：**
三種策略：
1. **模型選擇**：使用小型、快速模型（Claude Haiku 等）進行上下文化。輸出是短的事實性文字，不是創意寫作——前沿模型增加成本而不增加品質。
2. **提示快取**：在所有區塊上下文化呼叫之間快取完整文件文字。對於一個包含 30 個區塊的 10,000 token 文件，這可將輸入 token 成本降低約 90%。
3. **分層方法**：並非每份文件都需要 LLM 上下文化。對於結構良好的文件（帶有標題的 Markdown、HTML），使用確定性的上下文區塊標題（附加文件標題 + 章節層級結構），這是免費的。將 LLM 上下文化保留給非結構化或模糊的文件。

### Q：上下文檢索與 HyDE 在改善檢索品質方面如何比較？

**強而有力的回答：**
它們解決同一問題的不同面向。上下文檢索在**文件**的攝取時間進行豐富化（付費一次），而 HyDE 在**查詢**的搜尋時間進行豐富化（每次查詢付費）。對於每天處理 10,000 次查詢、語料庫有 50,000 個區塊的系統，上下文檢索要便宜得多，因為攝取成本被分攤了。HyDE 也有幻覺風險——假設的文件可能會引入錯誤的資料。在實踐中，最強大的系統兩者都用：攝取時使用上下文檢索豐富化文件，複雜查詢需要查詢端協助時使用 HyDE（或多重查詢擴展）。

---

## 參考文獻

- Anthropic. "Contextual Retrieval" (September 2024)
- Jina AI. "Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models" (2024)
- Voyage AI. "voyage-context-3: Contextualized Chunk Embeddings" (2025)
- NirDiamant. "RAG Techniques: Contextual Chunk Headers" (GitHub, 2024)

---

*前一篇：[進階檢索模式](09-advanced-retrieval-patterns.md) | 下一篇：[晚期互動與 ColBERT](11-late-interaction-colbert.md)*