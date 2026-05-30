# LLM 系統的存取控制

安全的存取控制對於多使用者和多租戶 LLM 應用程式至關重要。本章涵蓋身份驗證、授權和資料隔離模式。

## 目錄

- [存取控制需求](#存取控制需求)
- [身份驗證模式](#身份驗證模式)
- [授權模型](#授權模型)
- [租戶隔離](#租戶隔離)
- [API 金鑰管理](#api-金鑰管理)
- [稽核與合規](#稽核與合規)
- [面試題目](#面試題目)
- [參考文獻](#參考文獻)

---

## 存取控制需求

### 安全維度

| 維度 | 描述 | 控制措施 |
|-----------|-------------|----------|
| **身份驗證** | 誰在提出請求？ | API 金鑰、OAuth、JWT |
| **授權** | 他們能做什麼？ | RBAC、ABAC、政策 |
| **隔離** | 他們能看到什麼資料？ | 租戶篩選、加密 |
| **稽核** | 他們做了什麼？ | 日誌、合規報告 |

### LLM 特定考量

| 考量 | 風險 | 緩解措施 |
|---------|------|------------|
| 提示詞注入 | 繞過存取控制 | 輸入驗證 |
| 資料外洩 | 跨租戶暴露 | 嚴格篩選 |
| 模型輸出 | 暴露受保護資訊 | 輸出過濾 |
| 上下文污染 | 注入未授權資料 | 上下文驗證 |

---

## 身份驗證模式

### API 金鑰身份驗證

```python
class APIKeyAuthenticator:
    def __init__(self, key_store):
        self.key_store = key_store
    
    async def authenticate(self, api_key: str) -> AuthResult:
        if not api_key:
            return AuthResult(authenticated=False, error="缺少 API 金鑰")
        
        # 雜湊金鑰以進行查詢
        key_hash = self.hash_key(api_key)
        
        # 在儲存區中查詢
        key_record = await self.key_store.get(key_hash)
        
        if not key_record:
            return AuthResult(authenticated=False, error="無效的 API 金鑰")
        
        if key_record.expired:
            return AuthResult(authenticated=False, error="API 金鑰已過期")
        
        if key_record.revoked:
            return AuthResult(authenticated=False, error="API 金鑰已撤銷")
        
        return AuthResult(
            authenticated=True,
            user_id=key_record.user_id,
            tenant_id=key_record.tenant_id,
            scopes=key_record.scopes
        )
    
    def hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()
```

### JWT 與範圍

```python
class JWTAuthenticator:
    def __init__(self, public_key: str):
        self.public_key = public_key
    
    async def authenticate(self, token: str) -> AuthResult:
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                audience="llm-api"
            )
            
            return AuthResult(
                authenticated=True,
                user_id=payload["sub"],
                tenant_id=payload.get("tenant_id"),
                scopes=payload.get("scopes", []),
                expires_at=datetime.fromtimestamp(payload["exp"])
            )
        except jwt.ExpiredSignatureError:
            return AuthResult(authenticated=False, error="權杖已過期")
        except jwt.InvalidTokenError as e:
            return AuthResult(authenticated=False, error=str(e))
```

---

## 授權模型

### 基於角色的存取控制 (RBAC)

```python
class RBACAuthorizer:
    ROLE_PERMISSIONS = {
        "admin": ["*"],
        "developer": ["generate", "embed", "fine_tune", "read_metrics"],
        "user": ["generate", "embed"],
        "viewer": ["read_metrics"]
    }
    
    def authorize(self, user: User, action: str) -> bool:
        permissions = self.ROLE_PERMISSIONS.get(user.role, [])
        
        if "*" in permissions:
            return True
        
        return action in permissions
```

### 基於屬性的存取控制 (ABAC)

```python
class ABACAuthorizer:
    def __init__(self, policy_engine):
        self.policy_engine = policy_engine
    
    async def authorize(
        self,
        subject: dict,       # 誰（使用者屬性）
        action: str,         # 什麼（操作）
        resource: dict,      # 在什麼上（資源屬性）
        context: dict         # 何時/何處（環境）
    ) -> AuthzResult:
        # 評估所有適用的政策
        policies = await self.policy_engine.get_policies(action)
        
        for policy in policies:
            result = policy.evaluate(subject, action, resource, context)
            if result == PolicyResult.DENY:
                return AuthzResult(allowed=False, reason=policy.name)
            if result == PolicyResult.ALLOW:
                return AuthzResult(allowed=True)
        
        return AuthzResult(allowed=False, reason="沒有符合的政策")
```

### 模型層級權限

```python
class ModelAccessControl:
    MODEL_TIERS = {
        "gpt-4o": ["enterprise", "professional"],
        "gpt-4o-mini": ["enterprise", "professional", "starter"],
        "claude-3.5-sonnet": ["enterprise"],
        "claude-3.5-haiku": ["enterprise", "professional", "starter"]
    }
    
    def can_access_model(self, user: User, model: str) -> bool:
        allowed_tiers = self.MODEL_TIERS.get(model, [])
        return user.tier in allowed_tiers
    
    def get_available_models(self, user: User) -> list[str]:
        return [
            model for model, tiers in self.MODEL_TIERS.items()
            if user.tier in tiers
        ]
```

---

## 租戶隔離

### 資料隔離模式

```python
class TenantIsolatedVectorStore:
    def __init__(self, vector_db):
        self.db = vector_db
    
    async def search(
        self,
        tenant_id: str,
        query_embedding: list[float],
        top_k: int = 10
    ) -> list[dict]:
        # 關鍵：在資料庫層級始终按 tenant_id 篩選
        results = await self.db.search(
            query_vector=query_embedding,
            top_k=top_k,
            filter={"tenant_id": {"$eq": tenant_id}}  # 強制篩選
        )
        
        return results
    
    async def insert(
        self,
        tenant_id: str,
        documents: list[dict]
    ):
        # 關鍵：始終在元資料中包含 tenant_id
        for doc in documents:
            doc["metadata"]["tenant_id"] = tenant_id
        
        await self.db.insert(documents)
```

### 提示詞隔離

```python
class TenantAwarePromptBuilder:
    def build_prompt(
        self,
        tenant_id: str,
        user_query: str,
        context: list[dict]
    ) -> str:
        # 驗證所有上下文屬於該租戶
        for doc in context:
            if doc.get("tenant_id") != tenant_id:
                raise SecurityError("偵測到跨租戶上下文")
        
        # 建立隔離的提示詞
        return f"""
[租戶：{tenant_id}]
來自租戶文件的上下文：
{self.format_context(context)}

使用者查詢：{user_query}
"""
```

### 快取隔離

```python
class TenantIsolatedCache:
    def __init__(self, cache_backend):
        self.cache = cache_backend
    
    def _scoped_key(self, tenant_id: str, key: str) -> str:
        return f"tenant:{tenant_id}:{key}"
    
    async def get(self, tenant_id: str, key: str) -> any:
        return await self.cache.get(self._scoped_key(tenant_id, key))
    
    async def set(self, tenant_id: str, key: str, value: any, ttl: int = 3600):
        await self.cache.set(
            self._scoped_key(tenant_id, key),
            value,
            ttl=ttl
        )
```

---

## API 金鑰管理

### 金鑰生命週期

```python
class APIKeyManager:
    KEY_PREFIX = "llm_"
    
    async def create_key(
        self,
        user_id: str,
        tenant_id: str,
        name: str,
        scopes: list[str],
        expires_in_days: int = 365
    ) -> APIKey:
        # 產生安全金鑰
        raw_key = self.KEY_PREFIX + secrets.token_urlsafe(32)
        key_hash = self.hash_key(raw_key)
        
        # 儲存中繼資料（而非原始金鑰）
        key_record = APIKeyRecord(
            id=generate_id(),
            hash=key_hash,
            user_id=user_id,
            tenant_id=tenant_id,
            name=name,
            scopes=scopes,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=expires_in_days)
        )
        
        await self.store.save(key_record)
        
        # 僅在建立時回傳原始金鑰（不儲存）
        return APIKey(
            id=key_record.id,
            key=raw_key,  # 僅在建立時回傳
            name=name,
            scopes=scopes,
            expires_at=key_record.expires_at
        )
    
    async def revoke_key(self, key_id: str, reason: str):
        await self.store.update(key_id, {
            "revoked": True,
            "revoked_at": datetime.now(),
            "revoke_reason": reason
        })
        
        await self.audit_log.log("api_key_revoked", {
            "key_id": key_id,
            "reason": reason
        })
```

### 金鑰輪換

```python
class KeyRotator:
    async def rotate_key(self, old_key_id: str) -> APIKey:
        old_key = await self.key_store.get(old_key_id)
        
        # 使用相同權限建立新金鑰
        new_key = await self.key_manager.create_key(
            user_id=old_key.user_id,
            tenant_id=old_key.tenant_id,
            name=f"{old_key.name}（已輪換）",
            scopes=old_key.scopes
        )
        
        # 寬限期：舊金鑰暫時仍可運作
        await self.key_store.update(old_key_id, {
            "deprecated": True,
            "deprecated_at": datetime.now(),
            "grace_period_ends": datetime.now() + timedelta(days=7)
        })
        
        await self.notify_user(old_key.user_id, new_key)
        
        return new_key
```

---

## 稽核與合規

### 稽核日誌記錄

```python
class AuditLogger:
    async def log_request(
        self,
        request: LLMRequest,
        response: LLMResponse,
        auth: AuthResult
    ):
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request.id,
            "user_id": auth.user_id,
            "tenant_id": auth.tenant_id,
            "action": "llm_generate",
            "model": request.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cost": response.cost,
            "latency_ms": response.latency_ms,
            # 出於隱私考量，雜湊內容
            "input_hash": self.hash_content(request.prompt),
            "output_hash": self.hash_content(response.content)
        }
        
        await self.audit_store.append(audit_entry)
```

### 合規報告

```python
class ComplianceReporter:
    async def generate_report(
        self,
        tenant_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> ComplianceReport:
        logs = await self.audit_store.query(
            tenant_id=tenant_id,
            start=start_date,
            end=end_date
        )
        
        return ComplianceReport(
            tenant_id=tenant_id,
            period=(start_date, end_date),
            total_requests=len(logs),
            unique_users=len(set(l["user_id"] for l in logs)),
            models_used=list(set(l["model"] for l in logs)),
            total_cost=sum(l["cost"] for l in logs),
            data_access_events=self.extract_data_access(logs),
            security_events=await self.get_security_events(tenant_id, start_date, end_date)
        )
```

---

## 面試題目

### Q：如何在 RAG 系統中實作多租戶隔離？

**強烈回答：**

「多租戶隔離需要深度防禦：

**向量資料庫層級：**
- 每個向量在元資料中包含 tenant_id
- 所有查詢在資料庫層級按 tenant_id 篩選
- 絕不在檢索後篩選（資料已洩漏到記憶體）

**快取層級：**
- 所有快取金鑰前綴為 tenant_id
- 語義快取限定為租戶
- 即使對於相同的查詢，也不會有跨租戶快取命中

**提示詞層級：**
- 在包含之前，驗證上下文文件屬於請求租戶
- 絕不混合來自多個租戶的上下文

**輸出層級：**
- 驗證回應不包含跨租戶資訊
- 作為額外保障的輸出過濾

**稽核：**
- 記錄所有帶有租戶上下文的存取
- 監控跨租戶存取嘗試

關鍵原則：tenant_id 是每個資料存取點的強制篩選條件，而非可選參數。」

### Q：如何管理 LLM 服務的 API 金鑰？

**強烈回答：**

「安全的 API 金鑰管理：

**建立：**
- 產生密碼學安全的隨機金鑰
- 只儲存雜湊值，一次回傳原始金鑰
- 關聯使用者、租戶、範圍、過期時間

**驗證：**
- 將傳入的金鑰雜湊化，與儲存的雜湊比對
- 檢查過期和撤銷狀態
- 驗證範圍符合請求的操作

**輪換：**
- 支援帶有寬限期的金鑰輪換
- 過渡期間舊金鑰仍可運作（7 天）
- 通知使用者即將過期

**安全：**
- 對失敗的身份驗證嘗試進行速率限制
- 疑似入侵時立即撤銷
- 稽核所有金鑰操作

**範圍：**
- 細粒度：模型存取、操作類型、每日限制
- 預設最小權限

關鍵原則：永不儲存原始金鑰、支援輪換、實施最小權限。」

---

## 參考文獻

- OAuth 2.0：https://oauth.net/2/
- OWASP API Security：https://owasp.org/API-Security/

---

*上一篇：[安全性基礎](01-security-fundamentals.md)*