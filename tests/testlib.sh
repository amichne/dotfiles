#!/usr/bin/env bash

set -euo pipefail

TEST_PASS_COUNT=0
TEST_FAIL_COUNT=0

test_pass() {
    TEST_PASS_COUNT=$((TEST_PASS_COUNT + 1))
    printf 'PASS: %s\n' "$1"
}

test_fail() {
    TEST_FAIL_COUNT=$((TEST_FAIL_COUNT + 1))
    printf 'FAIL: %s\n' "$1" >&2
    if [ "$#" -gt 1 ]; then
        printf '  %s\n' "$2" >&2
    fi
}

assert_success() {
    local label="$1"
    shift
    if "$@"; then
        test_pass "$label"
    else
        test_fail "$label" "expected exit 0"
    fi
}

assert_failure_contains() {
    local label="$1"
    local expected="$2"
    shift 2
    local output_file="$TEST_TMP/assert-output"
    local command_status=0

    "$@" >"$output_file" 2>&1 || command_status=$?
    if [ "$command_status" -eq 0 ]; then
        test_fail "$label" "expected a non-zero exit"
        return
    fi
    if grep -qF "$expected" "$output_file"; then
        test_pass "$label"
    else
        test_fail "$label" "missing error: $expected"
    fi
}

assert_output_contains() {
    local label="$1"
    local expected="$2"
    shift 2
    local output_file="$TEST_TMP/assert-output"

    if ! "$@" >"$output_file"; then
        test_fail "$label" "command exited non-zero"
        return
    fi
    if grep -qF "$expected" "$output_file"; then
        test_pass "$label"
    else
        test_fail "$label" "missing output: $expected"
    fi
}

assert_output_empty() {
    local label="$1"
    shift
    local output_file="$TEST_TMP/assert-output"

    if ! "$@" >"$output_file"; then
        test_fail "$label" "command exited non-zero"
        return
    fi
    if [ ! -s "$output_file" ]; then
        test_pass "$label"
    else
        test_fail "$label" "expected no output"
    fi
}

test_summary() {
    printf 'Passed: %d  Failed: %d\n' "$TEST_PASS_COUNT" "$TEST_FAIL_COUNT"
    [ "$TEST_FAIL_COUNT" -eq 0 ]
}
