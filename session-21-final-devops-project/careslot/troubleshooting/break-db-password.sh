#!/usr/bin/env bash
# LAB 3 - Pods Running but never Ready (readiness probe /ready fails because the DB rejects the password).
# Investigate: kubectl get pods -n careslot            (0/1 READY)
#              kubectl describe pod <backend-pod>      (Readiness probe failed: HTTP 500)
#              kubectl logs <backend-pod>              (password authentication failed)
# Fix:         ./troubleshooting/break-db-password.sh restore
set -euo pipefail
NS=careslot; SECRET=careslot-db
if [ "${1:-break}" = "restore" ]; then
  kubectl -n $NS patch secret $SECRET -p "{\"data\":{\"DB_PASSWORD\":\"$(cat /tmp/careslot-db-pass)\"}}"
else
  kubectl -n $NS get secret $SECRET -o jsonpath='{.data.DB_PASSWORD}' > /tmp/careslot-db-pass
  kubectl -n $NS patch secret $SECRET -p '{"stringData":{"DB_PASSWORD":"wrong-password"}}'
fi
kubectl -n $NS rollout restart deploy/careslot-backend
