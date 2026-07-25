#!/usr/bin/env bash

set -euo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly repo_root="$(git -C "$script_dir/../.." rev-parse --show-toplevel)"
readonly output_dir="site-versioned"
mike=(uv run --locked --no-dev --group docs mike)

export GIT_AUTHOR_NAME="github-actions[bot]"
export GIT_AUTHOR_EMAIL="41898282+github-actions[bot]@users.noreply.github.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

prepare_history() {
  git fetch origin --force --tags
  if git ls-remote --exit-code --heads origin gh-pages > /dev/null; then
    git fetch origin gh-pages --depth=1
  fi
}

resolve_version() {
  if [[ "$DOCS_REF_TYPE" != tag ]]; then
    test "$DOCS_REF_NAME" = main
    identifier="dev"
    title="Development"
    is_latest=false
    return
  fi

  local release_version release_line latest_line_release latest_release
  release_version="$(
    python3 -c 'import runpy; print(runpy.run_path("src/ngh2/_version.py")["__version__"])'
  )"
  grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' <<< "$release_version"
  test "$DOCS_REF_NAME" = "v$release_version"

  release_line="${release_version%.*}"
  latest_line_release="$(
    git tag --list "v$release_line.*" --sort=-version:refname |
      awk '/^v[0-9]+\.[0-9]+\.[0-9]+$/ {
        sub(/^v/, "")
        print
        exit
      }'
  )"
  if [[ "$release_version" != "$latest_line_release" ]]; then
    echo "refusing to replace $release_line docs with older $release_version" >&2
    exit 1
  fi

  latest_release="$(
    git tag --list "v*" --sort=-version:refname |
      awk '/^v[0-9]+\.[0-9]+\.[0-9]+$/ {
        sub(/^v/, "")
        print
        exit
      }'
  )"
  identifier="$release_line"
  title="$release_version"
  if [[ "$release_version" = "$latest_release" ]]; then
    is_latest=true
  else
    is_latest=false
  fi
}

deploy_version() {
  if [[ "$is_latest" = true ]]; then
    "${mike[@]}" deploy \
      --update-aliases \
      --alias-type redirect \
      --title "$title" \
      "$identifier" latest
    "${mike[@]}" set-default latest
  else
    "${mike[@]}" deploy --title "$title" "$identifier"
    if [[ "$identifier" = dev ]] &&
      ! "${mike[@]}" list latest > /dev/null 2>&1
    then
      "${mike[@]}" alias --alias-type redirect dev latest
      "${mike[@]}" set-default latest
    fi
  fi
  git push origin gh-pages
}

stage_site() {
  if [[ -e "$output_dir" ]]; then
    echo "$output_dir already exists" >&2
    exit 1
  fi
  mkdir "$output_dir"
  git archive gh-pages | tar -x -C "$output_dir"
}

main() {
  : "${DOCS_REF_NAME:?DOCS_REF_NAME is required}"
  : "${DOCS_REF_TYPE:?DOCS_REF_TYPE is required}"

  cd "$repo_root"
  prepare_history
  resolve_version
  echo "publishing documentation as $title ($identifier)"
  deploy_version
  stage_site
}

main "$@"
