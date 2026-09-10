# Elementary School Timetable System

## Overview

國小智慧排課系統，目標是建立一個具備實際學校排課情境的 full-stack web application，涵蓋教師/班級/科目/教室/時段等資料管理、自動排課、限制條件驗證與人工調課。目前專案處於初始骨架建立階段，尚未實作任何業務邏輯。

## Tech Stack

- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic
- Database: PostgreSQL
- Testing: pytest（frontend testing framework 待定）
- Infrastructure: Docker, Docker Compose
- Version Control: Git, GitHub

## Architecture

React / TypeScript
→ FastAPI (API Layer)
→ Service Layer
→ Domain / Scheduling Engine
→ Repository / ORM
→ PostgreSQL

詳細架構原則與 Scheduling Engine 邊界請見 `AGENTS.md`。

## Project Structure

```text
backend/          FastAPI application
scheduling_engine/ Scheduling domain logic (framework-independent)
frontend/          React + TypeScript application（尚未初始化）
tests/             Automated tests
docs/               Project documentation
scripts/            Utility scripts
```

## Development

開發環境設定與啟動流程待專案基礎依賴建立後補充。

## Testing

測試策略與執行方式待測試套件建立後補充。

## Scheduling Engine

Scheduling Engine 的核心規則與邊界定義於 `AGENTS.md`，目前尚未實作。

## Future Improvements

待專案累積更多進度後補充。
