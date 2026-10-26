# CareSlot — clinic appointment booking (Session 21 DevOps capstone)

**Student:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

CareSlot is a front-desk app for a small clinic. Reception staff manage the clinic's **doctors**, **book patient appointments** in free time slots, and move each visit through the day (*Scheduled → Checked in → Completed*, or *Cancelled / No-show*). The API refuses to double-book a doctor and refuses bookings for doctors who are not taking appointments. The dashboard shows today's load, upcoming patients and each doctor's workload.

The application is my own domain. The DevOps layer follows the Session 21 reference architecture: tests → Docker → GitHub Actions → Trivy → GHCR → Terraform (AWS VPC + EKS) → Helm → Ingress → HPA → Prometheus + Grafana.

![CareSlot dashboard](docs/screenshots/01-app-dashboard.png)

---

## 1. Architecture

```text
Developer ── git push ──> GitHub ──> GitHub Actions
                                     ├─ 1. Test      pytest (15 tests) · vite build · helm lint · terraform validate
                                     ├─ 2. Security  Semgrep · pip-audit · Trivy fs · Trivy config · gitleaks
                                     ├─ 3. Build     docker build x2 · Trivy image gate · push to GHCR (tag = commit SHA)
                                     └─ 4. Deploy    helm upgrade --install · smoke test via Ingress · Prometheus target check
                                                        │
Terraform ──> AWS ap-south-1: VPC (2 public + 2 private subnets) ──> EKS + managed node group
                                                        │
                         Kubernetes namespace "careslot" (Helm release "careslot")
     Browser ──> Ingress (nginx) ──┬── /      ──> frontend Service ──> React + nginx  (2+ pods)
                                   └── /api   ──> backend Service  ──> FastAPI        (HPA 2-6 pods)
                                                                           │
                                                          PostgreSQL 16 + PersistentVolumeClaim
     Prometheus ── ServiceMonitor ──> backend /metrics ──> Grafana dashboard "CareSlot - API overview"
```

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite 5, responsive CSS, served by unprivileged nginx (port 8080) |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, prometheus-fastapi-instrumentator |
| Database | PostgreSQL 16 (two tables: `doctors`, `appointments`) |
| Tests | pytest + FastAPI TestClient on a throw-away SQLite DB; Node test runner for the frontend build |
| Containers | Docker (backend single stage, frontend multi-stage), Docker Compose |
| CI/CD | GitHub Actions, GitHub Container Registry |
| Security | Trivy (image, fs, config), Semgrep, pip-audit, gitleaks |
| Infrastructure | Terraform 1.9, AWS provider 5.x: VPC, subnets, IGW, optional NAT, IAM, KMS, EKS, node group, EBS CSI |
| Kubernetes | Helm 3 chart, Ingress (ingress-nginx), HPA (autoscaling/v2), PDBs, Pod Security `restricted` |
| Observability | kube-prometheus-stack (Prometheus Operator, Grafana, Alertmanager), ServiceMonitor, PrometheusRule |

## 2. Repository layout

```text
careslot/
├── backend/                 FastAPI app
│   ├── app/                 main.py, config.py, db.py, models.py, schemas.py, routers/{doctors,appointments}.py
│   ├── alembic/versions/    0001 create tables · 0002 seed doctors
│   ├── tests/               conftest.py + 15 tests
│   ├── Dockerfile           non-root (uid 10001), runs migrations then uvicorn
│   └── requirements.txt     runtime deps (requirements-dev.txt adds pytest)
├── frontend/                React + Vite, nginx.conf.template, multi-stage Dockerfile (nginx uid 101)
├── docker-compose.yml       db + backend + frontend
├── k8s/                     namespace.yaml (Pod Security restricted), resource-quota.yaml
├── helm/careslot/           Chart.yaml, values.yaml, values-dev.yaml, values-eks.yaml, templates/, dashboards/
├── terraform/               AWS VPC + EKS (*.tf, terraform.tfvars.example)
├── monitoring/              prometheus-values.yaml, careslot-alerts.yaml, grafana-dashboard-careslot.json
├── security/                gitleaks.toml, trivy.yaml, .trivyignore
├── troubleshooting/         3 break-and-fix labs
├── scripts/                 seed-demo.sh, load-test.sh
├── gitops/                  Argo CD Application (optional)
└── docs/screenshots/
```

The pipeline lives at the repository root: [`.github/workflows/session21-final-project.yml`](../../.github/workflows/session21-final-project.yml).

---

## 3. M1: Application

