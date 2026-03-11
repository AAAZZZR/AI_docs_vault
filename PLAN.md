# DocVault — 本地智能文件知識庫

## 定位

個人本地應用，零認證。上傳 PDF → AI 深度理解 → 智能標籤自動演化 → RAG 問答。

核心差異化：**標籤不是靜態分類，而是一個會自我學習、合併、分裂、建立層級的活知識圖譜。**

---

## 架構總覽

```
┌─────────────────────────────────────────────────────┐
│  Next.js Frontend (localhost:3000)                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Upload   │  │ Chat/RAG │  │ Tag Explorer      │  │
│  │ + Status │  │ Stream   │  │ (Graph + List)    │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / SSE
┌────────────────────┴────────────────────────────────┐
│  FastAPI Backend (localhost:8000)                     │
│  ┌──────────────────────────────────────────────┐    │
│  │  No Auth — single local user, auto-provision │    │
│  └──────────────────────────────────────────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │Documents │  │ Chat/RAG │  │ Tags + Taxonomy  │   │
│  │ Router   │  │ Router   │  │ Router           │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│                     │                                 │
│  ┌──────────────────┴──────────────────────────┐     │
│  │            Services Layer                    │     │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │     │
│  │  │LLM      │ │Embedding │ │TagEvolution  │  │     │
│  │  │(multi)  │ │(multi)   │ │Service       │  │     │
│  │  └─────────┘ └──────────┘ └──────────────┘  │     │
│  └──────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────┐
│  Celery Worker                                       │
│  ┌──────────────────────────────────────────────┐    │
│  │ Task 1: PDF Processing Pipeline              │    │
│  │ Task 2: Tag Evolution (periodic)             │    │
│  └──────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───┴───┐      ┌────┴────┐     ┌─────┴─────┐
│ PG 16 │      │  Redis  │     │ LLM APIs  │
│pgvector│      │ Queue   │     │ (外部)    │
│ bytea │      │ Cache   │     │           │
└───────┘      └─────────┘     └───────────┘
```

---

## 一、移除所有 Auth

### 現狀問題
- `User` model 有 `clerk_id`, `plan`, `usage_this_month` 等 SaaS 欄位
- `deps.py` 每次 request 都 query user
- 所有 router 都 `Depends(get_current_user)`
- Frontend `api.ts` 有 `getAuthHeaders()`

### 改動

**Migration `004_remove_auth.py`**
```sql
-- 直接移除 users table
-- documents, tags, chat_messages 的 user_id 欄位全部 DROP
-- 移除 unique constraint (user_id, name) on tags → 改為 unique (name)
ALTER TABLE documents DROP COLUMN user_id;
ALTER TABLE tags DROP COLUMN user_id;
ALTER TABLE chat_messages DROP COLUMN user_id;
ALTER TABLE query_logs DROP COLUMN user_id;
DROP TABLE users;
```

**刪除的檔案/模組**
- `backend/app/models/user.py`
- `backend/app/core/security.py`
- `backend/app/routers/preferences.py`

**修改的檔案**
- `backend/app/core/deps.py` → 只剩 `get_db`，移除 `get_current_user`
- `backend/app/routers/documents.py` → 所有 endpoint 不再需要 `current_user` 參數
- `backend/app/routers/tags.py` → 同上
- `backend/app/routers/chat.py` → 同上
- `backend/app/tasks/pdf_processing.py` → 不再 filter by `user_id`
- `backend/app/services/rag.py` → 不再 filter by `user_id`
- `backend/app/main.py` → 移除 preferences router
- `backend/app/models/base.py` → 移除 `UserScopedMixin`
- Frontend: `api.ts` 移除 `getAuthHeaders`, preferences 相關 type/method; 移除 settings page

---

## 二、智能標籤系統（核心）

### 2.1 設計哲學

傳統系統：使用者手動建 tag → 手動分類 → tag 越來越亂
DocVault：**LLM 看完文件後自動生成 tag → 系統定期檢視所有 tag → 發現冗餘就合併、發現太粗就分裂、自動建立層級**

