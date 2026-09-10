# Project Agent Instructions

## 1. Project Overview

本專案是「國小智慧排課系統」。

目標是建立一個具備實際學校排課情境的 full-stack web application，包含：

* 教師、班級、科目、教室、時段等資料管理
* 教師授課資格與實際授課分配
* 教師可用時段
* 每週授課節數需求
* 自動排課
* Hard Constraints 驗證
* Soft Constraints 評分與最佳化
* Greedy Scheduling
* Backtracking Scheduling
* 衝突檢查與衝突原因說明
* 手動調整課表
* 課表版本管理
* Draft / Published 狀態
* JWT Authentication
* Role-based Authorization
* REST API
* Automated Tests
* Docker Compose
* GitHub Portfolio

這是一個學習與作品集專案。

優先順序：

1. 正確性
2. 可理解性
3. 可測試性
4. 可維護性
5. 架構清晰
6. 功能完整
7. 效能最佳化

不要為了追求複雜或「看起來很厲害」而增加不必要的技術。

---

# 2. Technology Stack

## Frontend

* React
* TypeScript
* Vite

## Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic

## Database

* PostgreSQL

## Testing

* pytest
* frontend testing framework（依實際建立的 frontend stack 決定）

## Infrastructure

* Docker
* Docker Compose

## Version Control

* Git
* GitHub

Python dependency management 使用：

* `venv`
* `pip`

不要自行改用 Poetry、Pipenv、uv 或其他 package manager，除非使用者明確要求。

---

# 3. Architecture

主要架構：

React / TypeScript
↓
FastAPI
↓
API Layer
↓
Service Layer
↓
Domain / Scheduling Engine
↓
Repository / ORM
↓
PostgreSQL

核心原則：

* API Layer 負責 HTTP request / response
* Service Layer 負責 application logic
* Domain / Scheduling Engine 負責排課領域邏輯
* Repository / SQLAlchemy 負責資料存取
* Database 負責持久化

不要把商業邏輯全部放進 FastAPI route。

不要讓 SQLAlchemy model 直接充當所有 API response schema。

不要讓 Scheduling Engine 直接操作 PostgreSQL 或 SQLAlchemy Session。

---

# 4. Scheduling Engine Boundary

Scheduling Engine 是本專案的重要核心。

Scheduling Engine：

* 不可以直接存取 PostgreSQL
* 不可以 import SQLAlchemy Session
* 不可以依賴 FastAPI
* 不可以依賴 HTTP request
* 不可以直接操作 Repository
* 不可以直接修改資料庫

Scheduling Engine 應接收已準備好的 domain data / input model，產生 scheduling result。

概念流程：

Database
→ Repository
→ Service Layer
→ Domain Objects
→ Scheduling Engine
→ Scheduling Result
→ Service Layer
→ Database

Scheduler 必須可以在沒有 FastAPI request 的情況下被獨立測試。

---

# 5. Database Design Principles

目前核心 domain 包含：

* User
* AcademicYear
* Semester
* School
* Grade
* Class
* Teacher
* Subject
* Room
* TimeSlot
* TeacherSubject
* TeacherClassAssignment
* TeacherAvailability
* ClassSubjectRequirement
* Lesson
* ScheduleVersion
* Schedule

重要規則：

### TeacherSubject

表示：

「教師具備教授某科目的資格」

不代表教師一定被安排教授該科。

### TeacherClassAssignment

表示：

「這學期這位教師實際負責這個班級的某項教學」

資格與實際授課分配必須分開。

### ClassSubjectRequirement

表示：

某學期、某班級、某科目每週需要幾節課，以及相關限制。

例如：

* weekly_periods
* required_teacher
* required_room_type
* consecutive_limit

### Lesson

如果某科目每週需要 3 節課，應該建立 3 個 lesson instances。

每個 lesson instance 需要被安排：

* teacher
* class
* subject
* time slot
* room（如果需要）

### ScheduleVersion

課表應透過 ScheduleVersion 管理版本。

至少區分：

* DRAFT
* PUBLISHED

Published schedule 不可以直接修改。

如果需要修改已發布課表：

Published
→ 建立新的 Draft Version
→ 修改
→ 驗證
→ Publish

不要直接覆蓋已發布資料。

---

# 6. Scheduling Constraints

## Hard Constraints

目前核心 Hard Constraints：