### API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` · `/health` · `/ready` · `/metrics` | info · liveness · readiness (runs `SELECT 1`) · Prometheus |
| GET / POST | `/api/doctors` | list (`?active_only=true`) / add a doctor |
| GET / PUT / DELETE | `/api/doctors/{id}` | read / update (e.g. pause bookings) / remove |
| GET / POST | `/api/appointments` | list (`?status=`, `?doctor_id=`, `?on=YYYY-MM-DD`) / book |
| GET / PUT / DELETE | `/api/appointments/{id}` | read / reschedule or change status / delete |
| GET | `/api/appointments/stats` | today's count, counts per status, per-doctor workload |

Business rules (each covered by a test):

* A doctor cannot be booked for two overlapping visits. The API returns **409** unless the earlier visit is cancelled or a no-show.
* A paused doctor (`active=false`) cannot be booked (**409**). An unknown doctor returns **404**.
* Phone numbers and durations (5–120 min) are validated by Pydantic (**422**).

Swagger UI is served at `/docs` ([screenshot](docs/screenshots/05-swagger-docs.png)).

### Database and migrations

Alembic creates `doctors` and `appointments` (FK with `ON DELETE CASCADE`, indexes on `doctor_id`, `scheduled_at`, `status`). A second migration seeds four doctors, so a fresh install is usable at once. The backend container runs `alembic upgrade head` before starting Uvicorn.

```console
$ docker compose exec db psql -U careslot -d careslot -c "select version_num from alembic_version;"
    version_num
-------------------
 0002_seed_doctors

$ docker compose exec db psql -U careslot -d careslot -c "select id, doctor_id, patient_name, status, scheduled_at from appointments order by scheduled_at limit 5;"
 id | doctor_id | patient_name |   status   |      scheduled_at
----+-----------+--------------+------------+------------------------
  1 |         1 | Riya Patil   | COMPLETED  | 2026-10-15 04:00:00+00
  2 |         1 | Aman Gupta   | CHECKED_IN | 2026-10-15 04:20:00+00
  3 |         2 | Ishaan Nair  | SCHEDULED  | 2026-10-15 05:00:00+00
  4 |         3 | Neha Rao     | CANCELLED  | 2026-10-15 06:30:00+00
  5 |         4 | Kabir Shah   | SCHEDULED  | 2026-10-15 08:00:00+00
```

### UI

Dashboard with KPI cards, status chips, doctor and day filters, a "Book appointment" form, one-click status actions, a "Next up" feed, workload per doctor, a Doctors page (add, pause or resume), toasts, and loading and backend-error states. On phones the table turns into cards.

| Booking form | Doctors | Mobile |
|---|---|---|
| ![](docs/screenshots/02-app-book-appointment.png) | ![](docs/screenshots/03-app-doctors.png) | <img src="docs/screenshots/04-app-mobile.png" width="160"> |

### Run locally

```bash
docker compose up --build          # http://localhost:3000  (API: http://localhost:8000/docs)
./scripts/seed-demo.sh             # book 8 demo appointments for today
docker compose down -v             # stop and delete the database volume
```

