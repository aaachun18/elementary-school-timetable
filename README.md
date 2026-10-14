# 國小智慧排課系統 Elementary School Timetable System

[![CI](https://github.com/aaachun18/elementary-school-timetable/actions/workflows/ci.yml/badge.svg)](https://github.com/aaachun18/elementary-school-timetable/actions/workflows/ci.yml)

## 專案簡介

這是一個**約束滿足問題(Constraint Satisfaction Problem, CSP)的建模與求解專案**,不是一套 CRUD 練習。核心是 `scheduling_engine/`——一個完全獨立於 Web 框架與資料庫的排課引擎:輸入教師的任教資格、可用時段、工作量上限,班級的每週授課節數需求與教室類型限制,輸出一份滿足所有 Hard Constraint 的課表;當排不出來的時候,輸出的是一份講得出具體原因的失敗報告,而不是一句「排不出來」。FastAPI、PostgreSQL、React 前端,是把這個求解引擎包裝成可操作系統所需要的基礎設施。

## 功能特色

- **排課引擎**:自行實作 MRV(Minimum Remaining Values)候選排序、Greedy Scheduler、Backtracking Scheduler 三層演算法,涵蓋 11 條 Hard Constraint(H1–H9、H11、H12;H10 教室容量延後,見下方狀態表)。
- **Explainable Scheduling**:排課失敗時不會只回一句「排不出來」——結構化的 `ConstraintViolation` 會講出具體是哪個老師、哪個限制、建議去哪個畫面修正;另外有四類**靜態可行性預檢**(教師工作量超標、可用時段不足、停用狀態衝突、零合格教師),不需要跑一次搜尋就能直接證明無解。
- **JWT 認證 + 兩種帳號角色**:`ADMIN`(完整管理權限)與 `TEACHER`(唯讀,僅能查看已發布課表;課程與排課需求也只看得到有已發布版本的學期,不能使用衝突檢查)。被已發布或已封存課表使用的排課需求不可修改或刪除,排課需求總覽會事先標示為「已鎖定」並停用操作。
- **草稿 / 已發布 / 已封存版本管理**:排課版本分 `DRAFT`/`PUBLISHED`/`ARCHIVED` 三種狀態。發布某個版本時,同學期原本的已發布版本會自動封存,每學期最多一個已發布版本;已發布版本也可以直接取消發布(改為封存),封存的版本可以再發布回來;新版本一律以草稿建立;已發布與已封存的版本都完全鎖定不可修改,教師帳號只看得到已發布版本。
- **前端完整 CRUD 與課表檢視**:9 張基礎資料表(學校/學年度/學期/年級/老師/班級/科目/教室/時段)與排課需求均可在畫面上新增、編輯、刪除;排課控制台提供「選版本 → 展開課程清單 → 自動排課 → 發布」的完整流程;課表檢視支援依班級/依教師/依教室三種視角切換。
- **前端版本管理**:排課控制台可發布草稿、取消發布(改為封存,該學期暫時沒有生效課表)、把已封存版本重新發布以切換生效版本,以及把任何版本複製成新草稿(同一學期,或同學年的其他學期);每個動作都有確認對話框說明影響,例如發布時哪個版本會被自動封存;草稿版本也可以刪除。
- **檢查衝突**:管理員在課表檢視可一鍵檢查目前課表是否違反任何排課規則(衝堂、不可排課時段、固定時段等),結果以中文句子分類列出、相同問題合併計次,並可點「在課表中查看」直接切換到對應的班級/老師課表並標示該格。
- **課表編輯(移動、對調,含衝突預覽)**:管理員可在草稿版本的課表檢視開啟編輯模式,以點選或拖拉把課程移到其他節次、或與另一堂課對調;儲存前一律先預覽這次異動會新增與解決哪些問題。
- **換教師**:管理員可在草稿版本的課表檢視以「一門課」為單位把課換給其他教師(例如處理教師離職的連鎖換人),每次都先預覽受影響的課堂數與新增、解決的衝突。

## 畫面截圖

| 截圖 | 說明 |
|---|---|
| ![基礎資料瀏覽](docs/images/data-browser.png) | 基礎資料瀏覽(老師分頁展開):CRUD 操作按鈕,以及任教資格、不可用時段的即時管理。 |
| ![排課控制台](docs/images/scheduler-success.png) | 排課控制台:三步驟流程(選版本/展開課程清單/自動排課)+ 發布為最終確定版。 |
| ![失敗診斷](docs/images/failure-diagnostics.png) | 排課失敗診斷:具體列出每堂課失敗原因與建議修正頁面連結,而非單純回報失敗。 |
| ![課表檢視](docs/images/timetable-view.png) | 課表檢視:依班級/教師/教室切換視角,含非教學時段(早自習、午餐/午休)顯示。 |

## 架構

```mermaid
flowchart TB
    subgraph Client["前端 — frontend/(階段 A + 階段 B,已完成)"]
        React["React / TypeScript / Vite<br/>6 個核心頁面(登入/基礎資料/<br/>需求總覽/排課控制台/課表/失敗診斷)<br/>含完整 CRUD 表單與角色權限控制"]
    end

    subgraph API["API Layer — backend/app/routers/"]
        FastAPI["FastAPI Routers<br/>/api/v1/*<br/>JWT Auth + RBAC"]
    end

    subgraph Service["Service Layer — backend/app/services/"]
        SVC["業務邏輯 / Session 管理<br/>ORM ↔ Domain Dataclass 轉換<br/>例外分類與轉譯"]
    end

    subgraph Engine["Scheduling Engine — scheduling_engine/(框架獨立)"]
        Domain["Domain Dataclasses<br/>LessonAssignment / SchedulingResources"]
        Static["Static Feasibility Checks<br/>(工作量 / 可用時段 / 停用狀態)"]
        Constraints["Constraint Engine<br/>H1–H9, H11, H12"]
        Algo["Greedy Scheduler<br/>Backtracking Scheduler"]
    end

    subgraph Data["Data Layer"]
        ORM["SQLAlchemy Models"]
        PG[("PostgreSQL")]
    end

    React -->|"axios + JWT(sessionStorage)"| FastAPI
    FastAPI --> SVC
    SVC -->|"組裝"| Domain
    Domain --> Static
    Static -->|"通過"| Algo
    Domain --> Constraints
    Constraints -->|"提供即時驗證"| Algo
    Algo -->|"排課結果 / 失敗原因"| SVC
    SVC --> ORM
    ORM --> PG

    style Engine fill:#f0f7ff,stroke:#4a7fc9,stroke-width:2px
```

`scheduling_engine/` 刻意獨立於 FastAPI 與 SQLAlchemy——不 import 任何一行框架程式碼,只吃/吐純 Python dataclass,原因與完整說明見 `docs/SYSTEM_DESIGN.md` 第 2 節。

## 技術棧

| 分類 | 技術 | 版本 |
|---|---|---|
| 前端框架 | React / React DOM | 19.2.8 |
| 前端語言 | TypeScript | ~6.0.2 |
| 前端建置工具 | Vite | 8.3.0 |
| 前端路由 | React Router DOM | 7.18.3 |
| HTTP 客戶端 | axios | 1.20.0 |
| CSS | Tailwind CSS | 4.3.3 |
| 前端 Lint | oxlint | 1.81.0 |
| 後端框架 | FastAPI | 0.141.1 |
| ASGI Server | uvicorn | 0.52.4 |
| 資料驗證 | Pydantic | 2.13.5 |
| ORM | SQLAlchemy | 2.0.52 |
| 資料庫遷移 | Alembic | 1.19.2 |
| 資料庫驅動 | psycopg | 3.3.5 |
| 密碼雜湊 | passlib (bcrypt) | 1.7.4 |
| JWT | python-jose | 3.5.0 |
| 測試框架 | pytest | 9.1.1 |
| 資料庫 | PostgreSQL | 16(Docker image） |

版本號直接讀自 `requirements.txt`(後端)與 `frontend/package.json`(前端,`^`/`~` 前綴皆為目前 lockfile 實際安裝的版本)。

## ER Diagram

```mermaid
erDiagram
    ACADEMIC_YEAR ||--o{ SEMESTER : "有"
    SEMESTER ||--o{ CLASS_SUBJECT_REQUIREMENT : "有"
    SEMESTER ||--o{ SCHEDULE_VERSION : "有"
    GRADE ||--o{ CLASS_GROUP : "有"
    ROOM |o--o{ CLASS_GROUP : "擔任導師班教室(選填)"
    CLASS_GROUP ||--o{ CLASS_SUBJECT_REQUIREMENT : "有"
    SUBJECT ||--o{ CLASS_SUBJECT_REQUIREMENT : "有"
    TEACHER |o--o{ CLASS_SUBJECT_REQUIREMENT : "指定教師(選填)"
    TEACHER ||--o{ TEACHER_SUBJECT : "任教資格"
    SUBJECT ||--o{ TEACHER_SUBJECT : "被授資格"
    TEACHER ||--o{ TEACHER_AVAILABILITY : "不可用時段"
    TIME_SLOT ||--o{ TEACHER_AVAILABILITY : "被標記不可用"
    CLASS_SUBJECT_REQUIREMENT ||--o{ LESSON : "產生(diff-sync)"
    LESSON ||--o{ SCHEDULE : "在某版本中被排入"
    SCHEDULE_VERSION ||--o{ SCHEDULE : "包含"
    TEACHER |o--o{ SCHEDULE : "被指派(選填)"
    TIME_SLOT |o--o{ SCHEDULE : "被指派(選填)"
    ROOM |o--o{ SCHEDULE : "被指派(選填)"

    SCHOOL {
        int id PK
        string name
        bool is_active
    }
    USER {
        int id PK
        string username
        string hashed_password
        string role
    }
    CLASS_SUBJECT_REQUIREMENT {
        int id PK
        int semester_id FK
        int class_id FK
        int subject_id FK
        int weekly_periods
        int required_teacher_id FK
        string required_room_type
        int consecutive_limit
    }
    LESSON {
        int id PK
        int class_subject_requirement_id FK
        int sequence_number
    }
    SCHEDULE_VERSION {
        int id PK
        int semester_id FK
        int version_number
        string status
    }
    SCHEDULE {
        int id PK
        int schedule_version_id FK
        int lesson_id FK
        int teacher_id FK
        int time_slot_id FK
        int room_id FK
    }
    TEACHER {
        int id PK
        string name
        bool is_active
        int min_weekly_periods
        int max_weekly_periods
    }
```

> 圖中 `CLASS_GROUP` 對應程式碼裡的 `Class`(班級)——`CLASS` 是 Mermaid erDiagram 語法保留字。完整欄位、四個非直覺設計決策的理由見 `docs/SYSTEM_DESIGN.md` 第 4 節。

## 排課演算法摘要

**MRV → Greedy → Backtracking** 三層分工:MRV 排序決定「先處理候選最少的課」;Greedy 依序選第一個可行候選,選完不回頭,快但可能卡死;Backtracking 候選產生邏輯與 Greedy 共用,差別是沒有候選時會撤回前一堂課的選擇再試一次。完整推導(含 H7/H8 為什麼一個永遠整批驗證、一個可以即時過濾)見 `docs/SYSTEM_DESIGN.md` 第 5 節。

### Hard Constraint 實作狀態

| # | 名稱 | 狀態 |
|---|------|------|
| H1 | Teacher Conflict | ✅ 已做 |
| H2 | Class Conflict | ✅ 已做 |
| H3 | Room Conflict | ✅ 已做 |
| H4 | Teacher Availability | ✅ 已做 |
| H5 | Teacher Qualification | ✅ 已做 |
| H6 | Required Teacher | ✅ 已做 |
| H7 | Weekly Subject Requirement | ✅ 已做(僅整批驗證) |
| H8 | Teacher Maximum Workload | ✅ 已做(Greedy 整批 / Backtracking 即時) |
| H9 | Room Type | ✅ 已做 |
| H10 | Room Capacity | ⏸️ **延後**(`Room.capacity` 欄位已預留,Constraint 未實作) |
| H11 | Non-teaching Period | ✅ 已做 |
| H12 | Active Status | ✅ 已做 |

12 條 Hard Constraint 中 11 條已實作,H10 是唯一延後項目。各條狀態的完整說明、`ConstraintViolation` 共同格式、三種搜尋層級失敗類型、四類靜態可行性預檢,見 `docs/SYSTEM_DESIGN.md` 第 5、6 節。

## 安裝與啟動

### 前置需求

- Python 3.13
- Node.js(建議 20+;開發時用的是 24.x)
- Docker Desktop(跑 PostgreSQL)
- Git

### 1. 設定環境變數

在專案根目錄複製 `.env.example` 為 `.env`,填入實際值(以下只列出 key,不附真實值):

```
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5433/<dbname>
SECRET_KEY=
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
TEST_DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5433/<test_dbname>
```

各欄位用途:

| 欄位 | 用途 |
|---|---|
| `DATABASE_URL` | 後端與 Alembic 連線的開發資料庫位址 |
| `SECRET_KEY` | 簽發 / 驗證 JWT 用的密鑰,請填一段夠長的隨機字串 |
| `POSTGRES_DB` | Docker 容器啟動時建立的資料庫名稱 |
| `POSTGRES_USER` | Docker 容器啟動時建立的資料庫帳號 |
| `POSTGRES_PASSWORD` | 上述帳號的密碼 |
| `TEST_DATABASE_URL` | pytest 專用的測試資料庫位址(同一個 PostgreSQL、不同資料庫名) |

填寫範例(僅供本機開發參考,請自行替換密碼與密鑰):

```
DATABASE_URL=postgresql+psycopg://timetable:timetable_pw@localhost:5433/timetable
SECRET_KEY=change-me-to-a-long-random-string
POSTGRES_DB=timetable
POSTGRES_USER=timetable
POSTGRES_PASSWORD=timetable_pw
TEST_DATABASE_URL=postgresql+psycopg://timetable:timetable_pw@localhost:5433/timetable_test
```

⚠️ **`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB` 三個都必須填值,尤其 `POSTGRES_PASSWORD` 不可為空**——留空的話 PostgreSQL 容器會拒絕初始化並反覆重啟,資料庫無法啟動(症狀與處理方式見下方「疑難排解」)。

⚠️ **`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB` 必須與 `DATABASE_URL` 裡的帳號、密碼、資料庫名一致**——`POSTGRES_*` 決定容器實際建立的帳號與資料庫,`DATABASE_URL` 則是後端拿來連線的位址,兩者不一致時後端會連線失敗(驗證錯誤或資料庫不存在)。`TEST_DATABASE_URL` 的帳號、密碼也要與上述相同。

⚠️ `POSTGRES_PASSWORD` 請避免 `@ : / # ? %` 等特殊字元,否則 Docker 模式組出的 `DATABASE_URL` 會壞掉。

`TEST_DATABASE_URL` 的資料庫名稱**必須**與 `DATABASE_URL` 不同——測試套件會對它執行 `Base.metadata.drop_all()`,兩者相同的話 `tests/conftest.py` 會直接拒絕執行。本機 PostgreSQL 預設跑在 `5433`(而非 `5432`),是因為 `docker-compose.yml` 刻意把它對應到這個 host port:為避免與本機既有的 PostgreSQL 衝突,對外使用 `5433`。

### 2. 啟動 PostgreSQL

```bash
docker compose up -d
```

### 3. 建立測試資料庫(只需一次)

`TEST_DATABASE_URL` 指到的資料庫不會自動建立,需要手動連進容器建立(`postgres` 是 `docker-compose.yml` 裡的服務名稱,`docker compose exec` 會自動帶入 `.env` 裡的帳密,不用自己再替換一次):

```bash
docker compose exec postgres psql -U <POSTGRES_USER> -d <POSTGRES_DB> -c "CREATE DATABASE <test_dbname>;"
```

（`<POSTGRES_USER>`/`<POSTGRES_DB>`/`<test_dbname>` 對應到你在 `.env` 裡填的 `POSTGRES_USER`、`POSTGRES_DB`、`TEST_DATABASE_URL` 裡的資料庫名稱。）

### 4. 安裝依賴

先在專案根目錄建立並啟用虛擬環境:

```bash
# 建立虛擬環境(只需一次)
python -m venv .venv

# 啟用 — Windows PowerShell
.venv\Scripts\Activate.ps1

# 啟用 — Windows Git Bash
source .venv/Scripts/activate

# 啟用 — macOS / Linux
source .venv/bin/activate
```

之後每次開新的終端機執行後端、遷移或測試指令前,都要先啟用虛擬環境。

```bash
# 後端(在專案根目錄、已啟用虛擬環境)
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 5. 執行資料庫遷移

⚠️ **必須在專案根目錄執行**(`alembic.ini` 的 `script_location` 是以它自己所在目錄為基準,指到 `backend/alembic`;在 `backend/` 目錄內執行會直接失敗,回報「No 'script_location' key found」):

```bash
# 在專案根目錄
alembic upgrade head
```

### 6. 啟動後端

⚠️ **必須在 `backend/` 目錄內執行**(`app.main:app` 是相對於 `backend/` 的模組路徑;在專案根目錄執行會找不到 `app` 模組):

```bash
cd backend
python -m uvicorn app.main:app --reload
```

用 `python -m uvicorn` 而不是直接執行 `uvicorn`,是因為部分 Windows 環境的應用程式控制原則會阻擋虛擬環境裡的 `uvicorn.exe` 啟動檔;透過 `python -m` 啟動則不受影響。

預設監聽 `http://127.0.0.1:8000`,API 文件見 `/docs`。

### 7. 啟動前端

```bash
cd frontend
npm run dev
```

預設監聽 `http://localhost:5173`。

### 8. 建立第一個管理員帳號

`POST /api/v1/auth/register` **只有在系統內還沒有任何使用者時,才允許不登入直接呼叫**,用來建立第一個帳號;這個帳號**一律是 `ADMIN`**,不論請求裡的 `role` 填什麼。系統內一旦已有任何使用者,這個端點就必須由已登入的 `ADMIN` 呼叫:沒帶 token 回 `401`,帶 `TEACHER` 的 token 回 `403`。

建立第一個帳號(透過 `/docs` 互動式文件,或用 curl):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<your-password>", "role": "ADMIN"}'
```

**之後新增帳號**(`ADMIN` 或 `TEACHER`):用管理員帳號登入前端,到導覽列的「帳號管理」頁面新增。同一頁也可以重設任何帳號的密碼、刪除其他帳號(不能刪除目前登入中的自己)。

（備註:不透過前端時,也可以在 `/docs` 按右上角 **Authorize** 用管理員帳號登入後呼叫 `POST /api/v1/auth/register`,或用 curl 在請求加上 `Authorization: Bearer <access_token>` 標頭。）

### 9.(可選)灌入測試資料

```bash
# 在專案根目錄
python scripts/seed_test_data.py
```

這個腳本直接呼叫 Service 層函式(不透過 HTTP API),灌入一組可以直接跑完整個「展開課程清單 → 自動排課」流程的示範資料。重複執行需要加 `--confirm` 參數清掉上一次的結果,詳見腳本內的 docstring。

## 用 Docker 一次啟動全部服務

不想在本機安裝 Python / Node 時,可以改用 Docker 同時啟動資料庫、後端、前端。只需要完成上面的「1. 設定環境變數」(`.env` 放在專案根目錄),然後在專案根目錄執行:

```bash
docker compose --profile full up --build
```

（加上 `-d` 可在背景執行。）後端與前端服務放在 `full` 這個 profile 裡,所以上面「2. 啟動 PostgreSQL」的 `docker compose up -d` 不受影響,仍然只會啟動資料庫。

| 服務 | 網址 / 埠 | 說明 |
|---|---|---|
| 前端 | `http://localhost:5173` | nginx 提供建置好的靜態檔(容器內 80 埠,對外 5173) |
| 後端 | `http://localhost:8000`(API 文件:`/docs`) | 啟動前會自動執行 `alembic upgrade head`,不需要手動遷移 |
| PostgreSQL | `localhost:5433` | 與本機開發流程使用同一個資料庫容器與 volume,資料互通 |

後端容器會沿用 `.env` 的帳號、密碼與 `SECRET_KEY`,只把資料庫位址改成容器內部的 `postgres:5432`(`.env` 裡給本機開發用的 `DATABASE_URL` 不需要修改)。

**第一次啟動後建立管理員帳號**:做法與上面「8. 建立第一個管理員帳號」相同——後端已對外開在 `8000` 埠,直接用同一段 curl 指令,或打開 `http://127.0.0.1:8000/docs` 呼叫 `POST /api/v1/auth/register` 即可。只有資料庫內還沒有任何使用者時才能這樣匿名建立(帳號一律是 `ADMIN`);Docker 模式與本機開發流程共用同一個資料庫,若之前已經在本機建過帳號,直接用既有的管理員帳號登入前端 `http://localhost:5173`,到「帳號管理」頁面新增即可。

**停止**:

```bash
docker compose --profile full down
```

⚠️ 不要加 `-v`——`-v` 會連同資料庫 volume 一起刪除,所有資料都會消失。

⚠️ **Docker 模式與本機開發流程(venv + `python -m uvicorn` + `npm run dev`)共用同一個 postgres 容器與 volume,資料互通;但後端與前端只能二選一啟動**,否則 `8000`(後端)與 `5173`(前端)會發生埠號衝突。切換前先停掉另一邊的後端與前端。

### 載入測試資料

`scripts/seed_test_data.py` 請在**本機的虛擬環境內**執行(與上面「9.(可選)灌入測試資料」完全相同),它會依 `.env` 的 `DATABASE_URL` 連到 Docker 對外的 `5433` 埠,寫入的就是 Docker 模式正在使用的同一個資料庫:

```bash
# 在專案根目錄、已啟用虛擬環境
python scripts/seed_test_data.py
```

**不要在容器內執行**:腳本會把這次灌入的資料記錄在 `scripts/.seed_manifest.json`,之後用 `--confirm` 重複執行時要靠它清掉上一次的結果;在容器內產生的這個檔案不會被保留(容器重建後就消失,本機也看不到),下一次執行時腳本找到上次灌入的資料、卻找不到紀錄檔,會因為不知道哪些資料可以安全刪除而直接拒絕執行。後端 image 本身也沒有包含 `scripts/` 目錄。

## 測試

### 執行方式

已實測確認兩種執行位置皆可正常運作(專案沒有 `pytest.ini`/`pyproject.toml` 固定其中一種):

```bash
# 方式一:在專案根目錄
pytest tests/

# 方式二:在 backend/ 目錄內
cd backend
pytest ../tests/
```

若 `pytest` 指令找不到或被系統封鎖,可改用 `python -m pytest`,參數相同:

```bash
# 在專案根目錄
python -m pytest tests/

# 在 backend/ 目錄內
python -m pytest ../tests/
```

### 測試數量

**目前總計 503 個測試,全數通過**(2026-10-14 實際執行確認):

| 類別 | 測試數 | 執行方式 |
|---|---|---|
| Scheduling Engine(純 Python 邏輯,不碰資料庫) | 73 | `pytest tests/scheduling_engine/` |
| API / 整合測試(真實 FastAPI + PostgreSQL) | 430 | 其餘 `tests/test_*.py` |

Scheduling Engine 那組測試不需要啟動 FastAPI 或連資料庫,秒級內跑完;API 測試會對 `TEST_DATABASE_URL` 指到的資料庫逐一 `create_all`/`drop_all`,耗時較長。測試策略的完整理由見 `docs/SYSTEM_DESIGN.md` 第 9 節。

## API 文件

後端啟動後,互動式 API 文件(Swagger UI)在 `http://127.0.0.1:8000/docs`,涵蓋所有端點的請求/回應格式,可直接在頁面上測試呼叫(右上角 Authorize 填入登入拿到的 JWT token)。

## 專案結構

```text
backend/
  app/
    routers/         FastAPI 路由(/api/v1/*)
    services/        業務邏輯層
    models/           SQLAlchemy ORM models
    schemas/          Pydantic schemas
    core/             安全性(JWT/密碼雜湊)、依賴注入
  alembic/            資料庫遷移腳本
scheduling_engine/    排課引擎(框架獨立)
  constraints/        H1–H12 Hard Constraint
  algorithms/         Greedy / Backtracking / MRV
  models/             純 Python domain dataclass
frontend/
  src/
    pages/            6 個核心頁面
    components/       共用元件(Layout、失敗診斷等)
    api/              axios 呼叫層
    hooks/            共用 CRUD / 資料擷取邏輯
    styles/           Tailwind 共用樣式 token
tests/                後端測試(API 層 + scheduling_engine 子目錄)
scripts/              工具腳本(測試資料灌入)
docs/                 系統設計文件、截圖
```

## 已知限制與未來規劃

- **H10 教室容量**未實作 Constraint(欄位已預留)。
- **Soft Constraints(S1–S7)** 完全未開始(教師每日負擔平衡等)。
- **版本複製有使用範圍限制**:可以把任何版本(含已發布的)複製成新草稿(`POST /api/v1/schedule-versions/{id}/copy`),但跨學期只能在同一學年內、目標學期必須還沒有排課需求,複製出的版本只能手動調整,不能重新排課(排課控制台的複製對話框會說明這些限制)。
- **手動調整課表沒有重新驗證 Hard Constraint**:`PATCH /schedules/{id}` 目前只檢查型別、外鍵、已發布/已封存鎖定。
- **`User` 帳號與 `Teacher` 網域實體沒有關聯**:`TEACHER` 角色帳號無法對應到特定一位老師,還做不到「老師只看自己的課表」。
- **`School` 沒有實際接進資料模型**:目前是隱含單一學校假設。
- **`TimeSlot.period` 跨星期一致性依賴人工維護紀律**,資料庫層級沒有強制。

完整清單(含每一項的理由)見 `docs/SYSTEM_DESIGN.md` 第 10 節。

## 疑難排解

- **Windows 上 `psycopg` 連線失敗或載入錯誤**:部分 Windows 環境的應用程式控制原則(如 WDAC)可能封鎖 `psycopg` 的 C 擴充套件,若遇到此狀況可改用 `requirements.txt` 已一併列出的 `psycopg-binary`。
- **`uvicorn.exe` 被應用程式控制原則封鎖**:改用 `python -m uvicorn app.main:app --reload`(在 `backend/` 目錄內執行),不經過 `uvicorn.exe` 啟動檔。
- **前端被改到 `5174` 埠**:前端固定使用 `5173` 埠(後端 CORS 只允許 `http://localhost:5173` 這個來源);若 `npm run dev` 顯示改用 `5174`,代表已有舊的前端程式佔用 `5173`,請先關閉舊的前端程式再重新啟動,否則所有 API 呼叫都會被 CORS 擋下。
- **`docker compose --profile full up` 出現「dependency postgres failed to start」**:這個訊息本身看不出原因,請執行 `docker compose --profile full logs postgres` 查看資料庫容器的紀錄。若看到「superuser password is not specified」,代表 `.env` 的 `POSTGRES_PASSWORD` 是空的;填入值後,先執行 `docker compose --profile full down`,再執行 `docker compose --profile full up --build -d`。⚠️ `down` 不要加 `-v`——`-v` 會連同資料庫 volume 一起刪除,所有資料都會消失。
- **Docker 啟動時顯示埠號已被使用(`port is already allocated` / `address already in use`)**:先停掉本機開發流程啟動的後端(`python -m uvicorn`)與前端(`npm run dev`);若另一個資料夾(例如原本的專案資料夾)的資料庫容器也還在跑,先到該資料夾執行 `docker compose stop`。`5173`(前端)、`8000`(後端)、`5433`(PostgreSQL)三個埠都要確認沒被佔用,再重新執行 `docker compose --profile full up --build -d`。

## 相關文件

- [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) — 系統設計文件:架構決策紀錄、除錯歷程、演算法細節、ER 圖完整版。
- [`docs/FRONTEND_REQUIREMENTS.md`](docs/FRONTEND_REQUIREMENTS.md) — 前端需求文件:頁面範圍取捨原則、技術選型理由。