H1 Teacher Conflict
同一教師同一時段不能有兩堂課。

H2 Class Conflict
同一班級同一時段不能有兩堂課。

H3 Room Conflict
同一教室同一時段不能有兩堂課。

H4 Teacher Availability
教師不可在 unavailable 時段授課。

H5 Teacher Qualification
教師必須具備該科目授課資格。

H6 Required Teacher
指定教師時必須由指定教師授課。

H7 Weekly Subject Requirement
每個班級的科目每週必須滿足要求節數。

H8 Teacher Maximum Workload
教師不可超過最大每週授課節數。

H9 Room Type
需要特殊教室時必須符合教室類型。

H10 Room Capacity
教室容量必須足夠。

H11 Non-teaching Period
不可安排於非教學時段。

H12 Active Status
停用中的教師、班級、科目、教室等不得被排入新課表。

Hard Constraint violation：

* 不得產生合法排課結果
* 必須可以被驗證
* 最好能提供明確 violation explanation

---

## Soft Constraints

目前可包含：

S1 Teacher Daily Balance
S2 Minimize Teacher Gaps
S3 Subject Distribution Across Days
S4 Avoid Excessive Consecutive Lessons
S5 Avoid First Period Preference Violation
S6 Teacher Daily Maximum Preference
S7 Class Daily Balance

Soft Constraints 不可以讓課表變成 illegal schedule。

原則：

先滿足所有 Hard Constraints，再比較 Soft Constraint score。

---

# 7. Scheduling Algorithms

實作順序：

1. Greedy Scheduler
2. Backtracking Scheduler
3. Soft Constraint Optimization
4. Optional advanced solver（未來才考慮）

Greedy：

* 優先處理最受限制的 lesson
* 建立 candidate teachers / slots / rooms
* 過濾 Hard Constraint violation
* 選擇可行配置

Backtracking：

* 當目前選擇造成後續無法排課時 rollback
* 嘗試其他 candidate
* 必須有 search limit，例如：

  * maximum nodes
  * timeout

不可讓演算法無限制搜尋。

Scheduling 必須具備：

* success / failure
* execution duration
* search statistics（適當時）
* failure reason
* final score（若有 optimization）

如果無法產生完整合法課表：

**不得把部分排好的課表當作成功結果。**

---

# 8. Conflict Explanation

排課系統不應只回傳：

`Schedule failed`

應盡可能提供可理解的原因，例如：

* Teacher conflict
* Class conflict
* Room conflict
* Teacher unavailable
* Teacher not qualified
* Required teacher unavailable
* No suitable room
* Weekly periods cannot be satisfied

Conflict result 可以包含：

* type
* severity
* lesson_id
* teacher_id
* class_id
* subject_id
* time_slot_id
* message
* suggested_action（如果能合理提供）

錯誤訊息應該讓使用者知道：

「為什麼不能排」以及「可能怎麼解決」。

---

# 9. API Rules

API 使用：

`/api/v1/`

REST API 優先。

API Layer：

* 驗證 request
* 呼叫 Service
* 回傳 response

不要在 route 中直接實作複雜排課演算法。

Error Handling（CRUD 標準慣例，自 School 範例確立）：

* Service 層的 `create_xxx()` / `update_xxx()` / `delete_xxx()` 遇到 SQLAlchemy `IntegrityError` 時，一律 `db.rollback()` 後改拋出 `app/services/exceptions.py` 定義的自訂例外（`DependentRecordsExistError` / `InvalidReferenceError` / `DuplicateValueError`），不拋 `HTTPException`——Service 層必須維持與 FastAPI 無關。
* `create_xxx()` / `update_xxx()` 應呼叫 `raise_for_integrity_error(exc)` 做分類（依 `exc.orig` 的 psycopg 例外型別判斷，不用字串比對）；`delete_xxx()` 遇到 `IntegrityError` 一律視為 `DependentRecordsExistError`（DELETE 只會因為被其他表參照而失敗）。
* 這三個例外由 `backend/app/main.py` 的全域 `@app.exception_handler()` 統一轉成 HTTP 回應（409 / 422 / 409）。Router 層**不需要**也不應該自己 `try/except` 這些例外。
* 後續每張表複製 CRUD 時都應該遵循這個模式，不要各自重新設計錯誤處理。

Authentication：

* JWT
* Password hashing
* RBAC

Roles：

* ADMIN
* TEACHER
* STUDENT

