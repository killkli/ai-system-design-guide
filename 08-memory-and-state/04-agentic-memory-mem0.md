# 使用 Mem0 的代理記憶

**Mem0** 是用於 AI 代理的生產級開源記憶層。它提供了用於持久化、檢索與管理智慧體跨工作階段記憶的統一 API，解決了「個性化 AI」的核心挑戰：讓模型記住個體偏好、互動歷史與領域特定知識。

## 目錄

- [核心概念](#core-concepts)
- [記憶層級](#memory-tiers)
- [API 與 SDK](#api)
- [自訂與擴展](#customization)
- [面試問題](#interview-questions)
- [參考文獻](#references)

---

## 核心概念

Mem0 解決了三個長期挑戰：
1. **跨工作階段持久性**：使用者上次對話中提到的偏好，會在下一個工作階段記住。
2. **動態知識更新**：使用者偏好會隨時間改變，Mem0 處理更新與衝突解決。
3. **語境理解**：從對話中推斷意圖，而非僅依賴明確的使用者陳述。

---

## 記憶層級

Mem0 實現四層記憶：

| 層級 | 內容 | 存取頻率 |
|------|------|---------|
| **使用者事實** | 偏好、興趣、任務相關細節 | 高 |
| **互動歷史** | 過去對話的濃縮摘要 | 中 |
| **領域知識** | 專業術語、產業背景 | 低 |
| **原始對話** | 完整對話日誌（用於分析） | 極低 |

---

## API 與 SDK

### 儲存記憶
```python
import mem0

client = mem0.Client()

# 儲存使用者事實
result = client.add(
    messages=[
        {"role": "user", "content": "我喜歡簡潔的回覆"},
        {"role": "assistant", "content": "好的，我會保持簡潔"}
    ],
    user_id="user_123",
    metadata={"category": "preference"}
)
```

### 檢索記憶
```python
# 為代理檢索相關記憶
memories = client.search(
    query="使用者對回覆風格有什麼偏好？",
    user_id="user_123",
    limit=5
)
```

### 更新與刪除
```python
# 更新已改變的事實
client.update(memory_id="...", data={"text": "新的偏好內容"})

# 尊重「被遺忘權」
client.delete(memory_id="...")
```

---

## 自訂與擴展

### 自訂記憶萃取
```python
from mem0.llms import CustomLLM

class ClinicalLLM(CustomLLM):
    """用於醫療領域的自訂 LLM"""
    def extract_medical_facts(self, conversation):
        # 自訂萃取邏輯
        pass
```

### 與現有系統整合
Mem0 提供與 LangChain、LlamaIndex 與 CrewAI 的一級整合。
```python
from llama_index.core import VectorStoreIndex
from mem0.proxy import Mem0VectorStore

# 使用 Mem0 作為記憶後端的 LlamaIndex
vector_store = Mem0VectorStore(config={"user_id": "user_123"})
```

---

## 面試問題

### Q：Mem0 與基本向量 RAG 的主要區別是什麼？

**理想回答：**
基本向量 RAG 是**被動的**——它儲存文件並檢索相似的文件。Mem0 是**主動的**——它從互動中**推斷並萃取**結構化事實，並主動**更新**它們。向量 RAG 不理解「我的偏好改了」，而 Mem0 有**衝突解決機制**來處理更新。Mem0 還原生支援**使用者命名空間**，使跨工作階段的個人化更加安全，而非依賴元資料過濾。

### Q：Mem0 的潛在缺點是什麼？

**理想回答：**
Mem0 的主要挑戰是：
1. **供應商鎖定**：托管版本將資料保留在他們的基礎設施上；對於嚴格的資料主權要求，這可能是阻礙。
2. **每筆記憶 8K 字元上限**：不適合儲存完整的文件或長篇內容。
3. **萃取延遲**：每次互動後的萃取步驟增加了延遲，儘管 Mem0 提供了非同步背景萃取。
4. **無正式信念狀態模型**：記憶只能是覆寫或附加，沒有內建的「活躍/已取代/已撤回」信念追蹤。

---

## 參考文獻

- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [Mem0 文件](https://docs.mem0.ai)
- [Mem0 部落格](https://mem0.ai/blog)

---

*下一篇：[Zep 與時間圖譜](05-zep-and-temporal-graphs.md)*