```
上傳第 1 份文件 → tags: ["機器學習", "神經網路", "深度學習"]
上傳第 5 份文件 → 系統發現 "機器學習" 和 "深度學習" 常一起出現
                → 自動建議: "深度學習" 應為 "機器學習" 的子標籤
上傳第 20 份文件 → "機器學習" 下已有 15 份文件
                → 系統自動分裂: CNN, RNN, Transformer 各自成為子標籤
使用者修正某個 tag → 系統記住偏好，未來自動調整
```

### 2.2 Tag Model 升級

```python
class Tag(Base):
    id: UUID
    name: str                    # unique
    color: str | None
    description: str | None      # LLM 生成的描述
    source: TagSource            # auto | user | evolved
    parent_id: UUID | None       # 層級關係 (FK self)
    embedding: Vector(768)       # tag 語意向量
    merge_history: JSONB         # 合併記錄 [{"from": "舊名", "at": "2024-..."}]
    document_count: int          # 反正規化，加速查詢（trigger 更新）
    created_at, updated_at
```

新增 `tag_relations` 表（備用，記錄 tag 間的語意關係）：
```python
class TagRelation(Base):
    id: UUID
    tag_a_id: UUID               # FK Tag
    tag_b_id: UUID               # FK Tag
    relation_type: str           # "similar" | "parent_child" | "see_also"
    strength: float              # 0.0 ~ 1.0
    created_at
```

### 2.3 初次標籤生成（文件上傳時）

現在的 `build_tag_prompt` 太簡單。升級為兩階段：

**Stage A — 語意分析（在 condensed note 生成時已完成）**
從 condensed_note 的 `entities`, `key_findings`, `document_type`, `sections` 萃取語意信號。

**Stage B — 上下文感知標籤生成**

Prompt 改進：
```
你是一個智能文件標籤系統。根據以下資訊為這份文件生成標籤。

文件摘要：{summary}
文件類型：{document_type}
關鍵發現：{key_findings}
實體：{entities}

現有標籤庫（含描述和文件數量）：
{existing_tags_with_descriptions}

規則：
1. 優先複用現有標籤（只要語意匹配度 > 0.7）
2. 新標籤需要同時提供名稱和一句話描述
3. 標籤分兩層：
   - 領域標籤（如：金融、醫療、AI）：每份文件 1-2 個
   - 主題標籤（如：風險管理、transformer、藥物試驗）：每份文件 2-5 個
4. 如果某個現有標籤語意相近但不完全匹配，建議是否應該合併
5. 回傳 confidence 分數

回傳格式：
{
  "tags": [
    {"name": "...", "description": "...", "confidence": 0.95, "level": "domain|topic"},
    {"name": "...", "description": "...", "confidence": 0.85, "level": "topic",
     "reuse_existing": "已有標籤名"}
  ],
  "merge_suggestions": [
    {"existing": "Deep Learning", "new_or_existing": "深度學習", "reason": "同義"}
  ]
}
```

**標籤 Embedding**：每個新建 tag 都生成 embedding，存入 `tags.embedding`，用於後續語意比對。

### 2.4 標籤演化引擎（Tag Evolution Engine）

這是核心差異化。一個 **Celery periodic task**，每當文件數量增加達到閾值（每 5 份新文件）或每日一次，觸發 tag 演化分析。

#### 演化操作

| 操作 | 觸發條件 | 實作 |
|------|----------|------|
| **合併** | 兩個 tag embedding cosine similarity > 0.9 且共現率高 | LLM 確認 → 保留較佳命名 → 更新所有 DocumentTag |
| **分裂** | 一個 tag 下文件數 > 閾值（如 15）且文件間語意分散 | LLM 分析子群 → 建議子標籤 → 使用者確認或自動執行 |
| **層級建立** | 發現 A 的文件集合是 B 的子集 | 設定 parent_id |
| **重命名** | LLM 發現更好的命名（基於文件內容統計） | 更新 name，記錄 merge_history |
| **清理** | tag 只有 0-1 份文件且存在 > 30 天 | 標記為候選刪除 |

#### 演化 Pipeline

```python
# Celery periodic task
@celery_app.task(name="tag_evolution")
def run_tag_evolution():
    """
    1. 載入所有 tags（含 embedding）
    2. 計算 tag-tag cosine similarity matrix
    3. 找出 similarity > 0.85 的 pair → 合併候選
    4. 找出 document_count > 15 的 tag → 分裂候選
    5. 找出 tag 之間的包含關係 → 層級候選
    6. 將候選操作送給 LLM 做最終判斷
    7. 執行通過的操作（或存為 pending 待使用者確認）
    8. 更新所有受影響的 tag embedding
    """
```

