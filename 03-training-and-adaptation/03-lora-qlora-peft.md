# LoRA、QLoRA 與 PEFT

參數高效微調（PEFT）是適配 LLM 的產業標準。本章涵蓋 LoRA 及其進階變體的機制。

## 目錄

- [PEFT 革命](#peft-革命)
- [LoRA 機制](#lora-機制)
- [QLoRA：4-bit 微調](#qlora4-bit-微調)
- [進階變體（DoRA、Vera、RS-LoRA）](#進階變體doravera-rs-lora)
- [多 LoRA 服務（轉接器）](#多-lora-服務轉接器)
- [面試問題](#面試問題)
- [參考資料](#參考資料)

---

## PEFT 革命

前沿模型（GPT-5.5、Claude Opus 4.7、Llama 4 405B）的全微調在經濟上對大多數企業不可行。PEFT 使得：

1. **記憶體效率**：在單張 A100 上訓練 70B 模型。
2. **速度**：透過更新 <1% 的權重，快 2 倍。
3. **模組化**：無需重新載入權重即可將「技能」（轉接器）交換到共享基底模型上。

---

## LoRA 機制

LoRA（Low-Rank Adaptation，低秩適配）將可訓練的秩分解矩陣注入 transformer 層。

```python
# LoRA 對權重矩陣 W 的方程式：
h = Wx + (BA)x * (alpha/r)
```

- **W**：預訓練權重（凍結，梯度 = None）
- **A, B**：LoRA 轉接器（可訓練）
- **r**：秩（如 8、16、64）
- **alpha**：縮放因子（通常為 2 * rank）

### 原則細節：目標模組

歷史上，我們僅瞄準 query/value 投影（`q_proj`、`v_proj`）。
**現代標準**：瞄準**所有**線性層（`q, k, v, o, gate, up, down`），即使在較低秩下也能獲得最大穩定性與效能。

---

## QLoRA：4-bit 微調

QLoRA 透過將基底模型量化至 4-bit（NF4）的同時維護 16-bit 梯度，進一步提高效率。

| 優化 | 方法 | 效益 |
|--------------|--------|---------|
| **NF4 量化** | 正規化浮點 4 | 比標準 Int4 更好的資訊密度 |
| **雙重量化** | 量化量化常數 | 每模型節省約 0.5 GB VRAM |
| **分頁** | 統一記憶體（Nvidia） | 透過溢出至 CPU RAM 防止 OOM |

---

## 進階變體（DoRA、Vera、RS-LoRA）

### 1. DoRA（權重分解低秩適配）

DoRA 將權重更新分解為**幅度**與**方向**。
- **結果**：學習速度比 LoRA 快 2 倍，效能更接近全微調。
- **為何勝出**：它允許模型獨立調整改變多少與改變什麼。

### 2. Vera（基於向量的隨機聚合）

Vera 使用固定隨機投影搭配小型可訓練向量，而非低秩矩陣 `A` 和 `B`。
- **效率**：相較 LoRA 減少轉接器大小**10 倍**。
- **使用場景**：大規模多 LoRA 服務。

### 3. RS-LoRA（秩穩定化 LoRA）

使用縮放因子 `alpha / sqrt(r)`。
- **效益**：允許你增加秩（至 256+）而不至於模型不穩定或需要較低學習率。

---

## 多 LoRA 服務（轉接器）

生產系統現在提供一個基底模型（如 Llama 4 70B），並在同一批次中動態交換轉接器。

```python
# vLLM/LMCache 多 LoRA 模式：
# 請求 1 -> 基底 + Finance_轉接器
# 請求 2 -> 基底 + Legal_轉接器
# 請求 3 -> 基底 + Medical_轉接器
```

**技術：** **連續批處理 + PagedAttention v3** 允許以僅 5-10% 延遲開銷提供 100+ 轉接器，相較基底模型。

---

## 面試問題

### Q：為什麼 LoRA alpha 參數通常設為 rank 的 2 倍？

**最佳答案：**

`alpha` 參數是 LoRA 更新的縮放因子。當我們初始化 LoRA 矩陣時，B 通常初始化為零，A 是隨機的。隨著訓練，更新大小取決於秩 `r`。透過設定 `alpha=2r`（或任何常數），我們確保如果之後決定更改秩（例如從 8 改為 16），無需重新調整學習率。縮放因子 `alpha/r` 將更新幅度標準化至學習率的相對關係。

### Q：DoRA 是什麼？為什麼用它取代標準 LoRA？

**最佳答案：**

DoRA（權重分解低秩適配）是一種 2024 年的技術，將預訓練權重更新分解為幅度與方向分量，類似權重正規化。標準 LoRA 同時更新幅度與方向，DoRA 允許獨立學習。經驗上，DoRA 展現更好的收斂性與更高準確度，往往匹配低秩下的全參數微調，使其成為高風險領域適配的首選。

---

## 參考資料

- Hu et al. "LoRA: Low-Rank Adaptation of Large Language Models" (2021)
- Liu et al. "DoRA: Weight-Decomposed Low-Rank Adaptation" (2024)
- Dettmers et al. "QLoRA: Efficient Finetuning of Quantized LLMs" (2023)

---

*下一篇：[RLHF 與 DPO](04-rlhf-and-dpo.md)*
