# Zep 與時間圖譜

**Zep** 是一個開源長期記憶服務，專為 AI 代理與 RAG 設計。其核心創新是**時間知識圖譜**：每條資訊都有時間邊界（valid_from / valid_to），使系統能夠回答「我們在 3 月 12 日相信什麼？」以及「現在什麼是真的？」

## 目錄

- [時間圖譜差異](#why-temporal)
- [資料模型](#data-model)
- [雙時間查詢](#bi-temporal)
- [與競爭產品的比較](#comparison)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 時間圖譜差異

大多數記憶系統儲存**目前的**事實。Zep 儲存**具有歷史的事實**。

範例：
```
使用者 Alice 在 2025 年 1 月 1 日至 3 月 15 日期間任職於 Acme Corp。
她在 2025 年 3 月 20 日開始在 Beta Inc 工作。
```

Zep 可以回答：
- 「Alice 2 月在哪裡工作？」→ Acme Corp（準確）
- 「Alice 現在在哪裡工作？」→ Beta Inc（準確）
- 「Alice 什麼時候離開 Acme？」→ 3 月 15 日左右

---

## 資料模型

每個 Zep 節點有三個時間屬性：

| 屬性 | 意義 |
|------|------|
| `valid_from` | 事實開始有效的時間 |
| `valid_to` | 事實停止有效的時間（null = 目前為真） |
| `invalid_at` | 事實被*知道*為過時的時間 |

### 三元組結構
```
(subject) --[predicate]--> (object)
```
範例：
```
Alice --[WORKS_AT]--> Acme Corp
  valid_from: 2025-01-01
  valid_to: 2025-03-15
  invalid_at: 2025-03-20
```

---

## 雙時間查詢

Zep 的查詢 API 支援雙時間語意：

```python
# 語意時間查詢：「事實在歷史上什麼時候為真？」
result = zep.query(
    "Alice 在什麼時候任職於 Acme？",
    temporal_query={"valid_at": "2025-02-15"}
)

# 登錄時間查詢：「我們什麼時候知道這個事實？」
result = zep.query(
    "我們什麼時候得知 Alice 任職於 Acme？",
    temporal_query={"invalid_at": None}
)
```

---

## 與競爭產品的比較

| 維度 | Zep | Mem0 | Letta |
|------|-----|------|-------|
| **時間模型** | 雙時間（valid_from + invalid_at） | 單一時間（timestamp） | 事件 sourcing |
| **圖譜原生** | 是 | 混合（圖+向量） | 否 |
| **開源** | 是 | 部分 | 是 |
| **個人化排名** | DPR-style | BM25 + 興趣排名 | 基於重要性 |
| **代理框架整合** | LangChain、LlamaIndex | LangChain、OpenAI | LangChain、AutoGen |

---

## 面試問題

### Q：為什麼「雙時間」查詢對 AI 代理很重要？

**理想回答：**
因為代理需要回答兩種問題：
1. **語意問題**：「使用者在歷史上的哪個時間點相信 X？」——用於理解過去決策的上下文。
2. **登錄問題**：「我們的系統什麼時候知道 X 可能已過時？」——用於觸發資料重新整理或驗證。

大多數系統只有語意時間（時間戳）。Zep 的雙時間模型讓代理不僅知道「什麼是真的」，還知道「什麼時候改變的」，從而實現更聰明的**主動重新確認**——如果一個事實在 30 天前被 invalid_at，而今天我們需要它，這是一個信號，應該再次驗證而非直接使用。

### Q：Zep 與 GraphRAG 有何不同？

**理想回答：**
GraphRAG 使用圖形來建立**文件之間的關係結構**，以改善 RAG 的檢索。Zep 使用圖形來建立**實體之間的時間關係**。GraphRAG 的節點是文件；Zep 的節點是具有生命週期的事實。另一個關鍵差異：GraphRAG 主要用於**資訊檢索**（回答問題），而 Zep 主要用於**代理記憶**（維護持續的、世界觀的代理視角）。

---

## 參考文獻

- [Zep GitHub](https://github.com/getzep/zep)
- [Zep 文件](https://docs.getzep.com)
- [Zep 部落格](https://getzep.com/blog)
- [Graphiti：Zep 的圖形時間索引](https://github.com/getzep/graphiti)

---

*下一篇：[向量資料庫選型](06-vector-database-selection.md)*
