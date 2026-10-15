#!/usr/bin/env bash
# Generate steady traffic so Prometheus/Grafana panels and the HPA have something to show.
#   API=http://careslot.local DURATION=120 CONCURRENCY=20 ./scripts/load-test.sh
set -euo pipefail
API="${API:-http://localhost:8000}"; DURATION="${DURATION:-60}"; CONCURRENCY="${CONCURRENCY:-10}"
end=$((SECONDS + DURATION))
echo "Hitting $API for ${DURATION}s with $CONCURRENCY workers..."
worker() {
  while [ $SECONDS -lt $end ]; do
    curl -s -o /dev/null "$API/api/appointments"
    curl -s -o /dev/null "$API/api/appointments/stats"
    curl -s -o /dev/null "$API/api/doctors"
    curl -s -o /dev/null "$API/api/appointments/999999"   # 404s show up in the error-rate panel
  done
}
for _ in $(seq "$CONCURRENCY"); do worker & done
wait
echo "done"
