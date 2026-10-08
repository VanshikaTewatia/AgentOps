# AGENTOPS — Enterprise Deployment Guide

This guide details deployment options for **AGENTOPS**, ranging from local containerized orchestration with **Docker Compose** to Kubernetes declarative manifests.

---

## 1. Architecture & Services

```text
                                 Client / Browser
                                        │
                                        ▼ (Port 3000 / Ingress)
                              ┌───────────────────┐
                              │ Next.js Frontend  │
                              └─────────┬─────────┘
                                        │
                                        ▼ (Port 8000 / API v1)
                              ┌───────────────────┐
                              │  FastAPI Backend  │
                              └──────┬─────┬──────┘
                                     │     │
                        ┌────────────┘     └─────────────┐
                        ▼                                ▼
                ┌───────────────┐                 ┌───────────────┐
                │ PostgreSQL 16 │ (Port 8800)     │ Redis 7       │ (Port 6379)
                │  + pgvector   │                 │ (State Cache) │
                └───────┬───────┘                 └───────────────┘
                        │
                        ▼
                ┌───────────────┐
                │ Kafka (KRaft) │ (Port 9092)
                │(Event Stream) │
                └───────────────┘
```

---

## 2. Option A: Local Docker Compose (Recommended)

Docker Compose provides a complete multi-container setup with healthchecks, persistent volumes, and inter-service networking.

### Prerequisites
- Docker 24.0+ & Docker Compose v2+
- Port availability: `3000` (frontend), `8000` (backend), `8800` (Postgres), `6379` (Redis), `9092` (Kafka)

### Launch
```bash
# 1. Clone & enter directory
cd AgentOps

# 2. Build images & start all 5 containers
docker compose build --no-cache
docker compose up -d

# 3. Check health status
docker compose ps
```

### Database Migration & Seed
```bash
# Apply schema migrations
docker compose exec backend alembic -c backend/alembic.ini upgrade head

# Deterministically seed services, initial incidents, and vector runbooks
docker compose exec backend python backend/app/scripts/seed_data.py
```

### Access Endpoints
- **Operations Console**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Backend Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Cleanup & Reset
```bash
# Stop containers (preserves volume data)
docker compose down

# Full clean reset (removes all database and Kafka volumes)
docker compose down -v
```

---

## 3. Option B: Kubernetes Manifests (Declarative)

Declarative manifests are provided in [`k8s/`](file:///C:/Users/Lakshay/AgentOps/k8s) using **Kustomize**.

> [!NOTE]
> These manifests are designed for staging, development, or single-cluster demonstration environments (e.g. Minikube, Kind, or cloud dev clusters). For high-availability multi-region production, managed cloud database and messaging services (e.g., AWS RDS PostgreSQL, AWS MSK Kafka, AWS ElastiCache Redis) are recommended.

### Manifest Manifests Index
| File | Kind | Role |
|---|---|---|
| [`namespace.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/namespace.yaml) | `Namespace` | Dedicated `agentops` workspace. |
| [`configmap.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/configmap.yaml) | `ConfigMap` | Non-sensitive runtime environment variables. |
| [`secrets.example.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/secrets.example.yaml) | `Secret` | Placeholder secret template (no real credentials in Git). |
| [`postgres.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/postgres.yaml) | `StatefulSet` + `Service` | PostgreSQL 16 with `pgvector` and 10Gi PVC. |
| [`redis.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/redis.yaml) | `Deployment` + `Service` | Redis 7 cache with liveness/readiness probes. |
| [`kafka.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/kafka.yaml) | `StatefulSet` + `Service` | Apache Kafka 3.7 running with KRaft consensus. |
| [`backend.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/backend.yaml) | `Deployment` + `Service` | 2 replicas running FastAPI backend as non-root user. |
| [`frontend.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/frontend.yaml) | `Deployment` + `Service` | 2 replicas running Next.js 16 frontend as non-root user. |
| [`migration-job.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/migration-job.yaml) | `Job` | Controlled single-run Alembic migration & data seed jobs. |
| [`ingress.yaml`](file:///C:/Users/Lakshay/AgentOps/k8s/ingress.yaml) | `Ingress` | NGINX routing for `agentops.local`. |

### Kubernetes Deployment Steps
```bash
# 1. Apply namespace, configuration, and secrets
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.example.yaml

# 2. Deploy stateful infrastructure
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/kafka.yaml

# 3. Wait for database readiness and run migration Job
kubectl wait --for=condition=ready pod -l app=postgres -n agentops --timeout=60s
kubectl apply -f k8s/migration-job.yaml

# 4. Deploy stateless application workloads
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml

# Or apply all resources atomically with Kustomize:
kubectl apply -k k8s/
```

---

## 4. Verification & Health Diagnostic Checklist

```bash
# 1. Verify Backend Health
curl -s http://localhost:8000/api/v1/health | jq .

# Expected Output:
# {
#   "status": "healthy",
#   "app_name": "AGENTOPS",
#   "environment": "development",
#   "database_connected": true,
#   "details": {
#     "redis_connected": true,
#     "kafka_connected": true
#   }
# }

# 2. Run Automated Verification Suite
.\scripts\e2e_verify.ps1
```

---

## 5. Security & Isolation Model
- **Non-Root Execution**: Backend runs under `appuser` (UID 1000); Frontend runs under `nextjs` (UID 1001).
- **Zero Committed Secrets**: Secrets strictly loaded from in-cluster Kubernetes Secrets or `.env` files.
- **Atomic Concurrency Protection**: Database state machine uses Compare-And-Set SQL queries to prevent concurrent approval race conditions (HTTP 409).
- **Sanitized Parameter Inspection**: Human approval screens expose only sanitized, server-side validated parameters.
