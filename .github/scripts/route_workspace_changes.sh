#!/usr/bin/env bash
set -euo pipefail
: "${WORKSPACE_SHA:?WORKSPACE_SHA is required}"
: "${CHANGED_PATHS_FILE:?CHANGED_PATHS_FILE is required}"
[[ "${GITHUB_REPOSITORY:-}" == 'pvtkyron/pantry-core' && "${GITHUB_REF:-}" == 'refs/heads/main' ]] || { echo '[ROUTER][REJECTED] canonical Pantry Core/main required' >&2; exit 1; }
[[ "$WORKSPACE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo '[ROUTER][REJECTED] exact lowercase Workspace SHA required' >&2; exit 1; }
[[ -r "$CHANGED_PATHS_FILE" ]] || { echo '[ROUTER][REJECTED] change list unavailable' >&2; exit 1; }
for flag in NATIVE_APPROVAL_READY NATIVE_CANDIDATE_VERIFIED NATIVE_CANDIDATE_MATCHES_PINS NATIVE_SOURCE_APPROVED KYRONLINK_VALIDATED; do
  value="${!flag:-false}"
  [[ "$value" == true || "$value" == false ]] || { echo "[ROUTER][REJECTED] invalid $flag" >&2; exit 1; }
done
routes="$(bash "$(dirname "$0")/classify_workspace_change.sh" < "$CHANGED_PATHS_FILE")"
full=false; kyronlink=false; content=false; components=()
for route in $routes; do
  case "$route" in
    workspace-release) full=true ;;
    component-kyronlink) kyronlink=true ;;
    pantry-delta) content=true ;;
    component-lib|component-launcher|component-dex) components+=("$route") ;;
    none|'') ;;
    *) echo "[ROUTER][REJECTED] unknown route: $route" >&2; exit 1 ;;
  esac
done
full_requested=false
if [[ "${FORCE_FULL:-false}" == true || "$full" == true || ${#components[@]} -gt 1 ]]; then full_requested=true; fi
native_changed=false
if [[ " ${components[*]} " == *" component-lib "* ]]; then native_changed=true; fi
candidate="${NATIVE_CANDIDATE_VERIFIED:-false}"
approved="${NATIVE_APPROVAL_READY:-true}"
pin_match="${NATIVE_CANDIDATE_MATCHES_PINS:-false}"
blocked=false
if [[ "$approved" == false || ( "$candidate" == true && "$pin_match" != true ) ||
      ( ( "$native_changed" == true || "$full_requested" == true ) && "${NATIVE_SOURCE_APPROVED:-false}" != true && "$candidate" != true ) ]]; then blocked=true; fi
events=()
if [[ "$blocked" == true ]]; then
  if [[ ( "$native_changed" == true || "$full_requested" == true ) && "$candidate" != true ]]; then
    events+=(component-lib)
    echo '[ROUTER][CANDIDATE] native changed; request exactly one signed candidate while approval is pending'
  else
    echo "[ROUTER][WAIT] native approval/receipt pending; no duplicate build source=$WORKSPACE_SHA approved=$approved candidate=$candidate matching_pins=$pin_match"
  fi
elif [[ "$full_requested" == true ]]; then events+=(workspace-release)
else
  for component in "${components[@]}"; do
    if [[ "$component" == component-lib && "$candidate" == true && "$pin_match" == true ]]; then
      echo '[ROUTER][NATIVE/NOOP] signed candidate already verified; native pins unchanged from published source; no duplicate compile or upload'
    else events+=("$component"); fi
  done
  if [[ "$content" == true ]]; then events+=(pantry-delta); fi
fi
if [[ "$kyronlink" == true ]]; then
  if [[ "${KYRONLINK_VALIDATED:-false}" == true ]]; then echo "[ROUTER][KYRONLINK/NOOP] validated source=$WORKSPACE_SHA; no duplicate checks"
  else events+=(component-kyronlink); fi
fi
if [[ ${#events[@]} -eq 0 ]]; then echo '[ROUTER][NOOP] no releasable source changes'; exit 0; fi
if [[ "${ROUTER_DRY_RUN:-false}" == true ]]; then
  echo "[ROUTER][DRY-RUN] selected=${events[*]} no_build=true no_prepare=true no_publish=true"
  exit 0
fi
[[ "${ROUTER_DRY_RUN:-false}" == false ]] || { echo '[ROUTER][REJECTED] invalid dry-run control' >&2; exit 1; }
for event in "${events[@]}"; do
  jq -n --arg event "$event" --arg sha "$WORKSPACE_SHA" '{event_type:$event,client_payload:{workspace_sha:$sha}}' |
    gh api --method POST "repos/$GITHUB_REPOSITORY/dispatches" --input -
  echo "[ROUTER][DISPATCHED] event=$event source=$WORKSPACE_SHA"
done