Authorization 必須由 backend enforcement。

不能只依靠 frontend 隱藏按鈕來防止未授權操作。

---

# 10. Python Rules

Python code：

* 優先使用 type hints
* 避免巨大 function
* 避免巨大 class
* 避免 circular dependency
* 避免 global mutable state
* 不要使用 `except Exception: pass`
* 不要吞掉錯誤
* 不要用 magic numbers 取代 domain constants
* 不要把 business logic 隱藏在 utility function 裡

錯誤處理應該：

* 清楚
* 可追蹤
* 可測試
* 對 API 使用者提供合理錯誤訊息

---

# 11. TypeScript Rules

TypeScript：

* 優先使用明確 type
* 避免 `any`
* API response 建立明確型別
* UI component 不應直接包含大量 business logic
* API 呼叫與 UI rendering 適當分離
* 不要把整個 application 寫在單一 component

---

# 12. Database Migration Rules

任何 schema change：

Model change
→ Alembic migration
→ migration test / verification

禁止：

* 只修改 SQLAlchemy model 而不建立 migration
* 手動修改 production schema
* 為了讓測試通過而偷偷修改 database schema

Migration 必須可追蹤。

---

# 13. Testing Rules

任何新功能都應該考慮對應測試。

至少包含：

### Unit Test

測試：

* domain logic
* constraints
* service logic
* scheduler components

### Integration Test

測試：

* API
* database interaction
* authentication / authorization

### Scheduling Test

必須測試：

* teacher conflict
* class conflict
* room conflict
* availability
* qualification
* weekly periods
* room requirement
* workload
* impossible scheduling case

### Edge Cases

例如：

* 沒有可用教師
* 沒有可用教室
* 時段不足
* 教師全部 unavailable
* 要求節數超過可排時段
* 多個限制同時衝突

### Regression Test

修 bug 時：

bug
→ 加入 regression test
→ 修正
→ 確認 test 通過

不要刪除或降低測試來讓測試通過。

---

# 14. Determinism

Scheduling Engine 應盡可能支援 deterministic behavior。

如果演算法使用 randomization：

* 必須可以提供 random seed
* 相同 input + 相同 seed 應產生可重現結果

這對 debugging 與 testing 很重要。

---

# 15. Validation

Backend 是最終權威。

Frontend validation：

* 用於改善 UX

Backend validation：

* 負責真正判定是否合法

任何重要 constraint：

Frontend validation
≠
Backend validation

不能只在 frontend 判斷：

「這樣可以排。」

Backend 必須再次驗證。

尤其是：

* drag & drop
* manual timetable adjustment
* publish schedule

---

# 16. Agent Permission Boundary

Agent 可以：

* 建立程式碼
* 修改程式碼
* 建立測試
* 執行測試
* 執行 lint / type check
* 執行 application locally
* 分析錯誤
* 修正目前 task 所需要的程式

Agent 不可以自行：

* commit
* push
* merge branch
* 修改 GitHub repository settings
* 修改 secrets
* 修改 production infrastructure
* 大幅改變 architecture
* 更換 technology stack
* 新增大型 dependency
* 刪除重要測試
* 刪除使用者尚未確認的功能
* 把 MVP 擴張成大型系統

如果需要上述行為：

**先告知使用者並等待確認。**

---

# 17. Dependency Rules

新增 dependency 前：

1. 判斷是否真的需要
2. 優先使用現有 dependency
3. 說明新增 dependency 的理由
4. 如果會影響 architecture，先詢問使用者

不要因為「比較方便」就新增大型 framework。

---

# 18. Scope Control

目前 MVP 不包含：

* Mobile App
* Voice Interface
* Image Generation
* Vector Database
* Microservices
* Kubernetes
* Redis
* Message Queue
* Multi-school SaaS
* AI Agent Framework

如果未來確實需要，再另外討論。

不要自行 scope creep。

---

# 19. Working Method

每一個 Task 遵循：

Read
→ Analyze
→ Plan
→ Implement
→ Test
→ Run
→ Fix
→ Review
→ Report

## Read

先閱讀：

* `AGENTS.md`
* 相關 source files
* 相關 tests
* database models
* migrations
* interfaces

不要沒有閱讀現有程式就直接重寫。

## Analyze

說明：

* 現況
* 問題
* 需要修改的位置
* 可能影響

## Plan

先提出簡短 implementation plan。

