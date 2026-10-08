# The official repository and its GitHub copy

A project lives in two repositories that share no git history:

- the **official** one (e.g. GitLab), which the cluster CI builds and which the docs and
  package metadata link to;
- its **GitHub copy**, where Claude works, on stacked topic branches.

Files move between the two as plain copies, with no git trace, by `tools/sync_project.sh`.
Submodules are pinned on either side with `tools/git-pin-submodule`. This page is the
workflow; `--help` on each tool gives the details and the git commands behind them.

## Layout on the machine

```
project/                  <- ROOT ($ROOT, or the current directory)
    <name>/               official repository
    gh/<name>/            GitHub repository
```

Put `tools/` on your `PATH`: `git-pin-submodule` is then also `git pin-submodule`.

## From GitHub to the official repository (deploying a tip branch)

1. In the GitHub copy, the tip branch is pushed and validated (every compiler, Debug and
   Release, tests, linters, docs: the rules in `CLAUDE.md`).

2. Dry run, from `project/`:

   ```bash
   sync_project.sh <name> to-official origin/<tip>
   ```

   It fetches the GitHub copy, then prints what would change in the official checkout: the
   files added, updated or removed, and the submodules to align (see below). Nothing is
   written.

3. Apply:

   ```bash
   sync_project.sh --apply <name> to-official origin/<tip>
   ```

   The official checkout gets the files of the tip, as uncommitted changes. What stays
   untouched: `.git`, `.gitmodules` (the official URLs may differ), the submodule checkouts,
   the GitHub-only files (`.github/`), and every file the official git does not track: build
   directories, virtual environments, caches, local files.

4. Align the submodules. The dry run printed one command per submodule whose URL or commit
   differs, ready to paste:

   ```
   external/eigen: official commit none, github bc3b398
       (cd project/kord && git-pin-submodule external/eigen -u https://gitlab.com/libeigen/eigen.git -b 5.0 -c bc3b39870ecb690a623a3f49149a358b95c5781d)
   ```

   A submodule missing from the official `.gitmodules` is added by that command; a different
   URL is reported, and kept in the command only if the official one is wrong (a mirror on the
   official server is a legitimate difference: then drop the `-u`).

5. Review (`git status`, `git diff --cached` for the submodules), build and test in the official
   checkout, commit, push. The commit is yours; the copy carries no author.

A dependency that is itself a project of yours (pomac for kord) goes first: sync pomac, commit
it, then pin kord's `external/pomac` on that official commit, with the official URL.

## From the official repository to GitHub

```bash
sync_project.sh <name> to-github            # dry run, HEAD of the official repo
sync_project.sh --apply <name> to-github
```

`.gitmodules` is copied as is, and the submodules are registered at the official commits
(gitlinks), so that the GitHub copy builds the same thing. GitHub-only files are kept.
Commit in the GitHub copy; then `git submodule update --init --recursive` to populate the
checkouts (recursive: a documentation extension may carry submodules of its own).

## Submodules: `git pin-submodule`

One command for every case: add a submodule, switch its URL or branch, pin a commit or a tag,
or update it to the tip of its branch. What is not given comes from `.gitmodules` (URL,
branch) or is fetched (the branch's tip):

```bash
git pin-submodule external/pomac                        # update to the tip of its recorded branch
git pin-submodule external/pomac -b dev/official        # switch branch, pin its tip
git pin-submodule external/eigen -b 5.0 -t 5.0.1        # a release tag
git pin-submodule external/eigen -b 5.0 -c bc3b398      # an exact commit
git pin-submodule external/new -u https://... -b main   # add a submodule
```

It stages `.gitmodules` and the new submodule commit, and does not commit. It says what it
does: the recorded URL, branch and commit, the target, what changed and by how many commits,
and the date and subject of the pinned commit.

Never `git pull` inside a submodule: on the detached HEAD that submodules normally have it
refuses, and on a branch it can create a merge commit that exists only on your machine, which
every other clone and the CI then fail to fetch. `git pin-submodule <path>` is the update.

## Checking the CI files

`tools/check_ci.py` reads `.gitlab-ci.yml` and the files it includes, and fails on the usual
YAML traps (an unquoted `: ` in a script line becomes a mapping; `needs`/`extends` that do
not resolve). Run it before pushing CI changes on either side.
