# 學校自動排課系統 School Timetable System

[![CI](https://github.com/aaachun18/elementary-school-timetable/actions/workflows/ci.yml/badge.svg)](https://github.com/aaachun18/elementary-school-timetable/actions/workflows/ci.yml)

## 專案簡介

這是一個**約束滿足問題(Constraint Satisfaction Problem, CSP)的建模與求解專案**,不是一套 CRUD 練習。核心是 `scheduling_engine/`——一個完全獨立於 Web 框架與資料庫的排課引擎:輸入一筆排課紀錄的設定——參與排課的教師、他們的不可排時段與節數上下限,各年級可排的節次,班級的每週授課節數需求、指定教師、指定教室、連堂、固定時段與共同排課——輸出一份滿足所有 Hard Constraint、再依 Soft Constraint 最佳化的課表;當排不出來的時候,輸出的是一份講得出具體原因的失敗報告,而不是一句「排不出來」。FastAPI、PostgreSQL、React 前端,是把這個求解引擎包裝成可操作系統所需要的基礎設施。

📄 文件:[系統設計文件 `docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md)(架構決策、演算法、已知限制)・[面試示範腳本 `docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)(5–8 分鐘現場操作流程)

## 快速開始

最快的方式是用 Docker 一次啟動資料庫、後端、前端(需要先依下方「1. 設定環境變數」建立 `.env`):

```bash
docker compose --profile full up --build -d
```

啟動後打開 `http://localhost:5173`(公開首頁,按「登入」進入系統;一定要用 `localhost`,後端 CORS 只允許這個來源)。第一次使用需要先建立系統管理員帳號(見「8. 建立第一個系統管理員帳號」),或直接灌入示範資料(見「9.(可選)灌入示範資料」)。停止時執行 `docker compose --profile full down`(⚠️ 不要加 `-v`,會刪除資料庫資料)。

不用 Docker、在本機開發的完整步驟見下方「安裝與啟動」;執行測試見「測試」。

## 功能特色

- **三種角色、依學校隔離**:`系統管理員`(ADMIN)只管理學校與帳號——建立學校(國小/國中/高中,自動產生年級與時段,國小另帶 10 個預設科目與各年級節數)、建立/停用教學組長與一般老師帳號、改帳號所屬學校,讀不到任何排課資料;`教學組長`(COORDINATOR)負責自己學校的全部排課工作,也能建立/停用自己學校的一般老師帳號;`一般老師`(TEACHER)唯讀,只看得到自己學校已發布的課表。所有資料都屬於某一所學校,後端每個查詢都依登入者的學校過濾,別校的資料一律當成不存在(404/422)。
- **公開首頁與登入**:`/` 是未登入也能看的系統介紹,已登入者自動導向自己的首頁;登入頁左右分割(窄螢幕只顯示表單),閒置 30 分鐘才自動登出,操作中自動換發通行證。
- **學校資料**:班級、科目、科目需求(各年級每週節數)、教室(可設定一次最多幾班同時使用)、時段五個分頁;名稱以淡灰虛線框標出,點一下即可在列內修改;班級、科目、教室可停用/啟用,停用前說明影響範圍。
- **開始排課(6 步驟精靈)**:學年度與學期 → 教師設定(勾選參與的老師、每週最低/最高節數、課表格式勾選不可排時段、指派導師)→ 年級與可排節次(預設依低/中/高年級與國中產生)→ 科目需求(連堂樣式、指定老師、指定教室、固定時段;可把連堂或教室設定一次複製到同年級各班)→ 共同排課(把幾個班的同一科合併一起上)→ 確認並排課(排課前檢查列出會擋下排課的問題)。每一步各自儲存,中途離開再回來會回到上次的步驟。
- **排課紀錄**:每次排課或複製都留下一筆紀錄,各自保存一整份設定與課表,狀態為「尚未排課 / 自動排課 / 手動排課 / 複製自編號 x」;編號 1 永遠是最新的一筆,每列可寫備註。只有「尚未排課」能改設定;要改設定請「複製此次排課設定」。每學期最多一筆已發布,發布新的一筆時舊的自動取消發布,也可以直接「取消發布」。
- **排課引擎**:自行實作前向檢查搜尋(每次排出不同課表、90 秒上限,保留 Greedy 與 Backtracking 作對照),涵蓋 15 條 Hard Constraint 中的 14 條(H10 依決定不實作,見下方狀態表),排出合法課表後再依 3 條 Soft Constraint 最佳化:國語、數學排在第 1–2 節;體育避開第 1、4、5 節;國小全日的最後一節排活動性課程。
- **Explainable Scheduling**:排課失敗時不會只回一句「排不出來」——結構化的 `ConstraintViolation` 會講出具體是哪個老師、哪個限制、建議去精靈的哪一步修正;九類**靜態可行性預檢**(教師工作量超標、可用時段不足、停用狀態、零候選教師、固定時段不可能成立、連堂組合不可能成立、教室課數超過可用時段、年級開放節次不足、共同排課的固定時段矛盾)不需要跑一次搜尋就能直接證明無解。
- **連堂、固定時段與共同排課**:連堂樣式(例如自然每週 3 節設為 `2+1`)自動排在同一天相鄰的教學時段、不跨午休,不同組不同天;固定時段的課一定排在那裡;共同排課的各班一定排在同一時段,課表上列出全部老師。
- **手動調整(先預覽、每次自動重新檢查)**:手動編輯會建立暫存副本,儲存時才落地。選取或拖曳一堂課時,課表標出可放(淺綠)、衝突(淺紅)與可對調(淺藍)的格子;依班級、依教師檢視中拖到有課的格子就是對調;連堂可以拖到任何放得下的位置,擋路的課會換到連堂空出來的時段。選取一堂課後可直接更換教師(整門課一起換,同時更新科目需求)與更換教室。把課拖到「移出課表」框可以先移出課表(連堂整組一起),它會以「未排入課程」卡片列在課表上方,之後可拖曳放回。所有確認對話框都可用鍵盤操作。
- **檢查衝突**:課表一打開就自動檢查,每次調整後重新檢查;結果以中文句子分類列出、相同問題合併計次,並可點「在課表中查看」直接切換到對應的班級/老師課表並標示該格。依教室檢視列出共用同一間教室的所有班級,超過教室容納的班數時頁面上方顯示錯誤。
- **帳號管理**:序號、老師依姓名筆畫排序;搜尋帳號、姓名或身分證字號(按放大鏡或 Enter 才篩選,✕ 或「顯示全部」回到全部);系統管理員另可依角色篩選。同校同名的老師必須填身分證字號,畫面上以帳號區分。
- **易用性**:所有教師/班級下拉選單都能打字搜尋;科目一律依「國語、英、數、生活、美勞、自然、社會、藝術、音樂、健康、體育、綜合」排序;設計 token 的文字對比由測試檢查。
- **後台首頁(依角色)**:教學組長看到目前學期、最新紀錄的檢查結果與學校資料缺漏,以及開始排課、排課紀錄、學校資料三張入口卡片;一般老師只看到已發布課表的資訊與前往課表的入口;系統管理員直接進入學校管理。

## 功能展示

完整的操作流程與每一步的預期畫面,見 [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)(使用 `scripts/seed_test_data.py` 建立的示範國小)。

## 畫面截圖

| 截圖 | 說明 |
|---|---|
| ![公開首頁](docs/images/landing.png) | 公開首頁(`/`):未登入可看,主視覺、四張功能卡片與登入入口;已登入者自動導向後台首頁。 |
| ![登入頁](docs/images/login.png) | 登入頁(寬度 ≥768px):左側品牌區(主色深淺漸層、淡課表格線與右上柔光、三個重點、迷你課表插圖),右側「歡迎回來」表單。 |
| ![窄螢幕登入頁](docs/images/login-mobile.png) | 登入頁(寬度 <768px):隱藏品牌區,只顯示系統名稱、表單與「返回首頁」。 |

### 改版前的畫面(僅供參考)

> 以下截圖拍攝於 Task 98 改版前(2026-10-12–19):當時的頁面是「排課控制台」「課表檢視」、帳號是 `ADMIN`、版本是草稿/已發布/已封存,資料帶 `[SEED]` 前綴。概念(失敗診斷、衝突清單、預覽、連堂、未排入課程)仍相同,但畫面、按鈕與狀態名稱已經不同,待重新拍攝。

| 截圖 | 說明 |
|---|---|
| ![失敗診斷](docs/images/failure-diagnostics.png) | 排課失敗診斷:具體列出每堂課失敗原因與建議修正的位置,而非單純回報失敗。 |
| ![課表檢視](docs/images/timetable-view.png) | 課表:依班級/教師/教室切換視角,含非教學時段顯示。 |
| ![檢查衝突結果](docs/images/conflict-check.png) | 檢查衝突:問題依類型分組並合併計次,「在課表中查看」以琥珀色框定位到課表格子(目前改為自動檢查)。 |
| ![課表編輯模式的異動預覽](docs/images/timetable-edit.png) | 手動調整:拖曳課程後先預覽這次異動會新增或解決哪些問題,確認後才儲存(目前另有淺藍的「可對調」標示)。 |
| ![換教師面板與預覽](docs/images/reassign-teacher.png) | 換教師:以一門課為單位換人,預覽受影響的課堂數與新增、解決的問題。 |
| ![發布版本的確認對話框](docs/images/publish-switch.png) | 發布:每學期隨時只有一筆已發布(目前舊的一筆改回原本的狀態,不再有「已封存」)。 |
| ![連堂整組拖曳](docs/images/block-drag.png) | 連堂整組拖曳:同一組連堂以左緣細條相連,拖曳任一節時框出整組會落在的格子。 |
| ![未排入課程](docs/images/unscheduled-lessons.png) | 未排入課程:移出課表的課依班級列在課表上方,可拖曳或點選放入,連堂整組一起放入並先預覽。 |

## 架構

```mermaid
flowchart TB
    subgraph Client["前端 — frontend/"]
        React["React / TypeScript / Vite<br/>公開首頁 / 登入 / 後台首頁 / 學校資料 /<br/>開始排課精靈 / 排課紀錄 / 課表 /<br/>帳號管理 / 學校管理"]
    end

    subgraph API["API Layer — backend/app/routers/"]
        FastAPI["FastAPI Routers<br/>/api/v1/*<br/>JWT Auth + RBAC(三種角色)"]
    end

    subgraph Service["Service Layer — backend/app/services/"]
        SVC["業務邏輯 / Session 管理<br/>依學校隔離 / 暫存副本<br/>ORM ↔ Domain Dataclass 轉換<br/>例外分類與轉譯"]
    end

    subgraph Engine["Scheduling Engine — scheduling_engine/(框架獨立)"]
        Domain["Domain Dataclasses<br/>LessonAssignment / SchedulingResources"]
        Static["Static Feasibility Checks<br/>(工作量 / 可用時段 / 停用狀態 / 固定時段 /<br/>連堂 / 教室 / 年級節次 / 共同排課)"]
        Constraints["Constraint Engine<br/>H1–H9, H11–H15"]
        Algo["Forward Checking Scheduler<br/>(Greedy / Backtracking 作為對照)"]
        Soft["Soft Constraint Optimizer<br/>S8 / S9 / S10"]
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
    Algo -->|"合法課表"| Soft
    Constraints -->|"每一步都不得違反"| Soft
    Soft -->|"排課結果 / 失敗原因"| SVC
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
    SCHOOL ||--o{ SCHEDULE_VERSION : "有(排課紀錄)"
    USER |o--o| TEACHER : "一般老師帳號 = 教師"
    ACADEMIC_YEAR ||--o{ SEMESTER : "有"
    SEMESTER ||--o{ SCHEDULE_VERSION : "有"
    GRADE ||--o{ CLASS_GROUP : "有"
    GRADE ||--o{ GRADE_SUBJECT_REQUIREMENT : "學校層級的年級節數"
    SUBJECT ||--o{ GRADE_SUBJECT_REQUIREMENT : "有"
    SCHEDULE_VERSION ||--o{ SEMESTER_TEACHER : "參與排課的教師"
    TEACHER ||--o{ SEMESTER_TEACHER : "參與"
    CLASS_GROUP |o--o{ SEMESTER_TEACHER : "導師班級(選填)"
    SEMESTER_TEACHER ||--o{ SEMESTER_TEACHER_UNAVAILABILITY : "不可排時段"
    SCHEDULE_VERSION ||--o{ SEMESTER_GRADE_TIME_SLOT : "年級可排節次"
    GRADE ||--o{ SEMESTER_GRADE_TIME_SLOT : "開放"
    SCHEDULE_VERSION ||--o{ CLASS_SUBJECT_REQUIREMENT : "科目需求"
    CLASS_GROUP ||--o{ CLASS_SUBJECT_REQUIREMENT : "有"
    SUBJECT ||--o{ CLASS_SUBJECT_REQUIREMENT : "有"
    TEACHER |o--o{ CLASS_SUBJECT_REQUIREMENT : "指定教師(選填)"
    ROOM |o--o{ CLASS_SUBJECT_REQUIREMENT : "指定教室(選填)"
    CLASS_SUBJECT_REQUIREMENT ||--o{ LESSON : "產生(diff-sync)"
    SCHEDULE_VERSION ||--o{ COMBINED_LESSON : "共同排課"
    COMBINED_LESSON ||--o{ COMBINED_LESSON_MEMBER : "合併的各班需求"
    CLASS_SUBJECT_REQUIREMENT ||--o{ COMBINED_LESSON_MEMBER : "被合併"
    LESSON ||--o{ SCHEDULE : "被排入"
    SCHEDULE_VERSION ||--o{ SCHEDULE : "包含"
    TEACHER |o--o{ SCHEDULE : "被指派(選填)"
    TIME_SLOT |o--o{ SCHEDULE : "被指派(選填)"
    ROOM |o--o{ SCHEDULE : "被指派(選填)"

    SCHOOL {
        int id PK
        string name
        string school_type
    }
    USER {
        int id PK
        string username
        string role
        bool is_active
        int school_id FK
    }
    TEACHER {
        int id PK
        int school_id FK
        string name
        int user_id FK
        string national_id
        bool is_active
    }
    ROOM {
        int id PK
        int school_id FK
        string name
        int max_classes
        bool is_active
    }
    SCHEDULE_VERSION {
        int id PK
        int school_id FK
        int semester_id FK
        int version_number
        string status
        bool is_published
        int copied_from_number
        int editing_source_id FK
        string note
    }
    SEMESTER_TEACHER {
        int id PK
        int schedule_version_id FK
        int teacher_id FK
        int min_weekly_periods
        int max_weekly_periods
        int homeroom_class_id FK
    }
    CLASS_SUBJECT_REQUIREMENT {
        int id PK
        int schedule_version_id FK
        int class_id FK
        int subject_id FK
        int weekly_periods
        int required_teacher_id FK
        int required_room_id FK
        string lesson_pattern
    }
    LESSON {
        int id PK
        int class_subject_requirement_id FK
        int sequence_number
        int fixed_time_slot_id FK
        int block_no
        int block_seq
    }
    COMBINED_LESSON {
        int id PK
        int schedule_version_id FK
        int merged_count
        string block_nos
        int room_id FK
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

> 圖中的 `CLASS_GROUP` 對應程式碼裡的 `Class`(班級)——`CLASS` 是 Mermaid erDiagram 語法的保留字,拿來當實體名稱會導致解析失敗。學期、班級、需求、課程與排課結果沒有自己的 `school_id`,而是經由學年度/年級/紀錄往上找到學校(`backend/app/services/school_scope.py`)。`status` 只接受 `NOT_SCHEDULED`/`AUTO`/`MANUAL`/`COPIED`/`EDITING`(資料庫 CheckConstraint),`EDITING` 沒有編號、必有 `editing_source_id`;`COPIED` 必有 `copied_from_number`。已停用但保留資料的表與欄位(`teacher_subjects`、`teacher_availabilities`、`teachers.min/max_weekly_periods`、`rooms.room_type`、`class_subject_requirements.required_room_type`、`consecutive_limit`)未畫出。完整欄位與設計決策見 `docs/SYSTEM_DESIGN.md` 第 0、4 節。

## 排課演算法摘要

1. **靜態可行性預檢**:九類加總/比對就能證明無解的問題,命中就直接回報,不進入搜尋。
2. **前向檢查搜尋**(自動排課使用):每一步重新挑剩下候選最少的排課單位(一節課或一整組連堂),放下後立即刪掉其他單位因此不能用的候選,有單位沒有候選就馬上換;一輪撤回太多次就依 Luby 數列換一個順序重來。同樣的輸入與 seed 一定得到同樣的課表;服務每次用新的 seed,所以每次排出的課表不同。排完再以所有 Hard Constraint 整份驗證一次,不通過就什麼都不寫入。
3. **Soft Constraint 最佳化**:在合法課表上爬山,每一步都保持所有 Hard Constraint 成立,只在總分提高時接受(S8 國語數學第 1–2 節、S9 體育避開第 1、4、5 節、S10 國小全日最後一節排活動性課程)。

**導師規則(2026-11-12,見 `docs/SYSTEM_DESIGN.md` 決策 55,`algorithms/homeroom.py`)**:沒有指定教師的課,自動排課不會分給「別班的導師」——只要有任何一份滿足所有 Hard Constraint 的課表做得到;做不到時(例如非導師的老師節數上限不夠),改為讓導師教別班的節數(跨班節數)盡量少。指定教師(H6)是學校自己的決定,一律不算跨班;導師教自己班、或不是導師的老師,都不受影響。

Greedy 與 Backtracking 保留作為對照,完整推導(含 H7/H8 為什麼一個永遠整批驗證、一個可以即時過濾)見 `docs/SYSTEM_DESIGN.md` 第 5 節。

### Hard Constraint 實作狀態

| # | 名稱 | 狀態 |
|---|------|------|
| H1 | Teacher Conflict(同一合併節的老師可同時在多班) | ✅ 已做 |
| H2 | Class Conflict | ✅ 已做 |
| H3 | Room Conflict(教室同時段最多「一次最多幾班」班,合併節算 1 班) | ✅ 已做 |
| H4 | Teacher Availability | ✅ 已做 |
| H5 | Teacher Participation(只有參與這筆排課紀錄的老師能授課,取代任教資格) | ✅ 已做 |
| H6 | Required Teacher | ✅ 已做 |
| H7 | Weekly Subject Requirement | ✅ 已做(僅整批驗證) |
| H8 | Teacher Maximum Workload | ✅ 已做 |
| H9 | Required Room(指定了教室就必須在那間上課,取代教室類型) | ✅ 已做 |
| H10 | Room Capacity | ➖ 不實作(教室容量欄位已刪除,改以 H3 的「一次最多幾班」表達) |
| H11 | Non-teaching Period | ✅ 已做 |
| H12 | Active Status | ✅ 已做 |
| H13 | Grade Time Slots(班級只能排在所屬年級開放的節次) | ✅ 已做 |
| H14 | Combined Lesson Split(共同排課的各班必須同一時段) | ✅ 已做 |
| H15 | Requirement Mixed Teachers(同一班同一科目只能一位老師) | ✅ 已做 |

固定時段與連堂組合也是引擎保證的規則(以定義域實作,不在 H 編號內);教師低於最低每週節數只列為警告。各條的完整說明、`ConstraintViolation` 共同格式、失敗類型與靜態預檢,見 `docs/SYSTEM_DESIGN.md` 第 5、6 節。

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

**之後**:用系統管理員登入前端,先在「學校管理」建立學校,再到「帳號管理」替學校建立教學組長帳號(要選所屬學校)。教學組長登入後,到「帳號管理」建立自己學校的一般老師帳號(要填教師姓名,會一併建立教師),到「學校資料」補齊班級、科目、教室,並調整時段的標籤與是否可排課(建立學校時已自動產生年級與時段,國小另帶 10 個預設科目與各年級節數),再到「開始排課」排課。帳號可以停用/啟用、重設密碼;系統管理員還能改帳號所屬的學校、刪除帳號(有教師資料的一般老師帳號請改用停用)。

### 9.(可選)灌入示範資料

```bash
# 在專案根目錄
python scripts/seed_test_data.py          # 建立示範國小
python scripts/seed_test_data.py --run    # 建立後直接自動排課
```

這個腳本直接呼叫 Service 層函式(不透過 HTTP API),建立一所可以直接排課的「示範國小」:系統管理員 `admin`(資料庫還沒有系統管理員時才建立)、教學組長 `coordinator`、一般老師 `teacher01`–`teacher10`(王、林、陳、李、張、吳、黃、劉、蔡、楊老師),密碼都是 `demo-pass-123`;一到六年級(各一班:一年甲班…六年甲班)、星期一到五的時段(早自習、午休、放學不可排)、10 個預設科目與各年級節數、115 學年度第 1 學期、兩間特殊教室(自然教室、藝術教室;其他課都是原班上課,不佔教室),以及一筆「尚未排課」的排課紀錄:所有老師都參與(每週 8–20 節、少數不可排時段)、各年級預設可排節次、科目需求依學校的科目需求同步,國語文由各班導師授課,自然科學與藝術設為 `2+1` 連堂並指定特殊教室。加 `--run` 會接著自動排課(成功後紀錄變成「自動排課」)。示範國小已存在時腳本會停止,要重來請先重設開發資料庫(開發資料可丟棄,例如 `alembic downgrade base && alembic upgrade head`)。

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

後端 image 本身沒有包含 `scripts/` 目錄;若新電腦沒有安裝 Python,也可以把 `scripts/` 掛進後端容器執行(此做法尚未實測):`docker compose --profile full run --rm -v "./scripts:/app/scripts" backend python scripts/seed_test_data.py --run`。

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

**目前總計 1727 個測試**(2026-11-13 計數):後端 1167 個、前端 560 個。2026-11-13 完整執行:後端 1167 個全數通過(引擎 224 個約 17 秒、API 943 個約 22 分鐘);前端 557 個通過、3 個失敗——`utils/homeCards.test.ts` 的 `recordsCardText` 仍預期「· 最近一筆:狀態」字尾,但首頁未發布紀錄已在 2026-11-10 簡化為只顯示筆數,測試尚未跟著更新。

| 類別 | 測試數 | 執行方式 |
|---|---|---|
| Scheduling Engine(純 Python 邏輯,不碰資料庫) | 224 | `pytest tests/scheduling_engine/` |
| API / 整合測試(真實 FastAPI + PostgreSQL) | 943 | 其餘 `tests/test_*.py` |
| 前端純函式單元測試(Vitest,55 個檔案) | 560 | `cd frontend && npm test` |

前端測試只涵蓋純函式(衝突句子合併與前後比對、定位規則、候選格標示、拖放規則、未排入課程、預覽對話框、對話框鍵盤操作、失敗診斷句子、排課紀錄與精靈規則、連堂樣式與複製、共同排課、可搜尋選單、科目排序、教室容量、帳號清單排序與篩選、設計 token 與對比、閒置登出等),元件與頁面互動沒有自動化測試。

Scheduling Engine 那組測試不需要啟動 FastAPI 或連資料庫,很快就跑完;API 測試會對 `TEST_DATABASE_URL` 指到的資料庫逐一 `create_all`/`drop_all`,耗時較長(完整後端約 24 分鐘)。測試策略的完整理由見 `docs/SYSTEM_DESIGN.md` 第 9 節。

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
  constraints/        H1–H15 Hard Constraint(H10 不實作)
  algorithms/         前向檢查(自動排課使用)/ Greedy / Backtracking / Soft Constraint 最佳化
  models/             純 Python domain dataclass
frontend/
  src/
    pages/            頁面(公開首頁、登入、後台首頁、學校資料、開始排課精靈、排課紀錄、檢視排課設定、課表、帳號管理、學校管理)
    components/       共用元件(Layout、登入頁品牌區、可搜尋選單、失敗診斷、確認對話框、衝突清單、課表格、換教師、預覽對話框等;
                      wizard/ 為開始排課的各步驟與課表格式的時段勾選對話框)
    api/              axios 呼叫層
    hooks/            共用 CRUD、資料擷取、檢查衝突、移動/對調與換教師的流程
    utils/            純函式(衝突合併與比對、定位、拖放規則等;*.test.ts 為對應的單元測試)
    constants/        錯誤訊息與違規句子的中文樣板
    styles/           Tailwind 共用樣式 token(顏色 token 在 index.css 的 @theme)
    assets/           公開首頁使用的課表截圖
tests/                後端測試(API 層 + scheduling_engine 子目錄)
scripts/              工具腳本(示範國小灌入;reset_demo_* / add_demo_rooms 只適用 Task 98 之前的舊資料)
docs/                 系統設計文件、截圖
```

## 已知限制與未來規劃

- **H10 教室容量不實作**:教室容量欄位已刪除,一間教室同時能容納幾班改用「一次最多幾班同時使用」;系統不知道班級人數。
- **Soft Constraint 只有三條,科目以名稱判定**:S8/S9/S10 依科目名稱包含的關鍵字判斷(科目改名就不會被認出);`AGENTS.md` 列出的 S1–S7(教師每日負擔平衡、減少空堂等)尚未實作,分數也沒有顯示在畫面上。
- **手動調整不阻擋衝突、儲存後沒有上一步**:每次調整都先預覽並自動重新檢查,但衝突不會被擋下;未儲存的編輯可以離開頁面放棄。
- **換教師一次一門課**;**共同排課的課不能移出課表**(放回時無法帶著其他班的課)。
- **移動節次不會更新固定時段**:被固定時段的課移走後,檢查會列出「不在固定時段」;固定時段只能在尚未排課的紀錄設定。
- **一般老師看到的是全校已發布課表**:沒有「只看自己的課」的預設篩選。
- **「有未排入課程時不能發布」只在前端擋下**,後端發布 API 沒有同樣的檢查。
- **前端只有純函式的單元測試**:元件與頁面互動(拖曳、搜尋選單、精靈)沒有自動化測試,以手動驗證為主。
- **年級沒設定可排節次時不受限制**:精靈一定會為每個年級存下設定;直接用 API 跳過時,該年級視為全部節次都可排。

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
