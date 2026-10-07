# GitOps for TaskBoard

`argocd-application.yaml` points Argo CD at `helm/taskboard` in this repository. After a push to `main`:

1. CI builds, scans and pushes images tagged with the commit SHA.
2. A commit that changes `backend.tag` / `frontend.tag` in the values file is the deployment, because Git is the source of truth. A CI bot can make that commit, or a person can.
3. Argo CD notices the change and runs `helm template` + apply. With `selfHeal: true` it also reverts manual `kubectl` edits.

The live Argo CD demo (sync, self-heal) is in Session 20: `../../../session-20-monitoring-observability-gitops/README.md`.
