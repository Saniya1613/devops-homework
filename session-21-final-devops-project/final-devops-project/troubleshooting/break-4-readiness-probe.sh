#!/bin/bash
# Issue 4: the readiness probe points at a path the API does not serve
kubectl -n s21-final patch deployment taskboard-backend --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/readyz"}]'
