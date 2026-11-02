#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -f host/Dockerfile.security -t aterus-security-check .
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 128 --memory 512m --cpus 2 \
  aterus-security-check 2>&1 | tee security-test-results.txt
