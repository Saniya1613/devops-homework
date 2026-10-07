# Final DevOps Project – TaskBoard

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

The full documentation (overview, architecture, setup, Docker, Kubernetes, Helm, Terraform, CI/CD, DevSecOps, monitoring, GitOps, troubleshooting, screenshots and lessons learned) is in the session README:

➡️ [`../README.md`](../README.md)

Quick start:

```bash
# tests
cd application/backend && pip install -r requirements.txt && pytest -q
# images
docker build -f docker/backend.Dockerfile  -t taskboard-backend:1.0.1  application/backend
docker build -f docker/frontend.Dockerfile -t taskboard-frontend:1.0.1 application/frontend
# deploy
helm upgrade --install taskboard helm/taskboard -n s21-final --create-namespace --wait
curl -H 'Host: taskboard.local' http://<node-ip>/api/tasks
```
