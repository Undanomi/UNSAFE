#!/bin/bash

# Sourced by every non-interactive Bash process launched during provisioning.
# It reports the originating script and line without enabling command tracing,
# which could expose generated credentials in build logs.
slsg_report_script_failure() {
    local status=$?
    local source_file="${BASH_SOURCE[1]:-${BASH_SOURCE[0]:-unknown}}"
    local source_line="${BASH_LINENO[0]:-0}"
    trap - ERR
    printf 'SLSG_SCRIPT_FAIL phase=%s source=%s line=%s exit=%s\n' \
        "${SLSG_PHASE:-unknown}" "$source_file" "$source_line" "$status" >&2
    exit "$status"
}

set -E
trap 'slsg_report_script_failure' ERR
