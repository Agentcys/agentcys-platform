# Agentcys Platform

Multi-tenant GCP infrastructure deployment control plane. Agents call a REST API to provision infrastructure (Cloud Run services, databases, etc.) into customer GCP projects using Terraform. Customers supply a GCP service account key; the platform stores it in Secret Manager and drives Terraform operations via an ephemeral Cloud Run job.

## Architecture Overview

```
Agent / User
    │
    ▼
FastAPI (Cloud Run — our project)
    │  POST /deployments
    │  PATCH /deployments/{id}
    ▼
Cloud Tasks ──► Worker (Cloud Run Job — our project)
                    │
                    ▼
               Terraform  ──► Customer GCP Project
                    │          (Cloud Run, GCS, etc.)
                    ▼
               GCS State Bucket (customer + mirror)
```

## Repository Structure

```
agentcys-platform/
├── platform/              # Shared package
│   ├── config.py          # All env-driven config
│   ├── security/          # CSRF, audit, tenant guard, HMAC
│   ├── credentials/       # SA key credential provider
│   ├── models/            # Pydantic data models
│   └── store/             # Firestore CRUD helpers
├── api/                   # FastAPI application
│   ├── main.py            # App + middleware wiring
│   └── routes/            # Route modules (Prompt 2)
├── worker/                # Cloud Run Job worker (Prompt 4)
├── blueprints/            # Terraform module configs (Prompt 3)
└── tests/                 # pytest unit + integration
```

## Local Development Setup

### Prerequisites

- Python 3.12+
- Docker + Docker Compose
- `gh` CLI (for PR management)
- GCP credentials for local auth (optional — use Firestore emulator)

### Quick Start

```bash
# 1. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements-dev.txt
pip install -e .

# 3. Copy and fill environment variables
cp .env.example .env
# Edit .env with your local values

# 4. Start services (Firestore emulator + API + worker)
docker compose up

# 5. Run tests
pytest tests/ -x -q
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | Yes | `local` / `dev` / `test` / `prod` |
| `CORS_ALLOWED_ORIGINS` | Yes | Comma-separated allowed origins |
| `GCP_PROJECT_ID` | Yes | Our GCP project ID |
| `SECRET_MANAGER_PROJECT` | Yes | Project hosting Secret Manager |
| `STATE_MIRROR_BUCKET` | Yes | GCS bucket for Terraform state mirror |
| `BLUEPRINT_BUCKET` | Yes | GCS bucket for Terraform module tarballs |
| `CLOUD_TASKS_QUEUE` | Yes | Cloud Tasks queue name |
| `CLOUD_TASKS_LOCATION` | Yes | Cloud Tasks queue location |
| `HMAC_SIGNING_SECRET` | Yes | HMAC secret for API ↔ Worker auth |
| `REQUEST_MAX_BODY_BYTES` | No | Max request body size (default 1 MiB) |

### Running Tests

```bash
# Unit tests only
pytest tests/unit/ -x -q

# Integration tests (requires running Firestore emulator)
FIRESTORE_EMULATOR_HOST=localhost:8088 pytest tests/integration/ -x -q

# All tests
pytest tests/ -x -q
```

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

## Security Model

- **Tenant isolation**: every Firestore read asserts `tenant_id` matches the authenticated caller
- **CSRF protection**: Fetch Metadata header inspection (no token round-trips)
- **Service-to-service auth**: HMAC-SHA256 signed payloads between API and Worker
- **Credential storage**: GCP SA keys encrypted at rest in Secret Manager; never stored in Firestore
- **Audit trail**: every write emits a structured JSON audit event (stdout v1; BigQuery v2)

## License

Proprietary — © 2026 Agentcys