#### 使用者回饋迴路

```
使用者行為                    系統學習
────────────────────────────────────────
手動加 tag 到文件         → 該 tag 與文件內容關聯強化
手動移除 auto tag         → 降低該 tag 對此類文件的 confidence
手動合併兩個 tag          → 記住合併偏好
手動建立 parent-child     → 記住層級偏好
在 chat 中問「所有關於X的文件」→ X 成為 tag 候選（如果還不是）
```

實作：新增 `tag_events` 表記錄使用者操作：
```python
class TagEvent(Base):
    id: UUID
    event_type: str    # "add" | "remove" | "merge" | "rename" | "set_parent"
    tag_id: UUID
    document_id: UUID | None
    metadata: JSONB    # 額外資訊（如合併來源）
    created_at
```

演化引擎讀取這些 events 來學習使用者偏好。

### 2.5 Tag Explorer（前端）

不只是列表，而是一個**可視化的知識圖譜**：

```
┌──────────────────────────────────────────────┐
│  Tag Explorer                                 │
│                                               │
│  ┌─ View: [List] [Tree] [Graph] ──────────┐  │
│  │                                         │  │
│  │  [Tree View]                            │  │
│  │  ▼ 人工智慧 (25)                         │  │
│  │    ▼ 機器學習 (18)                       │  │
│  │      ► 深度學習 (12)                     │  │
│  │      ► 強化學習 (3)                      │  │
│  │    ► 自然語言處理 (7)                    │  │
│  │  ▼ 金融 (15)                            │  │
│  │    ► 風險管理 (8)                        │  │
│  │    ► 量化交易 (5)                        │  │
│  │                                         │  │
│  │  [Pending Evolution]                    │  │
│  │  💡 建議合併 "DL" → "深度學習" (92%)     │  │
│  │     [接受] [拒絕]                        │  │
│  │  💡 "機器學習" 下文件分散，建議分裂       │  │
│  │     [查看建議] [忽略]                    │  │
│  └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

---

## 三、移除不必要的複雜度

### 3.1 移除 Conversation 概念
本地應用不需要多輪對話管理。Chat 改為單一持續對話流，不需要 "New Chat"。
- 移除 `POST /chat/conversations`
- 移除 conversation list sidebar
- Chat 頁面直接就是一個對話框 + 歷史訊息（最近 50 條）

### 3.2 移除 QueryLog
直接整合進 ChatMessage，不需要獨立 table。

### 3.3 簡化 Document Status
移除 `UPLOADING`（前端直接 POST，不存在中間態）。只剩：
- `processing` → 正在分析
- `ready` → 完成
- `error` → 失敗

---

## 四、改進後的資料模型

```
┌─────────────┐      ┌──────────────┐      ┌─────────┐
│  documents  │──1:N─│ document_tags│──N:1──│  tags   │
│             │      │              │      │         │
│ id          │      │ document_id  │      │ id      │
│ title       │      │ tag_id       │      │ name    │
│ filename    │      │ confidence   │      │ parent_id│──self
│ pdf_data    │      │ source       │      │ embedding│
│ file_size   │      └──────────────┘      │ desc    │
│ page_count  │                            │ color   │
│ status      │      ┌──────────────┐      │ source  │
│ condensed   │      │ tag_relations│      │ doc_cnt │
│ embedding   │      │              │      └─────────┘
│ created_at  │      │ tag_a_id     │
└─────────────┘      │ tag_b_id     │      ┌──────────┐
                     │ relation     │      │tag_events│
┌─────────────┐      │ strength     │      │          │
│chat_messages│      └──────────────┘      │ type     │
│             │                            │ tag_id   │
│ id          │      ┌──────────────┐      │ doc_id   │
│ role        │      │ evolution_log│      │ metadata │
│ content     │      │              │      └──────────┘
│ refs        │      │ action       │
│ created_at  │      │ details      │
└─────────────┘      │ status       │
                     │ created_at   │
                     └──────────────┘
