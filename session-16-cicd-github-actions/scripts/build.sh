#!/bin/sh
# Produces the build artifact (dist/) that the CI job uploads with actions/upload-artifact.
set -e
rm -rf dist && mkdir -p dist
cp -r src package.json package-lock.json dist/
cat > dist/build-info.txt <<INFO
app=session16-cicd-demo
version=$(node -p "require('./package.json').version")
commit=${GITHUB_SHA:-local}
built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
node=$(node -v)
INFO
tar -czf session16-app.tar.gz -C dist .
echo "Build OK -> dist/ and session16-app.tar.gz"
ls -l dist session16-app.tar.gz
