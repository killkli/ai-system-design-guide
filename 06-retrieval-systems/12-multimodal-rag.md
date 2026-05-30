# 多模態 RAG

多模態 RAG 將檢索增強生成從純文字擴展到處理圖像、表格、圖表、音訊和混合版面文件。生產系統現在常見攝取包含圖表、簡報、掃描發票和研究論文的 PDF，其中視覺版面*就是*意義所在。三種架構占主導地位：標題與索引、統一視覺-文字嵌入（Cohere Embed v4、Voyage-Multimodal-3.5、Gemini Embedding 001），以及以頁面作為影像搭配晚期互動（ColPali、ColQwen2.5、ColNomic）。

## 目錄

- [為何純文字 RAG 失敗](#為何純文字-rag-失敗)
- [架構模式](#架構模式)
- [多模態嵌入策略](#多模態嵌入策略)
- [用於文件理解的視覺語言模型](#用於文件理解的視覺語言模型)
- [ColPali 與基於視覺的檢索](#colpali-與基於視覺的檢索)
- [表格萃取與結構化資料檢索](#表格萃取與結構化資料檢索)
- [圖表與圖表理解](#圖表與圖表理解)
- [生產架構](#生產架構)
- [實作範例](#實作範例)
- [系統設計面試角度](#系統設計面試角度)
- [參考文獻](#參考文獻)

---

## 為何純文字 RAG 失敗

傳統 RAG 管道將文件解析為文字區塊、嵌入它們，並針對文字查詢進行檢索。這在真實世界文件上會失敗：

| 文件元素 | 純文字 RAG 行為 | 實際遺失的資訊 |
|---------|----------------|----------------|
| **長條圖** | 只萃取軸標籤 | 趨勢、比較、數值幅度 |
| **架構圖** | 完全漏掉 | 元件關係、資料流向 |
| **表格** | 扁平化列失去結構 | 列-欄關聯、標題 |
| **資訊圖** | 擷取零散文字片段 | 視覺層次、空間分組 |
| **附標題的照片** | 取得標題，失去圖片 | 視覺證據、空間上下文 |

**現實**：企業文件有 40-60% 是非文字內容。財務報告的價值在於圖表。醫學論文的關鍵發現在於圖形。忽略視覺內容意味著忽略大部分知識。

---

## 架構模式

多模態 RAG 有三種主要模式，各有獨特的取捨：

### 模式 1：統一嵌入空間

```
                     共享向量空間
                    +-------------------+
  文字  --> 編碼器 |  [0.2, 0.8, ...] |
  圖片  --> 編碼器 |  [0.3, 0.7, ...] |  --> 單一索引 --> 檢索
  表格  --> 編碼器 |  [0.1, 0.9, ...] |
                    +-------------------+

  查詢「顯示營收趨勢」 --> 編碼 --> 在所有模態中找最近鄰
```

- **如何**：使用 CLIP 或 SigLIP 等模型將文字和圖片投影到相同的向量空間。
- **優點**：單一索引、單一查詢、簡單的檢索邏輯。
- **缺點**：嵌入品質因模態而異；表格需要序列化。

### 模式 2：模態特定檢索與融合

```
  查詢 --> +----> 文字索引    --> 前 K 名文字區塊
            |
            +----> 圖片索引   --> 前 K 名圖片
            |
            +----> 表格索引   --> 前 K 名表格
            |
            v
        融合 / 重新排序層 --> 組合前 K 名 --> VLM 生成器
```

- **如何**：每個模態使用獨立嵌入和索引。重新排序器或倒數排名融合（RRF）合併結果。
- **優點**：每個模態使用最佳的嵌入；可以獨立調整每個檢索器。
- **缺點**：更多的基礎設施複雜度；融合邏輯不簡單。

### 模式 3：視覺優先（頁面作為影像）

```
  文件頁面 --> 截圖/渲染 --> 視覺編碼器 --> 多向量索引
                                              |
  查詢 ---------> 文字編碼器 ------------+---> 晚期互動評分
                                                    --> 檢索前幾名頁面
```

- **如何**：將每個文件頁面視為單一影像。使用視覺語言模型（例如 ColPali）建立區塊層級嵌入。透過晚期互動（MaxSim）評分。
- **優點**：不需要 OCR，不需要版面解析，不需要表格萃取管線。端到端可訓練。
- **缺點**：索引時的計算量更高；失去細粒度文字搜尋。

**建議**：模式 3（視覺優先）在文件密集的使用案例中正在快速獲得關注。當你需要精確文字搜尋以及視覺檢索時，模式 2 仍然是生產主力。

---

## 多模態嵌入策略

### CLIP（對比語言-影像預訓練）

將文字和圖片映射到共享 512/768 維空間的原始雙編碼器。

- **優勢**：龐大生態系統、易於理解、許多微調變體。
- **劣勢**：在文件風格圖片（圖表、表格）上比自然照片弱。對比損失需要大批量。

### SigLIP / SigLIP 2

用 sigmoind 損失取代 CLIP 的 softmax 交叉熵，允許每個影像-文字配對獨立評估。

- **SigLIP 2（2025）**：新增標題解碼器、自蒸餾和遮罩預測。在 109 種語言的 100 億+ 圖片上訓練。
- **關鍵優勢**：在小批量（4-8k）時優於 CLIP，提供更密集、更強健的特性。
- **生產使用**：挪威國家圖書館、電子商務視覺搜尋、AI 藝術策展。

### RAG 用比較

| 模型 | 最適合 | 嵌入維度 | 文件品質 | 自然圖片品質 |
|------|--------|----------|----------|--------------|
| CLIP ViT-L/14 | 通用 | 768 | 中 | 高 |
| SigLIP 2 So400m | 多語言文件 | 1152 | 高 | 高 |
| Nomic Embed Vision | 文字密集文件 | 768 | 高 | 中 |
| Voyage Multimodal 3 | 混合文件 | 1024 | 高 | 高 |

### 嵌入策略決策

```
你的內容主要是自然圖片（照片、產品）嗎？
  是 --> CLIP 或 SigLIP 在你的領域上微調
  否
    v
你的內容是文件頁面（PDF、簡報、報告）嗎？
  是 --> ColPali / ColQwen（視覺優先，不需要 OCR）
  否
    v
是文字、圖片和結構化資料的混合嗎？
  是 --> 模態特定編碼器 + 融合（模式 2）
```

---

## 用於文件理解的視覺語言模型

VLMs 在多模態 RAG 中扮演兩個角色：（1）作為**生成器**，從檢索到的多模態上下文合成答案，以及（2）作為**索引引擎**，在攝取時萃取出結構化資訊。

### VLM 能力比較

| 能力 | Claude Opus 4.7 / Sonnet 4.6 | GPT-5.5 | Gemini 3.1 Pro |
|------|------------------------------|---------|----------------|
| **圖表閱讀** | 優秀 | 優秀 | 優秀 |
| **表格萃取** | 優秀 | 良好 | 優秀 |
| **圖表理解** | 優秀 | 良好 | 優秀 |
| **手寫 OCR** | 良好 | 良好 | 良好 |
| **多頁推理** | 優秀（Sonnet 4.6 上 1M ctx） | 優秀（1M ctx） | 優秀（1M ctx） |
| **結構化輸出** | 原生 JSON 模式 | 原生 JSON 模式 | 原生 JSON 模式 |

### VLM 增强攝取管道

```
  原始 PDF
    |
    v
  頁面渲染器（pdf2image，300 DPI）
    |
    v
  VLM 萃取 Pass：
    +-- 「將所有表格萃取為 markdown」
    +-- 「描述此圖表：軸、趨勢、關鍵資料點」
    +-- 「摘要此圖表：元件和關係」
    |
    v
  結構化輸出（JSON）
    |
    +---> 文字區塊     --> 文字嵌入索引
    +---> 表格 markdown  --> 文字嵌入索引（附元資料：「type=table」）
    +---> 圖表摘要 --> 文字嵌入索引（附元資料：「type=chart」）
    +---> 頁面圖片     --> 圖片嵌入索引（CLIP/SigLIP）
```

這種「先描述後嵌入」的方法將視覺內容轉換為可搜尋文字，同時保留原始圖片用於生成步驟。

---

## ColPali 與基於視覺的檢索

ColPali 代表了一種典範轉移：與其建構複雜的 OCR + 版面 + 表格萃取管道，不如將每個文件頁面視為單一影像，讓視覺語言模型處理一切。

### ColPali 如何運作

```
  文件頁面影像
        |
        v
  SigLIP 視覺編碼器（So400m）
        |
  將影像分割成區塊（例如 32x32 網格 = 1024 個區塊）
        |
        v
  Gemma 2B 語言模型（情境化區塊嵌入）
        |
        v
  線性投影 --> 128 維區塊嵌入
        |
        v
  結果：每頁 1024 個 128 維向量
        |
        v
  儲存在多向量索引中

  在查詢時：
  查詢 --> 分詞 --> 嵌入 --> 128 維 token 嵌入
        |
        v
  晚期互動（MaxSim）：
    分數 = 對所有查詢 token 求和 of 與任何區塊的最大相似度
```

### ColPali 與傳統管道比較

| 面向 | 傳統管道 | ColPali |
|------|----------|---------|
| **OCR** | 需要（Tesseract、Azure OCR） | 不需要 |
| **版面偵測** | 需要（Detectron2、LayoutLM） | 不需要 |
| **表格解析器** | 需要（Camelot、Tabula） | 不需要 |
| **圖表萃取器** | 需要（ChartOCR） | 不需要 |
| **索引速度** | 慢（多階段） | 快（單一 forward pass） |
| **檢索品質** | 文字上高，視覺上差 | 所有模態都高 |
| **儲存** | 文字索引（小） | 多向量索引（大） |

### ColPali 家族

- **ColPali（v1）**：PaliGemma-3B 主幹。原創。
- **ColQwen 2.5**：Qwen2-VL 主幹。更好的多語言支援，亞洲語言文件上改進。
- **ColSmol**：邊緣部署的較小變體。約 10 億參數。

### ViDoRe 基準測試結果

ColPali 在視覺複雜的基準測試（如 InfographicVQA、ArxivQA 和 TabFQuAD）上表現出色，分別測試資訊圖、圖形和表格。它在以文字為中心的文件上甚至超越傳統文字管道。

---

## 表格萃取與結構化資料檢索

表格是傳統 RAG 最困難的模態。逐行扁平化表格會摧毀赋予每個儲存格意義的列-標題關係。

### 策略 1：基於 VLM 的萃取

```python
# 偽代碼：使用 VLM 萃取表格
def extract_tables_from_page(page_image: bytes) -> list[dict]:
    prompt = """
    從此文件頁面萃取所有表格。
    對於每個表格，返回：
    {
      "title": "表格標題或標題",
      "headers": ["col1", "col2", ...],
      "rows": [["val1", "val2", ...], ...],
      "markdown": "| col1 | col2 |\n|---|---|\n| val1 | val2 |"
    }
    返回 JSON 陣列。如果沒有表格，返回 []。
    """
    response = vlm.generate(image=page_image, prompt=prompt)
    return json.loads(response)
```

### 策略 2：專業表格解析器

- **Tabula / Camelot**：基於規則的 PDF 表格萃取。快速但在複雜版面上脆弱。
- **Table Transformer（基於 DETR）**：從影像中偵測表格邊界和儲存格結構。
- **Unstructured.io**：結合啟發式與 ML 模型進行版面感知解析。

### 策略 3：表格感知分塊

```
  原始表格（20 列 x 8 欄）
        |
        v
  將整個單元作為一個單元分塊（不要跨區塊分割表格）
        |
        v
  將完整 markdown 表格作為單一區塊嵌入
        |
        v
  新增元資料：{"type": "table", "page": 14, "caption": "Q3 按地區營收"}
        |
        v
  在生成時間：將完整表格傳給 LLM，而非片段
```

**關鍵原則**：表格必須是原子檢索單元。永遠不要將表格跨區塊邊界分割。

---

## 圖表與圖表理解

### 圖表類型與萃取方法

| 圖表類型 | 萃取什麼 | 最佳方法 |
|---------|---------|----------|
| **長條/線條/圓形** | 資料值、趨勢、比較 | VLM 描述 + 資料表格萃取 |
| **流程圖** | 步驟、決策、連接 | VLM 結構化萃取（節點 + 邊） |
| **架構圖** | 元件、關係、資料流 | VLM 描述 + 實體萃取 |
| **散佈圖** | 相關性、異常值、叢集 | VLM 趨勢描述 + 原始資料（若有） |
| **甘特圖** | 時間表、依賴關係、里程碑 | VLM 結構化萃取 |

### 雙重表示策略

對於每個圖表或圖表，儲存兩種表示：

```
  圖表影像
    |
    +---> (1) 文字描述（用於文字檢索）
    |         「此長條圖顯示 Q3 按地區營收。
    |          北美：420 萬美元，歐洲：310 萬美元，亞太：280 萬美元。
    |          北美較上季成長 15%，而亞太下降 3%。」
    |
    +---> (2) 原始圖片（用於視覺檢索 + 生成上下文）
              使用 CLIP/SigLIP 嵌入儲存，用於基於圖片的查詢
```

這確保圖表可透過文字查詢（「亞太營收是多少？」）和視覺查詢（「顯示我營收圖表」）檢索。

---

## 生產架構

### 完整多模態 RAG 管道

```
  攝取：
  原始文件 --> 文件分類器 --+--> 文字密集  --> 分塊 + 文字嵌入
                                +--> 視覺密集 --> 頁面渲染 + ColPali
                                +--> 混合        --> VLM 萃取 + 混合
                                         |
                                         v
                          [文字索引] [圖片索引] [表格索引]

  檢索：
  查詢 --> 查詢分析器 --+--> 文字：BM25 + 密集搜尋
                             +--> 圖片：CLIP/ColPali 搜尋
                             +--> 表格：元資料過濾的密集搜尋
                                    |
                                    v
                             跨模態重新排序 --> 上下文組裝 --> VLM --> 回應
```

### 規模化考量

| 考量 | 解決方案 |
|------|---------|
| **索引大小** | ColPali 每頁儲存約 1024 個向量。100 萬頁約 10 億個向量。使用量化（二元、PQ）。 |
| **攝取延遲** | VLM 萃取很慢（約每頁 2-5 秒）。使用非同步工作者搭配 GPU 加速。 |
| **查詢延遲** | 多索引扇出增加延遲。使用平行檢索 + 積極的 top-k 修剪。 |
| **成本** | 攝取時的 VLM 呼叫是一次性的。隨查詢量攤銷。每頁預算 $0.01-0.05 的萃取成本。 |
| **儲存** | 將頁面圖片存放在物件儲存（S3）。將嵌入存放在向量資料庫。將文字存放在搜尋索引。 |

---

## 實作範例

### 使用 ColPali + VLM 的端到端多模態 RAG

```python
# 偽代碼：生產多模態 RAG 管道

from colpali_engine import ColPali, ColPaliProcessor
from qdrant_client import QdrantClient
import anthropic

# --- 索引 ---

def index_document(pdf_path: str, collection: str):
    """使用 ColPali 進行視覺檢索和 VLM 萃取進行文字檢索來索引 PDF 文件。"""

    pages = render_pdf_to_images(pdf_path, dpi=300)

    colpali_model = ColPali.from_pretrained("vidore/colpali-v1.3")
    processor = ColPaliProcessor.from_pretrained("vidore/colpali-v1.3")
    vlm_client = anthropic.Anthropic()

    for page_num, page_image in enumerate(pages):
        # 1. 生成 ColPali 多向量嵌入
        inputs = processor(images=[page_image])
        patch_embeddings = colpali_model(**inputs)  # 形狀：[1, 1024, 128]

        # 2. 透過 VLM 萃取結構化內容
        extraction = vlm_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": encode_image(page_image)},
                    {"type": "text", "text": """從此頁面萃取：
                    1. 所有文字內容（保留結構）
                    2. Markdown 格式的表格
                    3. 帶資料點的圖表描述
                    返回帶 keys：text、tables、charts 的 JSON"""}
                ]
            }]
        )

        structured = json.loads(extraction.content[0].text)

        # 3. 儲存在向量資料庫
        qdrant.upsert(collection, points=[
            # ColPali 多向量用於視覺檢索
            PointStruct(
                id=f"{pdf_path}:page:{page_num}:colpali",
                vector={"colpali": patch_embeddings[0].tolist()},
                payload={
                    "source": pdf_path,
                    "page": page_num,
                    "type": "page_image",
                    "text_preview": structured["text"][:500]
                }
            ),
            # 每個萃取元素的文字嵌入
            *create_text_chunks(structured, pdf_path, page_num)
        ])


# --- 檢索 ---

def retrieve(query: str, collection: str, top_k: int = 5):
    """混合檢索：ColPali 視覺 + 文字語義搜尋。"""

    # 透過 ColPali 的視覺檢索
    query_inputs = processor(text=[query])
    query_embeddings = colpali_model(**query_inputs)

    visual_results = qdrant.query(
        collection,
        query_vector=("colpali", query_embeddings[0].tolist()),
        limit=top_k,
        query_filter=Filter(must=[FieldCondition(key="type", match="page_image")])
    )

    # 透過密集嵌入的文字檢索
    text_embedding = text_encoder.encode(query)
    text_results = qdrant.search(
        collection,
        query_vector=("text", text_embedding.tolist()),
        limit=top_k
    )

    # 使用倒數排名融合融合結果
    fused = reciprocal_rank_fusion(visual_results, text_results, k=60)
    return fused[:top_k]


# --- 生成 ---

def generate_answer(query: str, retrieved_context: list) -> str:
    """使用多模態上下文透過 VLM 生成答案。"""

    content_blocks = [{"type": "text", "text": f"問題：{query}\n\n上下文："}]

    for ctx in retrieved_context:
        if ctx.payload["type"] == "page_image":
            # 包含實際頁面圖片
            content_blocks.append({
                "type": "image",
                "source": load_page_image(ctx.payload["source"], ctx.payload["page"])
            })
        else:
            # 包含文字/表格內容
            content_blocks.append({
                "type": "text",
                "text": f"[{ctx.payload['type']}] {ctx.payload['content']}"
            })

    content_blocks.append({
        "type": "text",
        "text": "僅使用提供的上下文回答問題。引用來源。"
    })

    response = vlm_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[{"role": "user", "content": content_blocks}]
    )
    return response.content[0].text
```

---

## 系統設計面試角度

### Q：設計一個用於回答包含文字、表格和圖表的收益報告問題的 RAG 系統。

**強而有力的回答：**

核心挑戰是收益報告中 60% 以上的資訊存在於表格和圖表中，而非散文。純文字 RAG 管道會錯過營收細分、趨勢線和比較資料。

**架構**：我會使用混合方法（模式 2 + 模式 3 的元素）：

1. **攝取**：以 300 DPI 渲染每個 PDF 頁面。執行 VLM 萃取 pass 將表格轉換為 markdown 並將圖表轉換為結構化描述。同時為每個頁面圖片生成 ColPali 多向量嵌入。

2. **儲存**：三個索引——（a）帶密集嵌入的文字區塊（財務文字），（b）帶密集嵌入的表格 markdown 加上表格類型的元資料過濾，（c）頁面級視覺檢索的 ColPali 多向量索引。

3. **檢索**：查詢分析器對查詢類型分類。「Q3 營收是多少？」觸發文字 + 表格搜尋。「顯示我營收趨勢」觸發視覺（ColPali）搜尋。結果透過 RRF 融合並由交叉編碼器重新排序。

4. **生成**：VLM（Claude 或 Gemini）接收融合的上下文——文字區塊、表格 markdown 和相關頁面圖片。它生成帶有特定頁面和表格引用的接地答案。

**關鍵取捨**：ColPali 在視覺內容上提供出色的召回，但每頁儲存約 1024 個向量，因此 10 萬份文件（50 萬頁）約有 5 億個向量。我會使用二元量化將儲存減少 32 倍，接受小幅召回損失。對於文字路徑，BM25 + 密集混合搜尋在財務術語上表現良好。

### Q：如何處理需要來自不同頁面上的圖表和表格資訊的查詢？

**強而有力的回答：**

這是跨模態、跨頁面檢索問題。解決方案有三個部分：

1. **檢索多樣性**：確保檢索器返回多種模態的結果。設定最低配額——每個檢索集中至少 2 個文字結果、2 個表格結果和 1 個視覺結果，無論哪個模態分數最高。

2. **上下文組裝**：在組裝 VLM 提示時，附帶明確出處包含所有檢索到的內容：「[表格來自第 14 頁：Q3 按地區營收]」和「[圖表來自第 22 頁：2024-2026 營收趨勢]」。VLM 然後可以跨兩者推理。

3. **代理式後備**：如果初始檢索未呈現足夠的跨模態上下文，代理層可以發出後續檢索：「表格顯示營收數字但使用者問的是趨勢——讓我也搜尋與營收相關的圖表。」

關鍵洞察是跨模態問題本質上是多跳的。系統需要從一個模態檢索、識別差距，然後從另一個模態檢索。

---

## 參考文獻

- Faysse 等。「ColPali：使用視覺語言模型的高效文件檢索」（ICLR 2025）
- Google。「SigLIP 2：多語言視覺語言編碼器」（2025）
- NVIDIA。「多模態檢索增強生成簡介」（2025）
- HKUDS。「RAG-Anything：全能多模態 RAG 框架」（2025）
- Vespa 部落格。「使用視覺語言模型的 PDF 檢索」（2024）

---

*上一篇：[晚期互動與 ColBERT](11-late-interaction-colbert.md)*
*下一篇：[RAG 評估模式](13-rag-evaluation-patterns.md)*