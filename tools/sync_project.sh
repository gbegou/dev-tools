#!/usr/bin/env bash
# Copy the tracked files of a project between its official repository and its GitHub copy,
# without git history (the destination gets plain file changes, to commit as you like).
#
#   project/                  <- ROOT (default: current directory, or $ROOT)
#       <name>/               official repository (e.g. GitLab)
#       gh/<name>/            GitHub repository
#
# Usage:
#   sync_project.sh [--apply] [--force] <name> to-github   [ref]   # ref default: HEAD of the official repo
#   sync_project.sh [--apply] [--force] <name> to-official <ref>   # e.g. origin/merge/viscosity-protocol
#   sync_project.sh -h | --help                                    # this help
#
# Without --apply, nothing is written: the script shows what would change (dry run).
# --force: accept a destination with uncommitted changes (they would be overwritten).
#
# What is copied: exactly the files tracked at <ref> (git archive), i.e. no .git, no build
# directories, no virtual environments, no caches, no untracked files. Files that the
# destination's git tracks and the source no longer has are removed at the destination.
#
# Never touched at the destination: .git, the submodule checkouts (their paths are read
# from both repositories, wherever they are), and every file the destination's git does not
# track (build directories, virtual environments, caches, local files).
#   - to-github:   .gitmodules is copied, and the submodules are registered at the commits of
#                  the official repo (gitlinks), so that the GitHub repo builds the same thing.
#                  GitHub-only files (.github/) are kept.
#   - to-official: the official .gitmodules is kept; the submodules of <ref> (URL, commit) are
#                  compared with the official ones, and a git-pin-submodule command (in this
#                  directory; `git-pin-submodule --help`) is printed for each one to align
#                  (a submodule missing from the official .gitmodules, or with another URL,
#                  would make the official CI clone the wrong URL or fail).
#                  GitHub-only files (.github/) are not copied.
# Paths matching .claude/ are never copied, and the exported files are searched for
# mentions of claude/anthropic (reported, not modified).
set -euo pipefail

# the comment block at the top of this file, without the leading "# "
usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; }

apply=false
force=false
while [[ $# -gt 0 && $1 == -* ]]; do
  case $1 in
    -h|--help) usage; exit 0 ;;
    --apply) apply=true ;;
    --force) force=true ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done
if [[ $# -lt 2 ]]; then
  usage >&2
  exit 2
fi

name=$1
direction=$2
ref=${3:-}
root=${ROOT:-$PWD}
official="$root/$name"
github="$root/gh/$name"

case $direction in
  to-github)
    src=$official; dst=$github
    ref=${ref:-HEAD}
    excludes=(/.git /.github /.claude)
    ;;
  to-official)
    src=$github; dst=$official
    if [[ -z $ref ]]; then echo "to-official needs a ref, e.g. origin/<tip-branch>" >&2; exit 2; fi
    excludes=(/.git /.gitmodules /.github /.claude)
    ;;
  *) echo "direction must be to-github or to-official, got: $direction" >&2; exit 2 ;;
esac

command -v rsync >/dev/null || { echo "rsync is required" >&2; exit 1; }
for repo in "$src" "$dst"; do
  git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git repository: $repo" >&2; exit 1; }
done

# ---- the source ref
if [[ $direction == to-official ]]; then
  git -C "$src" fetch --quiet origin
fi
sha=$(git -C "$src" rev-parse --verify --quiet "$ref^{commit}") || { echo "unknown ref in $src: $ref" >&2; exit 1; }
echo "source      : $src @ $ref ($(git -C "$src" rev-parse --short "$sha"))"
echo "destination : $dst"

# ---- submodule paths (gitlinks) of the source ref and of the destination: never mirrored
submodules=$( { git -C "$src" ls-tree -r "$sha" | awk '$2 == "commit" {print $4}'
                git -C "$dst" ls-files -s | awk '$1 == "160000" {print $4}'; } | sort -u)
for path in $submodules; do excludes+=("/$path"); done

# ---- the destination must be clean (uncommitted changes to tracked files would be lost;
#      untracked files are never touched)
if [[ -n $(git -C "$dst" status --porcelain --ignore-submodules=all --untracked-files=no) ]] && ! $force; then
  echo "the destination has uncommitted changes (use --force to overwrite them):" >&2
  git -C "$dst" status --short --ignore-submodules=all --untracked-files=no >&2
  exit 1
fi

# ---- export the tracked files
export_dir=$(mktemp -d)
trap 'rm -rf "$export_dir"' EXIT
git -C "$src" archive "$sha" | tar -x -C "$export_dir"
rm -rf "$export_dir/.claude"

