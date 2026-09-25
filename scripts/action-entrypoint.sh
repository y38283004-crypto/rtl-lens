#!/usr/bin/env bash
set -uo pipefail

scan_exit_code=2
report_paths=()

emit_outputs() {
  {
    printf 'scan-exit-code=%s\n' "$scan_exit_code"
    printf 'report-paths<<RTL_LENS_REPORT_PATHS\n'
    if ((${#report_paths[@]} > 0)); then
      printf '%s\n' "${report_paths[@]}"
    fi
    printf 'RTL_LENS_REPORT_PATHS\n'
  } >>"$GITHUB_OUTPUT"
}

finish_without_scan() {
  scan_exit_code="$1"
  shift
  printf 'RTL Lens Action: %s\n' "$*" >&2
  emit_outputs
  exit 0
}

if [[ -z ${GITHUB_OUTPUT:-} ]]; then
  printf 'RTL Lens Action: GITHUB_OUTPUT is required.\n' >&2
  exit 2
fi
if [[ $(uname -s) != Linux ]]; then
  finish_without_scan 2 "only Linux Docker hosts are supported"
fi
if ! command -v docker >/dev/null 2>&1; then
  finish_without_scan 2 "Docker is required"
fi
if ! command -v realpath >/dev/null 2>&1; then
  finish_without_scan 2 "realpath is required"
fi
if [[ -z ${GITHUB_WORKSPACE:-} || -z ${GITHUB_ACTION_PATH:-} ]]; then
  finish_without_scan 2 "GITHUB_WORKSPACE and GITHUB_ACTION_PATH are required"
fi

project_input=${RTL_LENS_INPUT_PROJECT_PATH-}
config_input=${RTL_LENS_INPUT_CONFIG_PATH-}
fail_on=${RTL_LENS_INPUT_FAIL_ON-}
report_format=${RTL_LENS_INPUT_REPORT_FORMAT-}
upload_report=${RTL_LENS_INPUT_UPLOAD_REPORT-}

if [[ -z $project_input ]]; then
  finish_without_scan 3 "project-path must not be empty"
fi
case "$fail_on" in
  error|warning|info) ;;
  *) finish_without_scan 3 "fail-on must be error, warning, or info" ;;
esac
case "$report_format" in
  json|html|both) ;;
  *) finish_without_scan 3 "report-format must be json, html, or both" ;;
esac
case "$upload_report" in
  true|false) ;;
  *) finish_without_scan 3 "upload-report must be exactly true or false" ;;
esac

workspace=$(realpath -e -- "$GITHUB_WORKSPACE") || finish_without_scan 3 "workspace does not exist"
action_path=$(realpath -e -- "$GITHUB_ACTION_PATH") || finish_without_scan 2 "Action path does not exist"

canonicalize_workspace_input() {
  local input=$1
  local candidate
  if [[ $input == /* ]]; then
    candidate=$input
  else
    candidate="$workspace/$input"
  fi
  realpath -e -- "$candidate"
}

is_within_workspace() {
  local candidate=$1
  [[ $candidate == "$workspace" || $candidate == "$workspace/"* ]]
}

project_path=$(canonicalize_workspace_input "$project_input") \
  || finish_without_scan 3 "project-path does not exist"
if ! is_within_workspace "$project_path" || [[ ! -d $project_path ]]; then
  finish_without_scan 3 "project-path must be a directory beneath the workspace"
fi

config_path=""
if [[ -n $config_input ]]; then
  config_path=$(canonicalize_workspace_input "$config_input") \
    || finish_without_scan 3 "config-path does not exist"
  if ! is_within_workspace "$config_path" || [[ ! -f $config_path ]]; then
    finish_without_scan 3 "config-path must be a file beneath the workspace"
  fi
fi

report_dir="$workspace/rtl-lens-reports"
if [[ -L $report_dir ]]; then
  finish_without_scan 3 "report directory must not be a symbolic link"
fi
mkdir -p -- "$report_dir" || finish_without_scan 2 "report directory could not be created"
report_dir=$(realpath -e -- "$report_dir") || finish_without_scan 2 "report directory is unavailable"
if ! is_within_workspace "$report_dir"; then
  finish_without_scan 3 "report directory must remain beneath the workspace"
fi

json_report="$report_dir/report.json"
html_report="$report_dir/report.html"
for report in "$json_report" "$html_report"; do
  if [[ -L $report || (-e $report && ! -f $report) ]]; then
    finish_without_scan 3 "report destinations must be regular files or absent"
  fi
  rm -f -- "$report" || finish_without_scan 2 "stale reports could not be removed"
done

to_container_path() {
  local host_path=$1
  if [[ $host_path == "$workspace" ]]; then
    printf '/workspace'
  else
    printf '/workspace/%s' "${host_path#"$workspace/"}"
  fi
}

project_container=$(to_container_path "$project_path")
config_container=""
if [[ -n $config_path ]]; then
  config_container=$(to_container_path "$config_path")
fi

image_name=rtl-lens-action:local
if ! docker build --target release --tag "$image_name" "$action_path"; then
  finish_without_scan 2 "container build failed"
fi

uid=$(id -u)
gid=$(id -g)
git_mask_args=()
if [[ -d $workspace/.git ]]; then
  git_mask_args+=(
    --tmpfs "/workspace/.git:rw,noexec,nosuid,nodev,size=64k,mode=700"
  )
elif [[ -e $workspace/.git || -L $workspace/.git ]]; then
  git_mask_args+=(
    --mount "type=bind,source=/dev/null,target=/workspace/.git,readonly"
  )
fi
docker_args=(
  run
  --rm
  --network=none
  --user "$uid:$gid"
  --read-only
  --cap-drop=ALL
  --security-opt=no-new-privileges
  --pids-limit=256
  --tmpfs "/tmp/rtl-lens-home:rw,noexec,nosuid,nodev,uid=$uid,gid=$gid,mode=700"
  --env HOME=/tmp/rtl-lens-home
  --env TMPDIR=/tmp/rtl-lens-home
  --volume "$workspace:/workspace:ro"
  --volume "$report_dir:/workspace/rtl-lens-reports:rw"
  "${git_mask_args[@]}"
  --workdir /workspace
)
scan_args=(
  scan
  "$project_container"
  --fail-on "$fail_on"
  --json /workspace/rtl-lens-reports/report.json
  --html /workspace/rtl-lens-reports/report.html
)
if [[ -n $config_container ]]; then
  scan_args+=(--config "$config_container")
fi

docker "${docker_args[@]}" "$image_name" "${scan_args[@]}"
scan_exit_code=$?
if ((scan_exit_code < 0 || scan_exit_code > 3)); then
  printf 'RTL Lens Action: container runtime returned %s; mapping it to exit code 2.\n' \
    "$scan_exit_code" >&2
  scan_exit_code=2
fi

case "$report_format" in
  json)
    rm -f -- "$html_report"
    [[ -f $json_report && ! -L $json_report ]] && report_paths+=("$json_report")
    ;;
  html)
    rm -f -- "$json_report"
    [[ -f $html_report && ! -L $html_report ]] && report_paths+=("$html_report")
    ;;
  both)
    [[ -f $json_report && ! -L $json_report ]] && report_paths+=("$json_report")
    [[ -f $html_report && ! -L $html_report ]] && report_paths+=("$html_report")
    ;;
esac

if ((scan_exit_code <= 1 && ${#report_paths[@]} == 0)); then
  printf 'RTL Lens Action: scan completed without the selected report files.\n' >&2
  scan_exit_code=2
fi

emit_outputs
exit 0