Without Docker: `cd backend && pip install -r requirements-dev.txt && export DATABASE_URL=postgresql+psycopg://careslot:careslot@localhost:5432/careslot && alembic upgrade head && uvicorn app.main:app --reload`, and in another terminal `cd frontend && npm install && npm run dev` (http://localhost:5173, proxies `/api` to port 8000).

## 4. M2: Testing

`tests/conftest.py` points `DATABASE_URL` at a throw-away SQLite file and rebuilds the schema for every test, so tests never touch PostgreSQL. `pytest.ini` sets `pythonpath` and `testpaths`.

```console
$ cd backend && pytest -v
tests/test_appointments.py::test_book_and_get_appointment PASSED
tests/test_appointments.py::test_double_booking_is_rejected PASSED
tests/test_appointments.py::test_cancelled_slot_can_be_rebooked PASSED
tests/test_appointments.py::test_reschedule_and_status_flow PASSED
tests/test_appointments.py::test_filters_and_stats PASSED
tests/test_appointments.py::test_delete_appointment PASSED
tests/test_appointments.py::test_booking_validation_and_unknown_doctor PASSED
tests/test_appointments.py::test_inactive_doctor_cannot_be_booked PASSED
tests/test_doctors.py::test_create_and_list_doctors PASSED
tests/test_doctors.py::test_get_update_delete_doctor PASSED
tests/test_doctors.py::test_doctor_validation PASSED
tests/test_health.py::test_health PASSED
tests/test_health.py::test_ready_checks_database PASSED
tests/test_health.py::test_root_identifies_service PASSED
tests/test_health.py::test_metrics_endpoint_is_prometheus_format PASSED
======================== 15 passed in 0.72s =========================
```

The frontend build has its own smoke test (`npm test`). It checks that `dist/` exists and that the bundle calls relative `/api` paths, with no hard-coded backend host.

## 5. M3: Git and GitHub

* Repository: https://github.com/Saniya1613/devops-homework (public), project folder `session-21-final-devops-project/careslot/`.
* The project was built as a series of small, descriptive commits (`git log --oneline -- session-21-final-devops-project`).
* `.gitignore` excludes `.env`, `__pycache__/`, `.venv/`, `node_modules/`, `dist/`, Terraform state and `*.tfvars`.

## 6. M4: Docker

| Image | Base | User | Notes |
|---|---|---|---|
| `careslot-backend` | `python:3.12-slim` | uid **10001** | OS packages patched, dependency layer cached, `HEALTHCHECK`, `alembic upgrade head && uvicorn` |
| `careslot-frontend` | **stage 1** `node:22-alpine` → **stage 2** `nginxinc/nginx-unprivileged:alpine` | uid **101** | only `dist/` is shipped, so no Node or `node_modules` in the runtime image; listens on 8080 |

```console
$ docker compose up --build -d && docker compose ps
SERVICE    IMAGE                     STATUS                    PORTS
backend    careslot-backend:local    Up 2 minutes (healthy)    0.0.0.0:8000->8000/tcp
db         postgres:16-alpine        Up 2 minutes (healthy)    0.0.0.0:5432->5432/tcp
frontend   careslot-frontend:local   Up 2 minutes (healthy)    0.0.0.0:3000->8080/tcp

$ curl -s localhost:8000/health; curl -s localhost:8000/ready
{"status":"UP"}{"status":"READY"}
```

## 7. M5 and M6: CI/CD and DevSecOps

The workflow runs on every push to `main` that touches this project, on pull requests, and on demand.

| Job | What happens | Fails the build when |
|---|---|---|
| 1. Test | `pytest -v`, `npm run build && npm test`, `helm lint` (3 value sets), `terraform fmt -check && validate` | any test, build or lint fails |
| 2. Security | Semgrep `p/python` (SAST), pip-audit + Trivy fs (dependencies), Trivy config (Terraform, Helm, K8s, Dockerfiles), gitleaks (secrets) | any HIGH or CRITICAL finding, or any leaked secret |
| 3. Build | builds both images, prints a full Trivy report, **Trivy gate**, pushes `ghcr.io/saniya1613/careslot-{backend,frontend}:<commit SHA>` | a HIGH or CRITICAL CVE that has a fix |
| 4. Deploy | kind cluster + ingress-nginx + metrics-server + kube-prometheus-stack, `helm upgrade --install`, smoke test through the Ingress, 60 s load, HPA status, Prometheus target **UP** check | pods not ready, Ingress smoke test fails, or Prometheus is not scraping the backend |

| 5. GitOps | on `main` only: writes the new SHA into `helm/careslot/values-gitops.yaml` and commits it (`[skip ci]`) | never (no change = no commit) |

Images are tagged with the full commit SHA, never `latest`, so every running pod can be traced back to one commit.

**What Trivy scanned and what it means.** Trivy scans each finished image: the OS packages (Debian 13 in the backend, Alpine in the frontend) and every Python package in the backend. The gate fails only on HIGH or CRITICAL vulnerabilities that already have a fixed version, because those are the ones we can act on. That is why both Dockerfiles upgrade their OS packages. In my local scan both images had **0 fixable HIGH/CRITICAL** findings. The backend still has unfixed Debian findings. One example is **CVE-2026-9538** in `perl-base` (HIGH, status `fix_deferred`), a denial of service via a crafted tar header in Perl's Archive::Tar. CareSlot never runs Perl or unpacks tar files, so it is not reachable. It stays visible in the report step and will be fixed when Debian ships a patch. Trivy config also flagged the public EKS API endpoint and the public subnets. These are deliberate for this demo, documented with `#trivy:ignore` comments in the Terraform, and can be tightened with `public_access_cidrs` and `enable_nat_gateway`. The missing Secrets encryption was fixed with a KMS key.

## 8. M7: Terraform (AWS VPC + EKS)

| File | Creates |
|---|---|
| `vpc.tf` | VPC `10.30.0.0/16`, **2 public + 2 private subnets** in 2 AZs (EKS/ELB tags), IGW, route tables, optional single NAT gateway |
| `iam.tf` | cluster role, node role (worker, CNI, ECR read, EBS CSI policies), KMS permission for the control plane |
| `eks.tf` | KMS key, **EKS cluster** (Secrets encryption, API and audit logs, access entries), **managed node group** (t3.medium, 1–3 nodes), add-ons `vpc-cni`, `kube-proxy`, `coredns`, `aws-ebs-csi-driver` |
| `outputs.tf` | VPC and subnet IDs, cluster name and endpoint, the `aws eks update-kubeconfig` command |
| `terraform.tfvars.example` | sample variables (no credentials; the real `terraform.tfvars` is git-ignored) |

`enable_nat_gateway = false` (default) puts nodes in the public subnets, which is the cheapest option for a short demo. `true` moves them to private subnets behind a NAT gateway. `kubernetes_version = null` uses the current AWS default, which avoids paid extended support.

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars      # optional tweaks
aws configure                                     # your own IAM user - keys never go in Git
terraform init
terraform plan -out tfplan                        # screenshot for M7
terraform apply tfplan                            # ~15 min
$(terraform output -raw configure_kubectl)        # aws eks update-kubeconfig ...
kubectl get nodes
# ... deploy (section 9), take screenshots ...
terraform destroy                                 # ALWAYS - screenshot for M7
```

Cost while running is roughly USD 0.10/h for the EKS control plane, plus the nodes (2 × t3.medium, much less with `SPOT`), plus about USD 0.02/h for the load balancer.

## 9. M8: Kubernetes + Helm

Chart `helm/careslot`: ConfigMap and Secret split (the DB password is generated randomly and kept across upgrades), backend and frontend Deployments (2+ replicas, zero-downtime rolling updates, startup, readiness and liveness probes, read-only root filesystem, all capabilities dropped, non-root), `wait-for-db` init container, ClusterIP Services, PostgreSQL with a PVC (`helm.sh/resource-policy: keep`), Ingress (`/api` → backend, `/` → frontend), HPA on CPU (2–6), PodDisruptionBudgets, ServiceMonitor and Grafana dashboard ConfigMap.

```bash
# monitoring first, so the ServiceMonitor CRD exists
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace \
  -f monitoring/prometheus-values.yaml --set grafana.adminPassword='<choose-one>'
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace
helm upgrade --install metrics-server metrics-server/metrics-server -n kube-system   # needed by the HPA

kubectl apply -f k8s/namespace.yaml
TAG=<commit SHA from the green pipeline>
helm upgrade --install careslot ./helm/careslot -n careslot -f helm/careslot/values-eks.yaml \
  --set backend.tag=$TAG --set frontend.tag=$TAG          # local cluster: -f helm/careslot/values-dev.yaml
kubectl apply -f monitoring/careslot-alerts.yaml

kubectl get pods,svc,ingress,hpa -n careslot
helm list -n careslot
kubectl get ingress careslot -n careslot      # EKS: open http://<ADDRESS>/  (local: add careslot.local to /etc/hosts)
```

If the GHCR packages are private, make them public (package settings → Change visibility) or create an `imagePullSecret`.

HPA demo: `API=http://<ingress-address> DURATION=120 CONCURRENCY=30 ./scripts/load-test.sh`, then watch `kubectl get hpa -n careslot -w`.

### GitOps with Argo CD (EKS)

On EKS the app is deployed by **Argo CD**, not by hand. `gitops/argocd-application.yaml` points Argo CD at this Helm chart on `main` with `values.yaml + values-eks.yaml + values-gitops.yaml`, with automated sync, prune and self-heal.

```text
git push -> 1. Test -> 2. Security -> 3. Build + Trivy + GHCR -> 4. Deploy (kind) -> 5. GitOps commit (new SHA)
                                                                                         |
                                       Argo CD on EKS sees the commit -> helm template -> rolling update
```

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -n argocd -f gitops/argocd-application.yaml
kubectl get applications -n argocd            # careslot  Synced  Healthy
kubectl port-forward -n argocd svc/argocd-server 8080:443   # UI; password: argocd-initial-admin-secret
```

## 10. M9: Observability

* `/metrics` exposes `http_requests_total`, `http_request_duration_seconds` (per handler, method and status class) and the business counter `careslot_appointments_booked_total`.
* The ServiceMonitor (label `release: monitoring`) makes Prometheus scrape every backend pod every 15 s.
* The Grafana dashboard **"CareSlot - API overview"** loads automatically through the sidecar. It shows requests/s, p95 latency, 5xx rate, bookings, backend pods UP, HPA replicas, requests by endpoint, p50/p95/p99, status classes, bookings/min, and CPU and memory per pod. JSON: [`monitoring/grafana-dashboard-careslot.json`](monitoring/grafana-dashboard-careslot.json).
* Alerts (`monitoring/careslot-alerts.yaml`): backend down, 5xx rate above 5 %, p95 above 500 ms, HPA at max, pod restarting.

```console
$ curl -s localhost:8000/metrics | grep -E '^(http_requests_total|careslot_)'
careslot_appointments_booked_total 0.0
http_requests_total{handler="/api/doctors",method="GET",status="2xx"} 4.0
http_requests_total{handler="/api/appointments/stats",method="GET",status="2xx"} 4.0
http_requests_total{handler="/api/appointments",method="GET",status="2xx"} 4.0
```

```bash
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090   # Status → Targets
kubectl port-forward -n monitoring svc/monitoring-grafana 3001:80                         # admin / <your password>
```

## 11. Troubleshooting labs

See [`troubleshooting/README.md`](troubleshooting/README.md):

1. A wrong image tag causes `ImagePullBackOff`.
2. A Service selector that matches no Pod leaves the Service with no endpoints.
3. A wrong DB password leaves pods Running but never Ready.

## 12. M10: Demo script

1. Open CareSlot and book an appointment, then try the same slot again to show the 409 conflict.
2. In `/docs`, run create, read, update and delete calls. Show the `appointments` table in `psql`.
3. Change something small (for example the KPI label), then `git commit` and `git push`.
4. In GitHub Actions, watch Test → Security → Build (Trivy) → Deploy go green. In GHCR, show the new SHA-tagged images.
5. Show `terraform/` and the AWS console (VPC + EKS). Run `kubectl get pods,svc,hpa -n careslot` and `helm list -n careslot`.
6. Run `helm upgrade` with the new SHA, open the app through the Ingress and show that the change is live.
7. Run `load-test.sh`, then show the HPA scaling and the Grafana panels moving.
8. Break the Service selector (lab 2) and fix it live.

The recorded presentation and the slide deck are in [`../demo/`](../demo/).

## 13. Submission evidence

| Rubric item | Evidence |
|---|---|
| App running in the browser | `docs/screenshots/01–05` |
| `pytest -v` passing | section 4 output + CI job "1. Test" |
| `docker compose up --build` | section 6 output |
| Green pipeline, Trivy output, GHCR SHA tags | Actions run for the latest commit, packages `careslot-backend` and `careslot-frontend` |
| `terraform plan`, AWS console (VPC + EKS), `terraform destroy` | run on my AWS account (section 8) and saved in `docs/screenshots/` |
| `kubectl get pods/svc`, `helm list`, app via Ingress | EKS cluster (section 9) + CI job "4. Deploy" log |
| Prometheus target UP, Grafana panel | EKS cluster (section 10) + CI job "4. Deploy" check |

### Screenshots (EKS run, ap-southeast-2)

| Evidence | Screenshot |
|---|---|
| pytest -v (15 passed) | ![pytest -v (15 passed)](docs/screenshots/06-pytest-15-passed.jpg) |
| terraform apply (28 added) | ![terraform apply (28 added)](docs/screenshots/07-terraform-apply.png) |
| AWS VPC + EKS ACTIVE + nodes Ready | ![AWS VPC + EKS ACTIVE + nodes Ready](docs/screenshots/08-aws-vpc-eks-nodes.png) |
| kubectl pods/svc + helm list on EKS | ![kubectl pods/svc + helm list on EKS](docs/screenshots/09-eks-kubectl-helm.jpg) |
| App via Ingress (AWS LB) | ![App via Ingress (AWS LB)](docs/screenshots/10-eks-app-via-ingress.jpg) |
| Prometheus targets UP | ![Prometheus targets UP](docs/screenshots/11-prometheus-targets-up.jpg) |
| Grafana CareSlot dashboard | ![Grafana CareSlot dashboard](docs/screenshots/12-grafana-dashboard.jpg) |
| terraform destroy (28 destroyed) | ![terraform destroy (28 destroyed)](docs/screenshots/13-terraform-destroy.png) |

## 14. Lessons learned

1. **Tests first is the cheapest gate.** The double-booking rule was easy to get wrong with time zones. A test caught it before any image was built.
2. **Readiness is not liveness.** `/ready` checks the DB, so a wrong password (lab 3) takes pods out of the Service instead of restarting them forever.
3. **Fail on what you can fix.** Gating on *fixable* HIGH/CRITICAL CVEs and patching base-image packages keeps the pipeline strict without blocking on CVEs no one can fix yet.
4. **Infrastructure costs money.** The defaults (no NAT gateway, small node group, SPOT option) and the `terraform destroy` step are part of the design.
