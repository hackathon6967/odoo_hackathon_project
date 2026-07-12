# EcoSphere — Full-Stack ESG Management Platform

EcoSphere is a comprehensive, production-ready full-stack Enterprise ESG (Environmental, Social, and Governance) Management Platform designed for hackathons. It integrates five core pillars and a background job processing pipeline to track emissions, reward CSR participation, manage policies, inspect directory audits, and build customizable ESG reports.

---

## 🌟 Key Features

1. **Environmental (Green themed)**: Log carbon emissions (electricity, gas, transport, fuel) with auto-calculated values based on customizable emission factors, view trends on chart visualizations, and monitor progress towards sustainability goals.
2. **Social (Amber themed)**: Organise community and corporate CSR activities with a submit-and-verify participation flow, manage training completion tracking, and view department diversity metrics.
3. **Governance (Indigo themed)**: Publish documents and policy versions, track employee acknowledgements, schedule audits, and escalate overdue compliance issues using an automated background flag runner.
4. **Gamification (Pink themed)**: Keep employees engaged via active challenge states, reward redemptions with race-safe currency deductions, and live-rank leaderboards.
5. **Scoring & Reporting (Cyan themed)**: Schedule periodic batch scoring jobs, visualize department rankings, and run the asynchronous Custom Report Builder to generate downloadable PDF/XLSX/CSV reports.

---

## 🛠 Tech Stack

*   **Frontend**: React (Vite), Tailwind CSS v4, Framer Motion, Recharts, Axios.
*   **Backend API**: FastAPI (Python 3.11), SQLAlchemy 2.0 (Asyncpg), PostgreSQL 15, Uvicorn.
*   **Worker Pipeline**: Redis, RQ (Redis Queue) worker & scheduler.
*   **Object Storage**: MinIO (S3-compatible) for hosting generated PDF reports and evidence proofs.
*   **Reverse Proxy & Gateway**: Caddy v2 for unified routing on default HTTP (`:80`).

---

## 🚀 Getting Started (Docker Compose)

The easiest and recommended way to launch the entire stack is using **Docker Desktop**.

### 1. Prerequisites
Ensure you have **Docker Desktop** installed and running:
*   [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
*   Make sure the Docker Engine daemon is fully running (whale icon in taskbar is stable).

### 2. clone & Start the Stack
Clone the repository and spin up all 7 microservices in background daemon mode:
```bash
git clone https://github.com/Abhyudya2006/EcoSphere.git
cd EcoSphere/ecosphere
docker compose up --build -d
```

### 3. Run Database Migrations
Create all 22 database schema tables inside the PostgreSQL container:
```bash
docker compose exec api alembic upgrade head
```

### 4. Seed the Database
Populate the database with sample departments, emission factors, badges, challenges, rewards, and default users:
```bash
docker compose exec api python seed.py
```

---

## 🔑 Demo Access & Ports

Once everything is booted up, access these endpoints in your web browser:

| Service / UI | Host URL | Description |
|---|---|---|
| **EcoSphere Frontend** | [http://localhost](http://localhost) | Main App Portal |
| **API Swagger Docs** | [http://localhost/api/docs](http://localhost/api/docs) | Interactive OpenAPI docs |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) | S3 Object Browser (`admin` / `minioadmin`) |

### Default Credentials:
Use any of these pre-seeded accounts to explore the app:
*   **Admin**: `admin@ecosphere.app` / `admin123`
*   **Manager**: `manager@ecosphere.app` / `admin123`
*   **Employee**: `employee@ecosphere.app` / `admin123`

---

## 📂 Project Structure

```
ecosphere/
├── apps/
│   └── web/                # React / Vite SPA frontend
├── services/
│   ├── api/                # FastAPI application + database schemas + alembic
│   └── worker/             # RQ background job process + PDF document builders
├── infra/
│   ├── caddy/              # Caddyfile gateway router
│   └── postgres/           # Database initialization scripts
└── docker-compose.yml       # 7-service orchestration file
```
