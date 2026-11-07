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

# Only the publisher-generated configuration is restored. An existing staged
# configuration edit is an index error, never permission to discard user work.
git -C "$pantry_root" ls-files --error-unmatch -- SrcVersion.ini >/dev/null 2>&1 || fail 'Pantry route configuration is not tracked'
git -C "$pantry_root" diff --cached --quiet -- SrcVersion.ini 2>/dev/null || fail 'Pantry route configuration has unexpected index changes'
git -C "$pantry_root" restore --source=HEAD --worktree -- SrcVersion.ini 2>/dev/null || fail 'Pantry route generated configuration restoration failed'

read_remote_main() {
  local remote
  remote="$(git -C "$workspace_root" ls-remote --exit-code --refs origin refs/heads/main 2>/dev/null)" || fail 'Pantry route remote main inspection failed'
  [[ "$remote" =~ ^([0-9a-fA-F]{40})[[:space:]]+refs/heads/main$ ]] || fail 'Pantry route remote main response rejected'
  printf '%s' "${BASH_REMATCH[1],,}"
}

remote_sha="$(read_remote_main)" || exit 1
[[ "$remote_sha" == "$source_sha" ]] || skip 'Remote main moved; the verified publication remains valid and the next publish regenerates route state'
git -C "$pantry_root" add --sparse -- "$state_path" >/dev/null 2>&1 || fail 'Pantry route state staging failed'
if git -C "$pantry_root" diff --cached --quiet -- "$state_path" 2>/dev/null; then
  printf '%s\n' '[PANTRY/ROUTE-STATE][UNCHANGED]'
  exit 0
else
  diff_status=$?
  [[ "$diff_status" -eq 1 ]] || fail 'Pantry route state index inspection failed'
fi
git -C "$pantry_root" -c user.name=pvtkyron -c user.email=117467541+pvtkyron@users.noreply.github.com \
  commit --only -m 'distribution: checkpoint Pantry Core route state [control-state]' -- "$state_path" >/dev/null 2>&1 || fail 'Pantry route state commit failed'
candidate="$(git -C "$workspace_root" rev-parse --verify HEAD 2>/dev/null)" || fail 'Pantry route checkpoint commit unavailable'
parents="$(git -C "$workspace_root" show -s --format=%P "$candidate" 2>/dev/null)" || fail 'Pantry route checkpoint parent inspection failed'
changed="$(git -C "$workspace_root" diff-tree --no-commit-id --name-only -r "$candidate" 2>/dev/null)" || fail 'Pantry route checkpoint path inspection failed'
[[ "$parents" == "$source_sha" && "$changed" == "Distribution/$state_path" ]] || fail 'Pantry route checkpoint escaped its exact source and state path'

# Normal push only. A rejected concurrent update must not turn an already
# verified Pantry Core publication into a failure or overwrite its peer.
if git -C "$workspace_root" push origin "$candidate:refs/heads/main" >/dev/null 2>&1; then
  printf '%s\n' '[PANTRY/ROUTE-STATE][PUSHED]'
  exit 0
fi
remote_sha="$(read_remote_main)" || exit 1
if [[ "$remote_sha" == "$candidate" ]]; then
  printf '%s\n' '[PANTRY/ROUTE-STATE][PUSHED] verified after interrupted push'
elif [[ "$remote_sha" != "$source_sha" ]]; then
  skip 'Remote main moved during push; the verified publication remains valid and the peer commit is preserved'
else
  fail 'Pantry route state push failed while remote main was unchanged'
fi
