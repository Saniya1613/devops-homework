#!/bin/bash
# Issue 3: the backend Service selector no longer matches the pod labels
kubectl -n s21-final patch service taskboard-backend -p '{"spec":{"selector":{"app":"taskboard-api"}}}'
