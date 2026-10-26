#!/usr/bin/bash
# Shared helpers for build steps. Source this file; it defines functions only.

# GitHub Actions log groups (plain text elsewhere).
group() { echo "::group::$*"; }
endgroup() { echo "::endgroup::"; }

log() { echo "[tamarack-build] $*"; }

die() {
    echo "[tamarack-build] ERROR: $*" >&2
    exit 1
}

# require_file PATH... : fail the build if an expected file is missing.
require_file() {
    local path
    for path in "$@"; do
        [[ -e "${path}" ]] || die "expected file is missing: ${path}"
    done
}

# load_brand : export BRAND_* variables generated from branding/brand.toml.
load_brand() {
    local env_file="${CTX:-/ctx}/generated/usr/share/tamarack/branding.env"
    require_file "${env_file}"
    set -a
    # shellcheck source=/dev/null
    source "${env_file}"
    set +a
}

# set_os_release KEY VALUE : replace or append a key in /usr/lib/os-release.
set_os_release() {
    local key="$1" value="$2" file=/usr/lib/os-release
    if grep -q "^${key}=" "${file}"; then
        # Use a delimiter that cannot appear in our values.
        sed -i "s|^${key}=.*|${key}=\"${value}\"|" "${file}"
    else
        echo "${key}=\"${value}\"" >>"${file}"
    fi
}
