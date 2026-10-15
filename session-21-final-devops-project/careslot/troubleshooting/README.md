# Troubleshooting labs

| Lab | Break it | Symptom | Root cause | Fix |
|---|---|---|---|---|
| 1 | `kubectl apply -f broken-image.yaml` | `ImagePullBackOff` | image tag does not exist in GHCR | use the SHA tag CI pushed |
| 2 | `kubectl apply -f broken-service.yaml` | Service has no endpoints | selector `app=careslot-api` matches no Pod | selector `app=careslot-backend` |
| 3 | `./break-db-password.sh` | pods `Running` but `0/1 READY` | `/ready` fails: DB rejects the password | `./break-db-password.sh restore` |

Clean up: `kubectl delete -f broken-image.yaml -f broken-service.yaml`
