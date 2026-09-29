#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
guard_output=$(mktemp -t reforge-release-url-guard.XXXXXX)
trap 'rm -f -- "$guard_output"' EXIT

check_guard() {
    local expected=$1
    local label=$2
    shift 2
    local actual=fail
    if ./gradlew :app:validateReleaseBackendUrl --console=plain "$@" >"$guard_output" 2>&1; then
        actual=pass
    fi
    if [[ "$actual" != "$expected" ]]; then
        cat "$guard_output"
        printf 'FAIL %s: expected %s, got %s\n' "$label" "$expected" "$actual"
        exit 1
    fi
    if [[ "$actual" == fail ]] && ! grep -Fq 'Release requires REFORGE_BACKEND_BASE_URL to be an explicit HTTPS URL.' "$guard_output"; then
        cat "$guard_output"
        exit 1
    fi
    printf 'PASS %s (%s)\n' "$label" "$actual"
}

check_guard fail missing
check_guard fail http -PREFORGE_BACKEND_BASE_URL=http://example.invalid
check_guard fail port-zero -PREFORGE_BACKEND_BASE_URL=https://example.invalid:0
check_guard fail port-overflow -PREFORGE_BACKEND_BASE_URL=https://example.invalid:65536
check_guard fail credentials -PREFORGE_BACKEND_BASE_URL=https://user:pass@example.invalid
check_guard fail query '-PREFORGE_BACKEND_BASE_URL=https://example.invalid?key=value'
check_guard fail fragment '-PREFORGE_BACKEND_BASE_URL=https://example.invalid#fragment'
check_guard fail placeholder '-PREFORGE_BACKEND_BASE_URL=https://example.invalid/$(BACKEND_PATH)'
check_guard pass default-port -PREFORGE_BACKEND_BASE_URL=https://example.invalid
check_guard pass lowest-port -PREFORGE_BACKEND_BASE_URL=https://example.invalid:1
check_guard pass highest-port -PREFORGE_BACKEND_BASE_URL=https://example.invalid:65535
