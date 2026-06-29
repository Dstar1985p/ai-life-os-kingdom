#!/usr/bin/env bash
set -e

echo "=== Release Gate ==="

BLOCKED=0

if find . -name ".env" -o -name "*.pem" -o -name "*.key" | grep -q .; then
  echo "ERROR: Potential secret file found."
  BLOCKED=1
fi

if grep -R "HARDCODED_SECRET\|PRIVATE_KEY\|BEGIN RSA PRIVATE KEY" . --exclude-dir=.git --exclude=release_gate.sh; then
  echo "ERROR: Possible secret marker found."
  BLOCKED=1
fi

if [ ! -d tests ]; then
  echo "ERROR: No tests directory found."
  BLOCKED=1
fi

if [ "$BLOCKED" -eq 1 ]; then
  echo "RELEASE BLOCKED."
  exit 1
fi

echo "Release gate passed."
