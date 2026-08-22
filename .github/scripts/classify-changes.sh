#!/bin/sh

set -eu

classify() {
    code=false
    docs=false

    while IFS= read -r path; do
        case "$path" in
            .readthedocs.yaml | \
            .github/workflows/ci.yml | \
            .gitmodules | .python-version | CMakeLists.txt | \
            CHANGELOG.md | CONTRIBUTING.md | LICENSE | README.md | \
            SECURITY.md | docs/assets/* | docs/overrides/* | \
            docs/griffe_runtime_docstrings.py | docs/site/* | \
            examples/* | pyproject.toml | src/ngh2/* | uv.lock | \
            vendor/nghttp2 | vendor/nghttp2/* | zensical.toml)
                docs=true
                ;;
        esac

        case "$path" in
            docs/griffe_runtime_docstrings.py | examples/python/*)
                code=true
                ;;
            .agents/* | .github/dependabot.yml | \
            .github/ISSUE_TEMPLATE/* | .readthedocs.yaml | \
            .github/pull_request_template.md | \
            CODE_OF_CONDUCT.md | docs/* | zensical.toml | *.md | LICENSE*)
                ;;
            *)
                code=true
                ;;
        esac
    done

    printf 'code=%s\ndocs=%s\n' "$code" "$docs"
}

if [ "${1-}" = "--all" ]; then
    printf 'code=true\ndocs=true\n'
    exit
fi

if [ "${1-}" = "--self-test" ]; then
    test "$(printf '%s\n' README.md | classify)" = "code=false
docs=true"
    test "$(printf '%s\n' CODE_OF_CONDUCT.md | classify)" = "code=false
docs=false"
    test "$(printf '%s\n' .github/ISSUE_TEMPLATE/01-bug-report.yml | classify)" = "code=false
docs=false"
    test "$(printf '%s\n' .github/dependabot.yml | classify)" = "code=false
docs=false"
    test "$(printf '%s\n' docs/knowledge/tooling/zensical.md | classify)" = "code=false
docs=false"
    test "$(printf '%s\n' docs/site/index.md | classify)" = "code=false
docs=true"
    test "$(printf '%s\n' docs/overrides/main.html | classify)" = "code=false
docs=true"
    test "$(printf '%s\n' SECURITY.md | classify)" = "code=false
docs=true"
    test "$(printf '%s\n' tests/test_connection.py | classify)" = "code=true
docs=false"
    test "$(printf '%s\n' src/ngh2/_core.pyx | classify)" = "code=true
docs=true"
    test "$(printf '%s\n' examples/python/first_round_trip.py | classify)" = "code=true
docs=true"
    test "$(printf '%s\n' docs/griffe_runtime_docstrings.py | classify)" = "code=true
docs=true"
    test "$(printf '%s\n' .github/workflows/ci.yml | classify)" = "code=true
docs=true"
    test "$(printf '%s\n' .readthedocs.yaml | classify)" = "code=false
docs=true"
    test "$(printf '%s\n' vendor/nghttp2 | classify)" = "code=true
docs=true"
    test "$(printf '%s\n' README.md tests/test_connection.py | classify)" = "code=true
docs=true"
    exit
fi

classify
