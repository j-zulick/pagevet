#!/usr/bin/env bash
# Draft-first release steps for .github/workflows/release.yml (the review's recommendation, PageVet chat 2026-11-26).
#   release-steps.sh create   <version> <commit> <title>   make (or reuse) a DRAFT release with the CHANGELOG notes;
#                                                           prints publish=true|false for $GITHUB_OUTPUT
#   release-steps.sh finalize <version>                    when every asset is uploaded, publish the draft and mark it
#                                                           Latest; stops (draft stays hidden) if anything is missing
#   release-steps.sh notes    <version>                    print the release notes (see below)
# Expected assets: explore.html, pagevet-<v>-py3-none-any.whl, pagevet-<v>.tar.gz. Uses gh with GH_TOKEN.
# Release notes are short (Joe's edit list, 2026-11-26 06:12 ET): one sentence, three bullets naming what users can try,
# one sentence on the assets, a link to CHANGELOG. They come from docs/releases/v<version>.md when it exists (checked for
# that shape); otherwise they are built from the CHANGELOG section: its first three bullets, each cut to its first sentence.
set -euo pipefail
cmd="${1:?create|finalize}"; v="${2:?version}"; tag="v$v"
state() { gh release view "$tag" --json isDraft --jq 'if .isDraft then "draft" else "published" end' 2>/dev/null || echo none; }
case "$cmd" in
  create)
    sha="${3:?commit}"; title="${4:?title}"
    case "$(state)" in
      published) echo "$tag is already published; nothing to do" >&2; echo "publish=false";;
      draft) echo "reusing the existing draft $tag" >&2; echo "publish=true";;
      none)
        notes="$(mktemp)"
        bash "$0" notes "$v" > "$notes" || exit 1
        gh release create "$tag" --draft --target "$sha" --title "$title" --notes-file "$notes" >/dev/null
        [ "$(state)" = draft ] || { echo "the draft $tag was not created" >&2; exit 1; }
        echo "publish=true";;
    esac;;
  finalize)
    want="explore.html pagevet-$v-py3-none-any.whl pagevet-$v.tar.gz"
    have="$(gh release view "$tag" --json assets --jq '[.assets[] | select(.size > 0) | .name] | sort | join(" ")')"
    [ "$have" = "$want" ] || { echo "assets of $tag are '$have', want '$want'; the release stays a draft" >&2; exit 1; }
    gh release edit "$tag" --draft=false --latest >/dev/null
    [ "$(state)" = published ] || { echo "$tag is still a draft after publishing" >&2; exit 1; }
    latest="$(gh release view --json tagName --jq .tagName)"
    [ "$latest" = "$tag" ] || { echo "Latest is $latest, not $tag" >&2; exit 1; }
    echo "$tag published with $want and marked Latest";;
  notes)
    file="docs/releases/$tag.md"
    if [ -f "$file" ]; then
      [ "$(grep -c '^- ' "$file")" = 3 ] || { echo "$file must have exactly three bullets" >&2; exit 1; }
      grep -q '^\*\*Assets:\*\*' "$file" || { echo "$file has no **Assets:** sentence" >&2; exit 1; }
      grep -q 'CHANGELOG' "$file" || { echo "$file has no link to CHANGELOG" >&2; exit 1; }
      cat "$file"
    else
      section="$(awk -v v="$v" 'index($0, "## [" v "]") == 1 {on = 1; next} /^## / {on = 0} on' CHANGELOG.md)"
      [ -n "$section" ] || { echo "CHANGELOG.md has no section for $v" >&2; exit 1; }
      [ "$(echo "$section" | grep -c '^- ')" -ge 3 ] || { echo "the CHANGELOG section for $v has fewer than three bullets; write $file" >&2; exit 1; }
      echo "PageVet $v adds the following; every change is in the CHANGELOG."; echo
      echo "$section" | grep '^- ' | head -3 | sed -E 's/^(- (\*\*[^*]+\*\*)?[^.]*\.).*/\1/'
      echo
      echo "**Assets:** the wheel and source archive install PageVet without cloning the repository. \`explore.html\` is the field-study explorer as one file you can open offline."
      echo; echo "All changes and measurements: [CHANGELOG](https://github.com/${GITHUB_REPOSITORY:-j-zulick/pagevet}/blob/$tag/CHANGELOG.md)."
    fi;;
  *) echo "unknown command $cmd" >&2; exit 2;;
esac
