# 國小智慧排課系統 Elementary School Timetable System

[![CI](https://github.com/aaachun18/elementary-school-timetable/actions/workflows/ci.yml/badge.svg)](https://github.com/aaachun18/elementary-school-timetable/actions/workflows/ci.yml)

## 專案簡介

這是一個**約束滿足問題(Constraint Satisfaction Problem, CSP)的建模與求解專案**,不是一套 CRUD 練習。核心是 `scheduling_engine/`——一個完全獨立於 Web 框架與資料庫的排課引擎:輸入這學期參與排課的教師、他們的不可排時段與節數上下限,各年級可排的節次,班級的每週授課節數需求、指定教師與指定教室,輸出一份滿足所有 Hard Constraint 的課表;當排不出來的時候,輸出的是一份講得出具體原因的失敗報告,而不是一句「排不出來」。FastAPI、PostgreSQL、React 前端,是把這個求解引擎包裝成可操作系統所需要的基礎設施。

📄 文件:[系統設計文件 `docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md)(架構決策、演算法、已知限制)・[面試示範腳本 `docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)(5–8 分鐘現場操作流程)

## 快速開始

最快的方式是用 Docker 一次啟動資料庫、後端、前端(需要先依下方「1. 設定環境變數」建立 `.env`):

```bash
docker compose --profile full up --build -d
```

啟動後打開 `http://localhost:5173`。第一次使用需要先建立系統管理員帳號(見「8. 建立第一個系統管理員帳號」),或直接灌入示範資料(見「9.(可選)灌入示範資料」)。停止時執行 `docker compose --profile full down`(⚠️ 不要加 `-v`,會刪除資料庫資料)。

不用 Docker、在本機開發的完整步驟見下方「安裝與啟動」;執行測試見「測試」。

## 功能特色

- **三種角色、依學校隔離**:`系統管理員`(ADMIN)只管理學校與帳號——建立學校、建立/停用教學組長與一般老師帳號、把帳號綁到學校;`教學組長`(COORDINATOR)負責自己學校的全部排課工作,也能建立/停用自己學校的一般老師帳號;`一般老師`(TEACHER)唯讀,只看得到自己學校已發布的課表。教師、科目、教室、時段、學年度、年級、班級、排課需求與排課紀錄都屬於某一所學校,後端每個查詢都依登入者的學校過濾,別校的資料一律當成不存在(404/422);建立一般老師帳號時一併建立該教師。
- **開始排課(精靈)**:教學組長在一個頁面依序完成——輸入學年度、選學期(不存在就建立)→ 從啟用中的老師帳號勾選這學期參與排課的老師,設定每週最低/最高節數,並用課表格式勾選不可排時段 → 建立年級(國小一到六或國中七到九),用課表格式勾選各年級這學期可排的節次(預設:低年級星期二 0–8 節、其他天 0–5 節;中年級星期三、五 0–5 節、其他天 0–8 節;高年級星期三 0–5 節、其他天 0–8 節;國中每天 0–8 節)→ 逐一建立班級(名稱可從「一年1班/一年甲班/一年忠班…」清單搜尋選取,也可自由輸入)→ 為每個班級設定科目(只能選學校已有的科目)、每週 1–6 節、連堂樣式(依節數展開的下拉選單,可不指定)、指定老師(可不指定,系統會分給還沒超過上限的老師)與特殊教室(只能選學校已有的教室,不指定就是原班教室)→ 確認後自動排課。每一步各自儲存,可以中途離開再回來。
- **排課紀錄**:每次排課都留下一筆紀錄(草稿/已發布/已封存),依學期列出;從紀錄可檢視課表並在編輯模式手動修改,也能發布、取消發布、複製成新草稿、刪除、設定固定時段與重新排課。指定特殊教室的課在課表上註記教室名稱,原班教室不顯示。
- **排課引擎**:自行實作 MRV(Minimum Remaining Values)候選排序、Greedy Scheduler、Backtracking Scheduler 三層演算法,涵蓋 12 條 Hard Constraint(H1–H9、H11–H13;H10 教室容量延後,見下方狀態表)。
- **Explainable Scheduling**:排課失敗時不會只回一句「排不出來」——結構化的 `ConstraintViolation` 會講出具體是哪個老師、哪個限制、建議去哪個畫面修正(例如「開始排課」的教師設定或年級節次那一步);另外有八類**靜態可行性預檢**(教師工作量超標、可用時段不足、停用狀態衝突、零候選教師、固定時段不可能成立、連堂組合不可能成立、教室課數超過教學時段、年級開放節次不足),不需要跑一次搜尋就能直接證明無解。
- **連堂組合**:排課需求可設定連堂樣式(例如自然每週 3 節設為 `2+1`:一組 2 節連堂加 1 節,每個數字是不同天),自動排課會把同一組排在同一天相鄰的教學時段(不跨午休)、同一位教師與教室,不同組排在不同天;不可能成立的設定會在排課前指出是哪個需求、哪一組;已儲存的課表若連堂被拆開或兩組排在同一天,衝突檢查會指出;手動移動、對調與換教師時整組一起動。課表上同一組的各格以左緣細條連在一起。
- **固定時段**:可以在排課紀錄把某堂課固定在指定時段,自動排課一定把它排在那裡;固定在非教學時段、年級沒開放的節次、指定教師在該時段不可排課、同班或同一位教師有兩堂課固定在同一時段等不可能成立的情況,會在排課前就指出是哪一堂課、哪個時段。
- **排課紀錄(v3)**:每筆排課紀錄各自保存一整份排課設定(參與教師、節數、不可排時段、年級可排節次、科目需求)與課表,狀態為「尚未排課 / 自動排課 / 手動排課 / 複製自編號 x」,編號全校流水、新的排最上面,每列可寫備註。只有「尚未排課」的紀錄能修改設定與自動排課;要改設定請「複製此次排課設定」。課表不會被直接修改:「手動編輯課表」會建立暫存副本,「儲存課表」時手動排課紀錄直接更新,其他(含已發布)另存成新的手動排課紀錄。「複製此課表」可複製到同學年度任一學期,複製的課表在手動編輯時可以換教師。「發布此課表」後同學期原本發布的紀錄會改回未發布,每學期最多一筆已發布,一般老師只看得到已發布的課表。
- **檢查衝突**:教學組長在課表頁可一鍵檢查目前課表是否違反任何排課規則(衝堂、不可排課時段、未參與本學期的老師、年級沒開放的節次、不在指定教室、固定時段、連堂等;教師低於最低每週節數、指定了教室卻沒有教室時列為警告,不影響課表是否合法),結果以中文句子分類列出、相同問題合併計次,並可點「在課表中查看」直接切換到對應的班級/老師課表並標示該格。
- **課表編輯(移動、對調、換教師、換教室、補排,含衝突預覽)**:在草稿版本的課表開啟編輯模式,以點選或拖拉把課程移到其他節次、或與另一堂課對調;以「一門課」為單位換教師;更改已排課的教室;把排課後才新增的需求拖進課表補排。儲存前一律先預覽這次異動會新增與解決哪些問題(以「問題身分」比對,同一個問題只是換了位置不會被誤判為解決)。所有確認對話框都可用鍵盤操作。
- **首頁儀表板(依角色)**:教學組長登入後先看到目前學期與已發布版本、最新草稿的錯誤/警告/未排入課程數、學校資料數量與缺漏(例如沒有導師教室的班級),上方三張入口卡片(開始排課、排課紀錄、學校資料)各附一行目前狀況;一般老師只看到已發布課表的資訊與前往課表的入口;系統管理員直接進入學校管理。

## 功能展示

完整的操作流程與每一步的預期畫面,見 [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)。示範中的「換教師」會改到學期共用的排課需求,每輪示範後用 `scripts/reset_demo_requirements.ps1` 重置(見下方「重置示範資料」)。

## 畫面截圖

> Task 98 起排課流程改為「開始排課」精靈與「排課紀錄」,以下截圖拍攝於改版前,課表頁的檢查衝突、編輯模式、換教師、連堂拖曳與未排入課程的操作仍相同;精靈與排課紀錄的截圖待補。

| 截圖 | 說明 |
|---|---|
| ![失敗診斷](docs/images/failure-diagnostics.png) | 排課失敗診斷:具體列出每堂課失敗原因與建議修正頁面連結,而非單純回報失敗。 |
| ![課表檢視](docs/images/timetable-view.png) | 課表:依班級/教師/教室切換視角,含非教學時段顯示。 |
| ![檢查衝突結果](docs/images/conflict-check.png) | 檢查衝突:問題依類型分組並合併計次,「在課表中查看」以琥珀色框定位到課表格子。 |
| ![課表編輯模式的異動預覽](docs/images/timetable-edit.png) | 課表編輯模式:拖曳課程後先預覽這次異動會新增或解決哪些問題,確認後才儲存;候選格以淡綠/淡紅標示。 |
| ![換教師面板與預覽](docs/images/reassign-teacher.png) | 換教師:以一門課為單位換人,預覽受影響的課堂數、新增與解決的問題,以及影響範圍。 |
| ![發布版本的確認對話框](docs/images/publish-switch.png) | 版本發布:發布新版本時,目前生效的版本自動封存,每學期隨時只有一個已發布版本。 |
| ![連堂整組拖曳](docs/images/block-drag.png) | 連堂整組拖曳:同一組連堂以左緣細條相連,拖曳任一節時框出整組會落在的格子。 |
| ![未排入課程](docs/images/unscheduled-lessons.png) | 排課後新增需求:未排入的課程依班級列在課表上方,可拖曳或點選放入,連堂整組一起放入並先預覽 |

## 架構

```mermaid
flowchart TB
    subgraph Client["前端 — frontend/(階段 A + 階段 B,已完成)"]
        React["React / TypeScript / Vite<br/>開始排課精靈 / 排課紀錄 / 課表 /<br/>學校資料 / 帳號管理 / 學校管理<br/>依角色顯示與導向"]
    end

    subgraph API["API Layer — backend/app/routers/"]
        FastAPI["FastAPI Routers<br/>/api/v1/*<br/>JWT Auth + RBAC"]
    end

    subgraph Service["Service Layer — backend/app/services/"]
        SVC["業務邏輯 / Session 管理<br/>ORM ↔ Domain Dataclass 轉換<br/>例外分類與轉譯"]
    end

    subgraph Engine["Scheduling Engine — scheduling_engine/(框架獨立)"]
        Domain["Domain Dataclasses<br/>LessonAssignment / SchedulingResources"]
        Static["Static Feasibility Checks<br/>(工作量 / 可用時段 / 停用狀態 /<br/>教室 / 年級節次 ...)"]
        Constraints["Constraint Engine<br/>H1–H9, H11–H13"]
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
    SCHOOL ||--o{ USER : "教學組長 / 一般老師"
    SCHOOL ||--o{ TEACHER : "有"
    SCHOOL ||--o{ ACADEMIC_YEAR : "有"
    SCHOOL ||--o{ GRADE : "有"
    SCHOOL ||--o{ SUBJECT : "有"
    SCHOOL ||--o{ ROOM : "有"
    SCHOOL ||--o{ TIME_SLOT : "有"
    USER |o--o| TEACHER : "一般老師帳號 = 教師"
    ACADEMIC_YEAR ||--o{ SEMESTER : "有"
    SEMESTER ||--o{ SEMESTER_TEACHER : "參與排課的教師"
    TEACHER ||--o{ SEMESTER_TEACHER : "參與"
    SEMESTER_TEACHER ||--o{ SEMESTER_TEACHER_UNAVAILABILITY : "不可排時段"
    SEMESTER ||--o{ SEMESTER_GRADE_TIME_SLOT : "年級可排節次"
    GRADE ||--o{ SEMESTER_GRADE_TIME_SLOT : "開放"
    SEMESTER ||--o{ CLASS_SUBJECT_REQUIREMENT : "有"
    SEMESTER ||--o{ SCHEDULE_VERSION : "有(排課紀錄)"
    GRADE ||--o{ CLASS_GROUP : "有"
    ROOM |o--o{ CLASS_GROUP : "導師教室(原班教室,選填)"
    CLASS_GROUP ||--o{ CLASS_SUBJECT_REQUIREMENT : "有"
    SUBJECT ||--o{ CLASS_SUBJECT_REQUIREMENT : "有"
    TEACHER |o--o{ CLASS_SUBJECT_REQUIREMENT : "指定教師(選填)"
    ROOM |o--o{ CLASS_SUBJECT_REQUIREMENT : "指定特殊教室(選填)"
    CLASS_SUBJECT_REQUIREMENT ||--o{ LESSON : "產生(diff-sync)"
    LESSON ||--o{ SCHEDULE : "在某版本中被排入"
    SCHEDULE_VERSION ||--o{ SCHEDULE : "包含"
    TEACHER |o--o{ SCHEDULE : "被指派(選填)"
    TIME_SLOT |o--o{ SCHEDULE : "被指派(選填)"
    ROOM |o--o{ SCHEDULE : "被指派(選填)"

    USER {
        int id PK
        string username
        string role
        int school_id FK
    }
    SEMESTER_TEACHER {
        int id PK
        int semester_id FK
        int teacher_id FK
        int min_weekly_periods
        int max_weekly_periods
    }
    CLASS_SUBJECT_REQUIREMENT {
        int id PK
        int semester_id FK
        int class_id FK
        int subject_id FK
        int weekly_periods
        int required_teacher_id FK
        int required_room_id FK
        string lesson_pattern
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
```

> 圖中 `CLASS_GROUP` 對應程式碼裡的 `Class`(班級)——`CLASS` 是 Mermaid erDiagram 語法保留字。學期、班級、需求、課程與排課結果沒有自己的 `school_id`,而是經由學年度/年級/學期往上找到學校(`backend/app/services/school_scope.py`)。已停用但保留資料的欄位與表(`teacher_subjects`、`teacher_availabilities`、`teachers.min/max_weekly_periods`、`rooms.room_type`、`class_subject_requirements.required_room_type`)未畫出。完整欄位與設計決策見 `docs/SYSTEM_DESIGN.md` 第 4 節。

## 排課演算法摘要

**MRV → Greedy → Backtracking** 三層分工:MRV 排序決定「先處理候選最少的課」;Greedy 依序選第一個可行候選,選完不回頭,快但可能卡死;Backtracking 候選產生邏輯與 Greedy 共用,差別是沒有候選時會撤回前一堂課的選擇再試一次。完整推導(含 H7/H8 為什麼一個永遠整批驗證、一個可以即時過濾)見 `docs/SYSTEM_DESIGN.md` 第 5 節。

### Hard Constraint 實作狀態

| # | 名稱 | 狀態 |
|---|------|------|
| H1 | Teacher Conflict | ✅ 已做 |
| H2 | Class Conflict | ✅ 已做 |
| H3 | Room Conflict | ✅ 已做 |
| H4 | Teacher Availability | ✅ 已做 |
| H5 | Teacher Participation(Task 98 起取代任教資格:只有參與本學期排課的老師能授課) | ✅ 已做 |
| H6 | Required Teacher | ✅ 已做 |
| H7 | Weekly Subject Requirement | ✅ 已做(僅整批驗證) |
| H8 | Teacher Maximum Workload | ✅ 已做(Greedy 整批 / Backtracking 即時) |
| H9 | Required Room(Task 98 起取代教室類型:指定了特殊教室就必須在那間上課) | ✅ 已做 |
| H10 | Room Capacity | ⏸️ **延後**(`Room.capacity` 欄位已預留,Constraint 未實作) |
| H11 | Non-teaching Period | ✅ 已做 |
| H12 | Active Status | ✅ 已做 |
| H13 | Grade Time Slots(Task 98:班級只能排在所屬年級這學期開放的節次) | ✅ 已做 |

13 條 Hard Constraint 中 12 條已實作,H10 是唯一延後項目;固定時段與連堂組合也是引擎保證的規則(以定義域實作,不在 H 編號內)。各條狀態的完整說明、`ConstraintViolation` 共同格式、三種搜尋層級失敗類型、六類靜態可行性預檢,見 `docs/SYSTEM_DESIGN.md` 第 5、6 節。

## 安裝與啟動

### 前置需求

- Python 3.13
- Node.js 22.12 以上或 24.x(Vite 8 與 Vitest 5 的需求;開發與 CI 用的是 24)
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

### 8. 建立第一個系統管理員帳號

`POST /api/v1/auth/register` **只有在系統內還沒有任何使用者時,才允許不登入直接呼叫**,用來建立第一個帳號;這個帳號**一律是系統管理員(`ADMIN`)**,不論請求裡的 `role` 填什麼。系統內一旦已有任何使用者,這個端點就必須由已登入的系統管理員或教學組長呼叫:沒帶 token 回 `401`,一般老師的 token 回 `403`。

建立第一個帳號(透過 `/docs` 互動式文件,或用 curl):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<your-password>", "role": "ADMIN"}'
```

**之後**:用系統管理員登入前端,先在「學校管理」建立學校,再到「帳號管理」替學校建立教學組長帳號(要選所屬學校)。教學組長登入後,到「帳號管理」建立自己學校的一般老師帳號(要填教師姓名,會一併建立教師),到「學校資料」建立科目、教室與時段,再到「開始排課」排課。帳號可以停用/啟用、重設密碼;系統管理員還能改帳號所屬的學校、刪除帳號(有教師資料的一般老師帳號請改用停用)。

### 9.(可選)灌入示範資料

```bash
# 在專案根目錄
python scripts/seed_test_data.py          # 建立示範國小
python scripts/seed_test_data.py --run    # 建立後直接自動排課
```

這個腳本直接呼叫 Service 層函式(不透過 HTTP API),建立一所可以直接排課的「示範國小」:系統管理員 `admin`(資料庫還沒有系統管理員時才建立)、教學組長 `coordinator`、一般老師 `teacher01`–`teacher08`,密碼都是 `demo-pass-123`;115 學年度第 1 學期、星期一到五第 0–8 節、科目、特殊教室(自然教室、音樂教室)與每班導師教室、一到六年級各一班、這學期的教師設定與年級可排節次、各班科目需求,以及一筆已展開課程的草稿紀錄。示範國小已存在時腳本會停止,要重來請先重設開發資料庫(開發資料可丟棄)。

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

**第一次啟動後建立系統管理員帳號**:做法與上面「8. 建立第一個系統管理員帳號」相同——後端已對外開在 `8000` 埠,直接用同一段 curl 指令,或打開 `http://127.0.0.1:8000/docs` 呼叫 `POST /api/v1/auth/register` 即可。只有資料庫內還沒有任何使用者時才能這樣匿名建立(帳號一律是 `ADMIN`);Docker 模式與本機開發流程共用同一個資料庫,若之前已經在本機建過帳號,直接用既有的帳號登入前端 `http://localhost:5173` 即可;也可以改用「9.(可選)灌入示範資料」建立示範國小與全部帳號。

**停止**:

```bash
docker compose --profile full down
```

⚠️ 不要加 `-v`——`-v` 會連同資料庫 volume 一起刪除,所有資料都會消失。

⚠️ **Docker 模式與本機開發流程(venv + `python -m uvicorn` + `npm run dev`)共用同一個 postgres 容器與 volume,資料互通;但後端與前端只能二選一啟動**,否則 `8000`(後端)與 `5173`(前端)會發生埠號衝突。切換前先停掉另一邊的後端與前端。

### 載入示範資料

`scripts/seed_test_data.py` 請在**本機的虛擬環境內**執行(與上面「9.(可選)灌入示範資料」完全相同),它會依 `.env` 的 `DATABASE_URL` 連到 Docker 對外的 `5433` 埠,寫入的就是 Docker 模式正在使用的同一個資料庫:

```bash
# 在專案根目錄、已啟用虛擬環境
python scripts/seed_test_data.py --run
```

後端 image 本身沒有包含 `scripts/` 目錄,所以不要在容器內執行。

### 重置示範資料(Task 98 之前的舊示範資料)

> 以下兩個腳本寫死了 Task 98 之前那份開發資料的學期與版本 id,只適用於那份舊資料;v3(排課設定改存在每筆排課紀錄)的 migration 之後資料表結構已改變,兩個腳本都不再適用。新的示範國小用 `seed_test_data.py` 重新建立即可。

[`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) 的「換教師」步驟會改到學期共用的排課需求(指定教師),之後同學期其他版本檢查時會出現「與指定教師不符」(已知取捨,見 `docs/SYSTEM_DESIGN.md` 第 10 節)。每輪示範後,在專案根目錄的 PowerShell 執行(需要 `postgres` 容器正在執行):

```powershell
# 試跑:結尾 ROLLBACK,不會儲存;摘要會顯示會修復幾筆
powershell -ExecutionPolicy Bypass -File scripts\reset_demo_requirements.ps1
# 確認後真正儲存
powershell -ExecutionPolicy Bypass -File scripts\reset_demo_requirements.ps1 -Commit
```

它透過 `docker compose exec -T postgres psql` 執行 `scripts/reset_demo_requirements.sql`(帳號與資料庫名稱取自容器自己的環境變數),只把指定教師改回封存版本 v4 排課列上的教師。學期與版本的 id 寫死在 SQL 裡,**只適用於開發資料庫中的這份示範資料,不是通用工具**。

示範版本建立時,自動排課還不會替沒有指定教室類型的需求排教室,所以原本沒有教室、「依教室」檢視是空的(Task 92B 起自動排課會使用班級的導師教室,見 `docs/SYSTEM_DESIGN.md` 決策 29)。`scripts/add_demo_rooms.ps1`(格式相同,預設試跑,加 `-Commit` 才寫入)會替學期 13 的每個 `[SEED]` 班級建立一間導師教室,並把各版本中沒有教室的課都排進該班的導師教室;只需執行一次,可重複執行。

## 測試

### 執行方式

**後端**(pytest,需要 PostgreSQL 與 `.env` 的 `TEST_DATABASE_URL`)——已實測確認兩種執行位置皆可正常運作(專案沒有 `pytest.ini`/`pyproject.toml` 固定其中一種):

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

**前端**(Vitest,只測純函式,不需要啟動後端或瀏覽器):

```bash
cd frontend
npm test          # 單元測試(vitest run)
npm run lint      # oxlint
npm run build     # tsc -b 型別檢查(含測試檔)+ vite build
```

CI(`.github/workflows/ci.yml`)在每次 push 與 pull request 時執行同樣的後端測試、遷移驗證,以及前端的 lint、test、build。

### 測試數量

**目前總計 1571 個測試,全數通過**(2026-10-28 實際執行確認):後端 1073 個、前端 498 個。

| 類別 | 測試數 | 執行方式 |
|---|---|---|
| Scheduling Engine(純 Python 邏輯,不碰資料庫) | 182 | `pytest tests/scheduling_engine/` |
| API / 整合測試(真實 FastAPI + PostgreSQL) | 871 | 其餘 `tests/test_*.py` |
| 前端純函式單元測試(Vitest) | 449 | `cd frontend && npm test` |

前端測試只涵蓋純函式(衝突句子合併與前後比對、定位規則、拖放規則、換教師列表、版本狀態標籤、錯誤訊息翻譯、密碼規則、節次顯示、版本刪除規則、失敗診斷句子、候選格標示、對話框鍵盤操作、連堂樣式選項、連堂分組與連接條、預覽對話框的結論與問題行、未排入課程的卡片與放入規則、指定教室提示、更改教室的選項排序與預覽文字、排課精靈的規則(年級名稱、班級名稱建議、節數檢查、時段格、版本編號)、排課紀錄排序、調整成功後的刷新規則、首頁儀表板的資料整理、設計系統的色票對比、狀態徽章語氣、停用原因與說明彈出框、首頁健康度徽章、課表檢查標籤、「在課表中查看」定位標記的顯示規則、精靈第 1 步的學期鎖定、步驟導覽只能往回與網址跳步的限制、停用確認框的影響訊息、停用班級的狀態與過濾、選擇用下拉的「請重新選擇」、被隱藏的停用科目需求、排課前檢查的阻擋問題、同名老師的帳號顯示、未排入課程時擋下發布),元件與頁面互動沒有自動化測試。

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
  constraints/        H1–H13 Hard Constraint
  algorithms/         Greedy / Backtracking / MRV
  models/             純 Python domain dataclass
frontend/
  src/
    pages/            頁面(登入、首頁、開始排課精靈、排課紀錄、課表、學校資料、帳號管理、學校管理)
    components/       共用元件(Layout、失敗診斷、確認對話框、衝突清單、課表格、換教師面板、預覽對話框等;
                      wizard/ 為開始排課的各步驟與課表格式的時段勾選對話框)
    api/              axios 呼叫層
    hooks/            共用 CRUD、資料擷取、檢查衝突、移動/對調與換教師的流程
    utils/            純函式(衝突合併與比對、定位、拖放規則等;*.test.ts 為對應的單元測試)
    constants/        錯誤訊息與違規句子的中文樣板
    styles/           Tailwind 共用樣式 token
tests/                後端測試(API 層 + scheduling_engine 子目錄)
scripts/              工具腳本(示範國小灌入;舊示範資料的重置與導師教室)
docs/                 系統設計文件、截圖
```

## 已知限制與未來規劃

- **H10 教室容量**未實作 Constraint(欄位已預留)。
- **Soft Constraints(S1–S7)** 完全未開始(教師每日負擔平衡等)。
- **版本複製有使用範圍限制**:可以把任何版本(含已發布的)複製成新草稿(`POST /api/v1/schedule-versions/{id}/copy`),但跨學期只能在同一學年內、目標學期必須還沒有排課需求,複製出的版本只能手動調整,不能重新排課(排課紀錄的複製對話框會說明這些限制)。
- **手動調整不阻擋衝突、也沒有復原**:課表編輯模式與換教師在儲存前一律預覽衝突,但衝突不會被擋下;儲存後沒有「上一步」。低階的 `PATCH /schedules/{id}` 只檢查型別、外鍵、已發布/已封存鎖定。
- **連堂的點選流程沒有整組落點預覽**:拖曳時會框出整組會落在的格子,先點選再按「移到這裡」時沒有(格子仍有可放/不可放標示,預覽也會列出整組變動)。`consecutive_limit` 已停用,由 `lesson_pattern` 取代。
- **移動與對調不會改教室**:移動與對調只改時段;要改教室請用「已選取」列的「更改教室」。
- **前端只有純函式的單元測試**:元件與頁面互動沒有自動化測試,以手動驗證為主。
- **換教師會改到整個學期共用的排課需求**:在草稿換人會同時改需求的指定教師,同學期其他版本(包含已發布的)檢查時會出現「與指定教師不符」;根治需要讓指定教師隨版本保存。
- **一般老師看到的是全校已發布課表**:帳號已與教師一對一(Task 98),但課表頁還沒有「只看自己的課」的預設篩選。
- **每學期設定沒有版本鎖定**:參與教師、不可排時段與年級節次是學期共用的設定,修改後重新檢查已發布的課表時,會依新設定判斷。
- **年級沒設定可排節次時不受限制**:精靈的「下一步」一定會為每個年級存下設定(至少一節);直接用 API 跳過時,該年級視為全部節次都可排。
- **精靈與排課紀錄頁沒有元件層級的自動化測試**:規則以純函式與後端 API 測試涵蓋,畫面以手動驗證為主。
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
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — 面試示範腳本:起始條件、逐步操作與預期畫面、常見問題的簡短回答。
- [`docs/FRONTEND_REQUIREMENTS.md`](docs/FRONTEND_REQUIREMENTS.md) — 前端需求文件:頁面範圍取捨原則、技術選型理由。
