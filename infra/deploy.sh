#!/usr/bin/env bash
# Build (local, not container) and deploy the `scrubbed` stack. Sends stay in dry mode
# unless you pass SendMode=live:   ./deploy.sh SendMode=live
#
# The repo's sam shim has a stale shebang, so we run samcli through the venv python
# directly (the venv has samcli installed).
set -euo pipefail
cd "$(dirname "$0")"
export AWS_PROFILE="${AWS_PROFILE:-default}" AWS_DEFAULT_REGION=us-east-1
VENV="$(cd .. && pwd)/.venv"
export PATH="$VENV/bin:$PATH"                         # python3.12 for the local build
SAM=("$VENV/bin/python" "$VENV/bin/sam")

"${SAM[@]}" build
if [ "$#" -gt 0 ]; then
  "${SAM[@]}" deploy --no-confirm-changeset --no-fail-on-empty-changeset --parameter-overrides "$@"
else
  "${SAM[@]}" deploy --no-confirm-changeset --no-fail-on-empty-changeset
fi
aws cloudformation describe-stacks --stack-name scrubbed --region us-east-1 \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output table