如果需求存在重大歧義或會改變 architecture：

**先詢問使用者。**

如果只是一般 implementation detail：

Agent 可以自行選擇合理方案。

## Implement

只修改完成目前 Task 所必要的檔案。

不要順便重構整個專案。

## Test

執行相關測試。

如果適合，再執行完整 test suite。

## Run

需要時實際啟動 application 或 API 驗證。

## Fix

如果測試失敗：

先找 root cause。

不要：

* 隨便加 workaround
* 關掉測試
* skip test
* 修改測試來配合錯誤實作

## Review

確認：

* 是否符合需求
* 是否破壞既有功能
* 是否符合 architecture
* 是否有不必要修改
* 是否需要 migration
* 是否需要新增測試

## Report

完成後報告：

1. 修改了什麼
2. 為什麼這樣修改
3. 修改哪些檔案
4. 執行了哪些測試
5. 測試結果
6. 是否有已知問題
7. 是否有需要使用者決定的事項

然後停止。

不要自行開始下一個 Task。

---

# 20. One Task at a Time

一次只處理一個明確 Task。

不要收到：

「建立 backend」

就自行完成：

* backend
* frontend
* database
* authentication
* scheduler
* Docker
* deployment

應拆成多個 Task。

如果目前 Task 已完成：

**停止並等待使用者下達下一個 Task。**

---

# 21. File Modification Rules

修改前先確認：

* 目前 branch
* git status
* 相關檔案
* 是否存在未提交的使用者修改

如果發現使用者已有未提交修改：

不要覆蓋或重置。

不要執行：

* `git reset --hard`
* `git checkout --`
* 大範圍刪除
* destructive commands

除非使用者明確要求。

只修改目前 Task 所需要的檔案。

---

# 22. Git Rules

Agent：

* 不自動 commit
* 不自動 push
* 不修改 commit history

完成 Task 後只提供：

* 修改摘要
* 測試結果
* 建議 commit message（如果適合）

Git commit 由使用者決定。

---

# 23. Important Decision Rule

以下事情不能擅自決定：

* 更換 framework
* 更換 database
* 更換 ORM
* 更換 package manager
* 大幅修改 architecture
* 修改核心 domain model
* 改變 scheduling semantics
* 改變 Hard Constraint 定義
* 刪除既有功能
* 大幅增加 scope

遇到上述情況：

先向使用者說明：

1. 現況
2. 問題
3. 建議方案
4. 影響

等待使用者決定。

---

# 24. Code Quality Philosophy

本專案是學習與作品集專案。

因此：

**不要追求最少程式碼，而要追求容易理解、容易測試、容易說明。**

優先：

* explicit over clever
* simple over complex
* readable over compressed
* testable over convenient
* maintainable over premature optimization

不要為了展示技術而加入不必要的設計模式。

---

# 25. Definition of Done

一個 Task 只有在以下條件滿足時才算完成：

* 功能符合需求
* 相關測試已建立或更新
* 測試通過
* 沒有明顯 regression
* architecture 沒有被破壞
* 沒有不必要的檔案修改
* migration 已處理（如果需要）
* error handling 合理
* code 可讀
* Agent 已回報結果

完成後停止，不自行開始下一項工作。

---

# 26. Current Development Priority

依照目前專案階段，優先順序：

1. Project Skeleton
2. Backend Foundation
3. Frontend Foundation
4. Database Schema
5. Alembic Migration
6. Authentication / RBAC
7. CRUD
8. Scheduling Domain Model
9. Hard Constraints
10. Greedy Scheduler
11. Backtracking Scheduler
12. Soft Constraints
13. Optimization
14. Conflict Explanation
15. Timetable UI
16. Manual Adjustment
17. Schedule Version / Publish
18. Tests
19. Docker
20. Documentation / README

除非使用者明確要求，不要跳過基礎架構直接建立後期功能。

---

# 27. Final Rule

Agent 是：

**Implementation Partner**

不是：

**Autonomous Project Manager**

使用者負責：

* 需求
* 優先順序
* 架構重大決策
* Domain semantics
* 最終接受標準

Agent 負責：

* 分析
* 實作
* 測試
* Debug
* 技術建議

如果不確定：

**不要猜。**

如果只是一般 implementation detail：

**可以自行做合理決定。**

如果會影響產品需求、domain semantics 或 architecture：

**先詢問使用者。**