# ---- copy into the destination (no rsync --delete: untracked files, e.g. builds, are kept)
rsync_opts=(-a --checksum --itemize-changes)   # checksum: list real content changes only
for e in "${excludes[@]}"; do rsync_opts+=(--exclude "$e"); done
$apply || rsync_opts+=(--dry-run)
echo
echo "== files"
# rsync --itemize-changes prints one line per changed item: an 11-character code, then the
# path. The code reads YXcstpoguax:
#   Y  what happens: > (sent to the destination), c (created: a directory), * (a message,
#      e.g. *deleting), . (not transferred, attributes only)
#   X  the type: f (file), d (directory), L (symlink)
#   then one character per attribute, + when the item is new (>f+++++++++), . when the
#   attribute is unchanged, or its letter when it changes: c (checksum, i.e. the content),
#   s (size), t (time), p (permissions), o/g (owner/group).
# Only the transferred files matter here (the directories follow; a time stamp alone, which
# the export always changes, is reported by rsync as .f..t...... and ignored), in words:
#   added     the file is not at the destination
#   updated   its content differs (--checksum)
#   removed   tracked at the destination and absent from the source (computed below)
changes=$(rsync "${rsync_opts[@]}" "$export_dir/" "$dst/")   # set -e: stops on an rsync error
changes=$(awk '$1 ~ /^>[fL]/ { print ($1 ~ /\+\+\+/ ? "added    " : "updated  "), $2 }' <<<"$changes")
# removed: tracked at the destination (not a submodule, not excluded), absent from the export
excluded() { local e; for e in "${excludes[@]}"; do [[ /$1 == "$e" || /$1 == "$e"/* ]] && return 0; done; return 1; }
removed=()
while IFS= read -r file; do
  excluded "$file" || [[ -e $export_dir/$file || -L $export_dir/$file ]] || removed+=("$file")
done < <(git -C "$dst" -c core.quotepath=off ls-files -s | awk '$1 != "160000"' | cut -f2-)
for file in "${removed[@]}"; do
  changes+=$'\n'"removed   $file"
  if $apply; then
    rm -f -- "$dst/$file"
    rmdir -p --ignore-fail-on-non-empty -- "$(dirname -- "$dst/$file")" 2>/dev/null || true
  fi
done
changes=$(sed '/^$/d' <<<"$changes")
echo "${changes:-(no change)}"

# ---- submodules
# A field (url, branch) of the submodule at a path in a .gitmodules file (empty if absent)
field_of() {
  [[ -f $1 ]] || return 0
  git config -f "$1" --get-regexp '^submodule\..*\.path$' | while read -r key value; do
    [[ $value == "$2" ]] && git config -f "$1" --get "${key%.path}.$3"
  done
  return 0
}
# The branch to pin a submodule on: the one in the source's .gitmodules (the commit is on it),
# else the official one, else a branch whose tip is the commit, else the default branch of the
# repository (<branch> if it cannot be reached)
branch_of() {  # path url commit
  local branch refs
  branch=$(field_of "$export_dir/.gitmodules" "$1" branch)
  [[ -n $branch ]] || branch=$(field_of "$dst/.gitmodules" "$1" branch)
  if [[ -z $branch ]]; then
    refs=$(GIT_TERMINAL_PROMPT=0 git ls-remote --symref "$2" HEAD 'refs/heads/*' 2>/dev/null || true)
    branch=$(awk -v c="$3" '$1 == c && $2 ~ /^refs\/heads\// {sub("refs/heads/", "", $2); print $2; exit}' <<<"$refs")
    [[ -n $branch ]] || branch=$(awk '$1 == "ref:" {sub("refs/heads/", "", $2); print $2; exit}' <<<"$refs")
  fi
  echo "${branch:-<branch>}"
}
echo
echo "== submodules"
while read -r _ type subsha path; do
  [[ $type == commit ]] || continue
  current=$(git -C "$dst" ls-files -s -- "$path" | awk '$1 == "160000" {print $2}')
  if [[ $direction == to-github ]]; then
    if [[ $subsha == "$current" ]]; then
      echo "  $path: same commit ${subsha:0:7}"
    else
      echo "  $path: register ${subsha:0:7} (was ${current:0:7})"
      if $apply; then
        # an empty directory is an unpopulated submodule (otherwise `git add -A` records a deletion)
        mkdir -p "$dst/$path"
        git -C "$dst" update-index --add --cacheinfo "160000,$subsha,$path"
      fi
    fi
    continue
  fi
  src_url=$(field_of "$export_dir/.gitmodules" "$path" url)
  dst_url=$(field_of "$dst/.gitmodules" "$path" url)
  if [[ -n $dst_url && $dst_url == "$src_url" && $subsha == "$current" ]]; then
    echo "  $path: same URL and commit ${subsha:0:7}"
    continue
  fi
  url=${dst_url:-$src_url}
  if [[ -z $dst_url ]]; then
    echo "  $path: not in the official .gitmodules"
  elif [[ $dst_url != "$src_url" ]]; then
    # may be intended (e.g. a dependency mirrored on the official server): kept in the command
    echo "  $path: official URL $dst_url, github $src_url (if the official one is wrong,"
    echo "      use the github one in the command)"
  fi
  [[ $subsha == "$current" ]] || echo "  $path: official commit ${current:-none}, github ${subsha:0:7}" | sed 's/\([0-9a-f]\{7\}\)[0-9a-f]\{33\}/\1/'

  echo "      (cd $dst && git-pin-submodule $path -u $url -b $(branch_of "$path" "$src_url" "$subsha") -c $subsha)"
done < <(git -C "$src" ls-tree -r "$sha")

# ---- traces
echo
echo "== mentions of claude/anthropic in the copied files"
if [[ $direction == to-official ]]; then
  hits=$(cd "$export_dir" && grep -rniI -e claude -e anthropic --exclude-dir=.github . || true)
else
  hits=$(cd "$export_dir" && grep -rniI -e claude -e anthropic . || true)
fi
echo "${hits:-(none)}"

echo
if $apply; then
  echo "done. Review and commit in $dst:"
  echo "  git -C $dst status && git -C $dst diff --stat"
else
  echo "dry run: nothing written. Run again with --apply to copy."
fi
