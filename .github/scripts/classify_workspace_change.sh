#!/usr/bin/env bash
set -euo pipefail

has_kyronlink=false
has_launcher=false
has_lib=false
has_java=false
has_content=false
has_shared_version_header=false
has_other_release_input=false

while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  case "$path" in
    *.md)
      continue
      ;;
    .kyron/control/request.json)
      continue
      ;;
    src/common/Shared/SrcVersionBlob.hpp|src/common/Shared/SrcVersionRouteState.hpp)
      has_shared_version_header=true
      ;;
    KyronLink/*.md)
      continue
      ;;
    KyronLink/*)
      has_kyronlink=true
      ;;
    Launcher/*)
      has_launcher=true
      ;;
    VeraInternal/*)
      has_lib=true
      ;;
    Distribution/src/*)
      has_java=true
      ;;
    Distribution/lua/*|Distribution/img/*|Distribution/assest/*|Distribution/Font/*|Distribution/vm/*|Distribution/enrollment/*|Distribution/dist/InputHost.dex|Distribution/auth/subscription.json|Distribution/client/commands.json)
      has_content=true
      ;;
    etc/*|Shared/*|src/common/Shared/*|Directory.Build.props|Bootstrap/*|NativeBridgeRuntime/*|Distribution/tools/*|Distribution/tests/*|Distribution/security/*|Distribution/auth/*|Distribution/SrcVersion.ini)
      has_other_release_input=true
      ;;
    *)
      ;;
  esac
done

# Kyron Link has independent managed/Android checks; never silently drop it
# when a change also needs the signed Launcher/native release lanes.
if [[ "$has_kyronlink" == true ]]; then
  printf '%s\n' component-kyronlink
fi

if [[ "$has_other_release_input" == true ]]; then
  printf '%s\n' workspace-release
elif [[ "$has_shared_version_header" == true ]]; then
  if [[ "$has_launcher" == true || "$has_lib" == true || "$has_java" == true ]]; then
    printf '%s\n' workspace-release
  else
    printf '%s\n' 'component-launcher component-lib'
  fi
elif [[ "$has_launcher" == true && "$has_lib" == false && "$has_java" == false ]]; then
  printf '%s\n' component-launcher
elif [[ "$has_lib" == true && "$has_launcher" == false && "$has_java" == false ]]; then
  printf '%s\n' component-lib
elif [[ "$has_java" == true && "$has_launcher" == false && "$has_lib" == false ]]; then
  printf '%s\n' component-dex
elif [[ "$has_launcher" == true && "$has_lib" == true ]] || \
     [[ "$has_java" == true && ( "$has_launcher" == true || "$has_lib" == true ) ]]; then
  # Mixed component changes keep the atomic full-release/source validation path.
  printf '%s\n' workspace-release
else
  # Distribution/src is routed by pantry-watch to DEX; docs/control-only edits
  # do not need a Workspace compiler lane.
  if [[ "$has_content" == true ]]; then
    printf '%s\n' pantry-delta
  elif [[ "$has_kyronlink" == false ]]; then
    printf '%s\n' none
  fi
fi