```

**新增 `evolution_log` 表** — 記錄每次演化操作：
```python
class EvolutionLog(Base):
    id: UUID
    action: str           # "merge" | "split" | "reparent" | "rename" | "delete"
    details: JSONB        # {"from": [...], "to": "...", "reason": "..."}
    status: str           # "pending" | "approved" | "rejected" | "auto_applied"
    created_at
```

---

## 五、API 設計

### Documents
```
POST   /api/v1/documents/upload          上傳 PDF
GET    /api/v1/documents                  列表（支援 tag filter、search）
GET    /api/v1/documents/{id}             詳情
GET    /api/v1/documents/{id}/download    下載 PDF
DELETE /api/v1/documents/{id}             刪除
```

### Tags
```
GET    /api/v1/tags                       所有 tag（含 tree 結構）
POST   /api/v1/tags                       手動建 tag
PATCH  /api/v1/tags/{id}                  更新 tag
DELETE /api/v1/tags/{id}                  刪除 tag
POST   /api/v1/tags/{id}/merge           合併 tag（target_id in body）
POST   /api/v1/tags/{id}/split           請求 LLM 分裂建議

POST   /api/v1/documents/{doc_id}/tags/{tag_id}    加 tag
DELETE /api/v1/documents/{doc_id}/tags/{tag_id}    移除 tag
```

### Tag Evolution
```
GET    /api/v1/evolution/pending          待審核的演化建議
POST   /api/v1/evolution/{id}/approve     核准
POST   /api/v1/evolution/{id}/reject      拒絕
POST   /api/v1/evolution/run              手動觸發演化
```

### Chat
```
GET    /api/v1/chat/messages              最近 N 條訊息
POST   /api/v1/chat/messages              發送（SSE streaming 回應）
DELETE /api/v1/chat/messages              清空歷史
```

---

## 六、實作順序

### Phase 1：清理基底
1. Migration 移除 `users` 表、所有 `user_id` 欄位
2. 移除所有 auth 相關代碼（deps, security, preferences router）
3. 簡化 Document status enum
4. 移除 conversation/query_log 機制，chat 簡化
5. 前端移除 settings page、auth headers、conversation sidebar

### Phase 2：標籤模型升級
6. Migration 加 `tags.embedding`, `tags.merge_history`, `tags.document_count`
7. 新建 `tag_relations`, `tag_events`, `evolution_log` 表
8. 更新 Tag model、schemas
9. 實作改進版 tag prompt（上下文感知）
10. 上傳時為每個新 tag 生成 embedding

### Phase 3：標籤演化引擎
11. `TagEvolutionService` — 合併、分裂、層級偵測
12. Celery periodic task 定時觸發
13. Evolution API endpoints
14. 使用者回饋記錄（TagEvent 寫入）

### Phase 4：前端 Tag Explorer
15. Tree view 組件
16. Pending evolution 審核 UI
17. Tag 詳情面板（描述、文件列表、關聯 tag）
18. 拖拽設定 parent-child 關係

### Phase 5：Chat 與 RAG 改進
19. Chat 頁面重構（移除 conversation 概念）
20. RAG 查詢加入 tag 語意加權
21. Chat 中提到的概念自動成為 tag 候選

---

## 七、技術決策

| 決策 | 選擇 | 原因 |
|------|------|------|
| PDF 存儲 | PostgreSQL bytea | 已實作，個人用量不需要物件存儲 |
| 向量索引 | pgvector HNSW | 已有，文件 + tag 共用 |
| Tag embedding 維度 | 與 doc embedding 相同 | 共用 embedding service |
| 演化觸發 | 基於事件 + 定時 | 新文件觸發局部、定時觸發全局 |
| 演化策略 | LLM 判斷 + 使用者確認 | 高 confidence 自動、低 confidence 人工 |
| 前端 tag graph | Tree view 優先 | 比力導向圖更直覺，後續可加 |

---

## 八、風險與限制

- **LLM 成本**：每次演化要呼叫 LLM。緩解：用 fast model、設定冷卻時間
- **Tag 爆炸**：文件少時 tag 可能過多。緩解：設定最低 confidence 閾值
- **合併錯誤**：自動合併可能失誤。緩解：高敏感操作需使用者確認
- **演化速度**：文件很少時演化無意義。緩解：至少 10 份文件才啟動演化
