#!/bin/bash
# Issue 2: someone "fixes" the ConfigMap by hand and introduces a typo in DB_HOST, then restarts the backend
kubectl -n s21-final patch configmap taskboard-config --type merge -p '{"data":{"DB_HOST":"taskboard-postgress"}}'
kubectl -n s21-final rollout restart deployment taskboard-backend
