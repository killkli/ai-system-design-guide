# Semantic Kernel

**Semantic Kernel（SK）** 是 Microsoft 的企業級 AI 編排引擎。它仍然是致力於 **Azure/Microsoft 生態系統**和 **C#/.NET** 架構的組織的主要橋樑，儘管其大部分前進動力現在在 **Microsoft Agent Framework** 內發布（這是 AutoGen + SK 的統一後續版本，2026 年 2 月 RC 1.0，2026 年 Q2 GA）。

## 目錄

- [企業 DNA](#dna)
- [外掛和規劃器](#plugins)
- [記憶體和連接器](#memory)
- [多語言支援（C# 對比 Python）](#multi-language)
- [面試題目](#interview-questions)
- [參考文獻](#references)

---

## 企業 DNA

當 LangChain 被新創公司偏好時，Semantic Kernel 被**銀行和財富 500 強**偏好。
- **依賴注入**：SK 遵循標準企業設計模式。
- **強型別**：C# 型別的一級支援使其在大型任務關鍵系統中具有高可靠性。
- **安全性**：與 Azure Active Directory（Microsoft Entra ID）和受控識別的深度整合。

---

## 外掛和規劃器

1. **Kernel 函式**：基本邏輯單位（原生程式碼或 LLM 提示詞）。
2. **外掛**：函式集合（例如「GitHub 外掛」或「SQL 外掛」）。
3. **規劃器**：SK 的規劃器已從簡單的 ReAct 演變為**階層規劃器**，可以協調跨越多天的長期業務流程。

---

## 記憶體和連接器

Semantic Kernel 使用**連接器**來抽象底層基礎設施。
- **通用連接器**：一個介面適用於 OpenAI、Mistral 和本地 Onyx 模型。
- **向量儲存抽象**：無需更改核心業務邏輯，即可無縫切換 Azure AI Search、Pinecone 和 Qdrant。

---

## 多語言支援

SK 是少數主要框架中將 C# 和 Python 視為平等的框架之一。
- **模式**：在 Python 中開發和原型設計；在 C# 中部署核心編排以提高效能和型別安全。
- **邏輯共享**：跨兩種語言工作的共享提示範本（.yaml）。

---

## 面試題目

### Q：為何 Staff 工程師會選擇 Semantic Kernel 而非 LangChain？

**強烈回答：**
**架構對齊**。如果一個組織已經建立在 .NET/Azure 堆疊上，Semantic Kernel 適合其現有的 CI/CD、監控（App Insights）和安全（Entra ID）管線。LangChain 通常感覺像是一個「外部」技術片段。此外，SK 的**強型別**和**依賴注入**模式防止了大型 LangChain 專案中常見的「義大利麵程式碼」。對於處理敏感財務資料的企業，**原生 Azure 整合**（安全和審計）是決定性因素。

### Q：Semantic Kernel 中的「函式呼叫」抽象是什麼？

**強烈回答：**
SK 使用**基於外掛的模型**。每個函式（原生 C# 或基於 LLM）都向 Kernel 註冊。當 LLM 決定需要工具時，Kernel 在外掛登錄中查詢函式、驗證參數並執行它。SK 現在支援**自動意圖檢測**：基於當前上下文視窗，Kernel 可以主動建議使用者可能需要的外掛，而無需他們提出要求。

---

## 參考文獻

- Microsoft Learn。〈Semantic Kernel 文件〉（2025）
- Azure Architecture Center。〈使用 Semantic Kernel 的 AI 設計模式〉（2025）
- Build 2025。〈SK 輔助的未來〉（2025 會議回顧）

---

*下一篇：[AutoGen 和 CrewAI](07-autogen-crewai.md)*