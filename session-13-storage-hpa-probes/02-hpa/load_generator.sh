#!/usr/bin/env bash
# ==============================================================================
# load_generator.sh – adapted from devops-heros/session-13-storage-hpa-probes/hpa/load_generator.sh
# Runs parallel request loops against the backend to trigger HPA scaling.
# Usage: ./load_generator.sh [URL] [WORKERS]
#   default URL = the ClusterIP of yatri-backend-service in namespace s13-hpa
# (In the homework run I used the in-cluster busybox pod load-generator.yaml instead,
#  so the load does not depend on a port-forward.)
# ==============================================================================
set -euo pipefail
NS=s13-hpa
WORKERS="${2:-4}"
if [[ $# -ge 1 ]]; then
  TARGET_URL="$1"
else
  CIP=$(kubectl get svc yatri-backend-service -n "$NS" -o jsonpath='{.spec.clusterIP}')
  TARGET_URL="http://${CIP}/healthz"
fi

echo "=================================================="
echo "      KUBERNETES HPA TRAFFIC LOAD GENERATOR       "
echo "=================================================="
echo "Target : $TARGET_URL   Workers: $WORKERS"
echo "Press Ctrl+C to stop.  Watch with: kubectl get hpa -n $NS -w"

trap 'echo; echo "Stopping workers"; kill 0' INT TERM
for ((i = 1; i <= WORKERS; i++)); do
  while true; do curl -s --noproxy '*' -o /dev/null "$TARGET_URL" || true; done &
done
wait
