# Minimal, up-to-date base image (scanned by Trivy in the pipeline)
FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install pinned dependencies, then remove pip itself from the runtime image
# (pip is not needed at runtime and is a frequent source of CVEs)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y pip \
 && rm -rf /usr/local/lib/python3.12/ensurepip

COPY app ./app

# Run as an unprivileged user (matches runAsNonRoot / runAsUser in k8s/deployment.yaml)
RUN addgroup -S -g 10001 appgroup && adduser -S -D -H -u 10001 -G appgroup appuser
USER 10001:10001

EXPOSE 5001
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:5001/health || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--worker-tmp-dir", "/tmp", "--no-control-socket", "--access-logfile", "-", "app.app:app"]
