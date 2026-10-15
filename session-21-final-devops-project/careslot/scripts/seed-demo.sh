#!/usr/bin/env bash
# Book a few demo appointments for today so the dashboard has data.
#   ./scripts/seed-demo.sh                      (Docker Compose, default)
#   API=http://careslot.local ./scripts/seed-demo.sh   (through the Kubernetes Ingress)
set -euo pipefail
API="${API:-http://localhost:8000}"
day=$(date -u +%Y-%m-%d)
book() { # doctor_id HH:MM patient phone reason
  curl -sf -X POST "$API/api/appointments" -H 'Content-Type: application/json' \
    -d "{\"doctor_id\":$1,\"scheduled_at\":\"${day}T$2:00Z\",\"patient_name\":\"$3\",\"patient_phone\":\"$4\",\"reason\":\"$5\"}" \
    | python3 -c 'import json,sys; a=json.load(sys.stdin); print("booked #%s %s with %s" % (a["id"], a["patient_name"], a["doctor_name"]))' \
    || echo "skipped $3 (slot taken?)"
}
book 1 "04:00" "Riya Patil"     "+91 98765 43210" "Fever and cough"
book 1 "04:20" "Aman Gupta"     "+91 98200 11223" "Blood pressure review"
book 2 "05:00" "Ishaan Nair"    "+91 99300 44556" "Vaccination"
book 3 "06:30" "Neha Rao"       "+91 97690 77889" "Skin allergy"
book 4 "08:00" "Kabir Shah"     "+91 90040 99001" "Knee pain"
book 1 "10:30" "Sara Khan"      "+91 91670 12121" "Follow-up"
book 3 "11:00" "Vikram Joshi"   "+91 93220 34343" "Acne treatment"
book 2 "12:15" "Anaya Kulkarni" "+91 96190 56565" "Ear infection"
# move a few through the day's workflow
curl -sf -X PUT "$API/api/appointments/1" -H 'Content-Type: application/json' -d '{"status":"COMPLETED"}' >/dev/null || true
curl -sf -X PUT "$API/api/appointments/2" -H 'Content-Type: application/json' -d '{"status":"CHECKED_IN"}' >/dev/null || true
curl -sf -X PUT "$API/api/appointments/4" -H 'Content-Type: application/json' -d '{"status":"CANCELLED"}' >/dev/null || true
curl -s "$API/api/appointments/stats"; echo
