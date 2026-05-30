# 量化深度探討

量化是減少模型權重精度（如從 16-bit 降至 4-bit）以節省記憶體並提高推論速度的過程。這是在消費者和單 GPU 硬體上部署大型模型的主要工具。

## 目錄

- [精度-效能權衡](#精度-效能權衡)
- [量化方法（NF4、GPTQ、AWQ）](#量化方法nf4-gptq-awq)
- [GGUF 與 EXL2](#gguf-與-exl2)
- [KV 快取量化（VRAM 節省器）](#kv-快取量化vram-節省器)
- [量化感知微調](#量化感知微調)
- [面試問題](#面試問題)
- [參考資料](#參考資料)

---

## 精度-效能權衡

傳統模型使用 **BF16**（16-bit）。量化尋求將其減少至 **FP8**、**4-bit（Int4/NF4）**，甚至 **1.5-bit（BitNet）**。

| 精度 | 位元數 | 權重大小（8B 模型） | 品質損失 | GPU 相容性 |
|-----------|------|------------------------|--------------|-------------------|
| **BF16** | 16 | 16 GB | 0%（基準） | 所有現代 |
| **FP8** | 8 | 8 GB | < 1% | H100 / B200 / RTX 4090 |
| **4-bit（NF4）**| 4 | 5 GB | 1-2% | 所有現代 |
| **2-bit** | 2 | 2.5 GB | 10-15% | 研究/專業化 |

---

## 量化方法

### 1. NF4（NormalFloat4）

QLoRA 微調的黃金標準。它假設權重服從常態分布，並將其映射至 16 個值。

### 2. AWQ（激活感知權重量化）

不是對所有權重平等量化，AWQ 識別對品質**最重要**的「顯著」權重的 **1%**，並將它們保持較高精度。
- **優點**：比 GPTQ 更好的準確度。

### 3. FP8（多節點標準）

Nvidia Transformer Engine 原生支援的硬體量化。
- **為何勝出**：提供 Int8 的速度與 Float16 的動態範圍，使其在訓練與推論兩方面都穩定。

---

## GGUF 與 EXL2

### GGUF（llama.cpp）

- **部署**：CPU + GPU 卸載。
- **優點**：跨平台（Mac、Linux、Windows）、單一檔案、高度可攜。
- **缺點**：比純 GPU 格式慢。

### EXL2（ExLlamaV2）

- **部署**：僅 GPU（Nvidia）。
- **優點**：Nvidia GPU 上**最快的** 4-bit 格式。比 AutoGPTQ/AWQ 顯著更快。
- **缺點**：不靈活（僅限 Nvidia）。

---

## KV 快取量化（VRAM 節省器）

在長上下文 RAG（1M+ tokens）中，**KV 快取**消耗的 VRAM 通常比模型權重本身還多。

- **BF16 KV 快取**：2M tokens ≈ 32GB VRAM（8B 模型）。
- **FP8/Int4 KV 快取**：2M tokens ≈ 8GB - 16GB VRAM。

**細節**：現代服務框架（vLLM、SGLang、TensorRT-LLM）現在支援**串流量化**，KV 快取即時壓縮，允許在同一 GPU 上達到 4 倍更高的並發。

---

## 量化感知訓練（QAT）

不是在模型訓練*後*量化（訓練後量化），QAT 在訓練*過程中*模擬量化。
- **結果**：模型學習補償失去的精度。
- **狀態**：對小於 3B 參數的模型是必需的，以在 4-bit 下保持可用。

---

## 面試問題

### Q：為什麼 QLoRA 使用 NF4 而非標準 Float4？

**最佳答案：**

標準 Float4 具有固定網格，不能很好地映射至 LLM 權重的實際分布，後者通常服從以零為中心的常態分布。NF4（NormalFloat4）是一種數學上優化的資料類型，使得常態分布的每個值正好包含相等數量的量化區間。這防止了權重「叢集」，確保模型保留盡可能多的資訊（熵），從而顯著提高準確度超過標準 4-bit 整數。

### Q：AWQ 與 GPTQ 有何不同？

**最佳答案：**

GPTQ 是一種「逐層」量化方法，最小化權重的均方誤差。AWQ（激活感知權重量化）是「輸入感知」的。它基於小型校準運行中看到的實際啟動值，識別哪些權重最「顯著」。透過僅將這些重要權重（通常為 1%）保持較高精度並量化其餘，AWQ 在較小模型或更積極量化（如 3-bit）的情況下達到比 GPTQ 更好的困惑度。

---

## 參考資料

- Dettmers et al. "QLoRA: Efficient Finetuning of Quantized LLMs" (2023)
- Frantar et al. "GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers" (2022)
- Lin et al. "AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration" (2023)

---

*下一篇：[推論優化](../04-inference-optimization/01-inference-fundamentals.md)*
