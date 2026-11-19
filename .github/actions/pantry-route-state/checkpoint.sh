#!/usr/bin/env bash
set -euo pipefail

fail() { printf '::error::%s\n' "$1" >&2; exit 1; }
skip() { printf '::notice::[PANTRY/ROUTE-STATE][SKIP] %s\n' "$1"; exit 0; }

source_root="${PANTRY_ROUTE_SOURCE_ROOT:-}"
source_sha="${PANTRY_ROUTE_SOURCE_SHA:-}"
source_sha="${source_sha,,}"
[[ -n "$source_root" && "$source_sha" =~ ^[0-9a-f]{40}$ ]] || fail 'Pantry route checkpoint inputs rejected'
pantry_root="$(cd -- "$source_root" 2>/dev/null && pwd -P)" || fail 'Pantry route source folder unavailable'
workspace_root="$(git -C "$pantry_root" rev-parse --show-toplevel 2>/dev/null)" || fail 'Pantry route source is not a Git checkout'
workspace_root="$(cd -- "$workspace_root" 2>/dev/null && pwd -P)" || fail 'Pantry route Workspace folder unavailable'
[[ "$pantry_root" == "$workspace_root/Distribution" && ! -e "$pantry_root/.git" && ! -L "$pantry_root/.git" ]] || fail 'Pantry route source must be the integrated Workspace Distribution'
[[ -f "$pantry_root/SrcVersion.ini" && ! -L "$pantry_root/SrcVersion.ini" ]] || fail 'Pantry route source configuration unavailable'
local_head="$(git -C "$workspace_root" rev-parse --verify HEAD 2>/dev/null)" || fail 'Pantry route source commit unavailable'
[[ "$local_head" == "$source_sha" ]] || fail 'Pantry route source commit changed locally'

state_path='release/pantry-core-route-state.ini'
state="$pantry_root/$state_path"
[[ -d "$pantry_root/release" && ! -L "$pantry_root/release" && -f "$state" && ! -L "$state" ]] || fail 'Generated Pantry route state unavailable or outside its owned folder'
first_line=''
if ! IFS= read -r first_line < "$state"; then
  [[ -n "$first_line" ]] || fail 'Generated Pantry route state is empty or unreadable'
fi
[[ "${first_line%$'\r'}" == "; Pantry-Source: $source_sha" ]] || fail 'Generated Pantry route state source pin rejected'

# Canonical prepare restored the tracked input after verifying this checkpoint.
# Generated release/ data stays out of Workspace Git; only ciphertext leaves the job.
git -C "$pantry_root" diff --cached --quiet -- SrcVersion.ini || fail 'Pantry route configuration has unexpected index changes'
git -C "$pantry_root" diff --quiet -- SrcVersion.ini || fail 'Pantry route configuration was not restored by verified preparation'
python "$GITHUB_ACTION_PATH/../../scripts/pantry_route_state.py" capture \
  --source-root "$pantry_root" --source-sha "$source_sha" \
  --core-root shelf --output "$RUNNER_TEMP/kyron-route-state/route-state.enc"
