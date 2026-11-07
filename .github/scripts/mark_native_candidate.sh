#!/usr/bin/env bash
set -euo pipefail
sha="${WORKSPACE_SHA:?exact Workspace SHA required}"
[[ "${GITHUB_REPOSITORY:-}" == 'pvtkyron/pantry-core' && "${GITHUB_REF:-}" == 'refs/heads/main' ]] || { echo '::error::Native receipt requires canonical Pantry Core/main'; exit 1; }
[[ "$sha" =~ ^[0-9a-f]{40}$ && "$CANDIDATE_SHA32" =~ ^[0-9a-f]{64}$ && "$CANDIDATE_SHA64" =~ ^[0-9a-f]{64}$ && "${GITHUB_RUN_ID:-}" =~ ^[1-9][0-9]*$ && "${GITHUB_RUN_ATTEMPT:-}" =~ ^[1-9][0-9]*$ ]] || { echo '::error::Signed candidate identity invalid'; exit 1; }
key="${CANDIDATE_INPUTS_SHA256:-}"
[[ -z "$key" || "$key" =~ ^[0-9a-f]{64}$ ]] || { echo '::error::Native input fingerprint rejected'; exit 1; }
out="${RUNNER_TEMP:?}/kyron-native-receipt"
mkdir -p "$out"
jq -n --arg inputs_sha256 "$key" --arg source "$sha" --arg sha32 "$CANDIDATE_SHA32" --arg sha64 "$CANDIDATE_SHA64" --argjson run_id "$GITHUB_RUN_ID" --argjson attempt "$GITHUB_RUN_ATTEMPT" '{schema:1,source_sha:$source,inputs_sha256:$inputs_sha256,sha32:$sha32,sha64:$sha64,producer_run_id:$run_id,producer_attempt:$attempt,verified:true,published:false}' > "$out/native-candidate-receipt.json"
echo '[NATIVE/RECEIPT][VERIFIED] small signed-candidate receipt; NOT_PUBLISHED'
