# dev-tools

Rules and tools I give to Claude, reusable across projects.

| Path | Content |
| --- | --- |
| `CLAUDE.md` | The rules: git workflow, reviews, audits, Python, C++, tests and docs, dependencies, GitLab CI, official/GitHub sync |
| `tools/sync_project.sh` | Raw copy (no git history) between an official repository and its GitHub copy; `--help` for usage |
| `tools/git-pin-submodule` | Adds or updates a submodule (`--url`, `--branch`, `--commit` or `--tag`), staged; what is not given comes from `.gitmodules` or the branch's tip, so `git pin-submodule <path>` updates a submodule and `-b dev/official` switches its branch (`git pin-submodule` once on PATH); `--help` explains each git command |
| `tools/check_ci.py` | Checks GitLab CI files: script lines are strings, `needs`/`extends` resolve |
| `tools/pyright_report.py` | Works through a basedpyright report (`basedpyright --outputjson`): `summary` counts errors and warnings by rule, file and package used; `list` prints them as `path:line:column` lines, filtered by severity, rule, file or package (e.g. the calls into a library whose API changed), with `--fail` for a CI gate; guide in `doc/pyright_report.md`, options in `--help` |
| `tools/test/` | Tests of the tools (`python -m pytest tools/test`) |
| `templates/gitlab-ci/` | GitLab CI layout for a cluster with modules and Jacamar runners (from pomac: replace the project name, ctest patterns and modules) |
| `doc/official_and_github.md` | The workflow between an official repository and its GitHub copy, with the two tools, step by step |
| `doc/pyright_report.md` | Working through a basedpyright report with `tools/pyright_report.py`: a worked example, the filters, recipes (a library's API change, triage, CI gate) |

## Use in a project

Projects carry no `CLAUDE.md`. Give the rules to Claude from this repository (a sibling
checkout, or a session that has it), or copy `CLAUDE.md` into `~/.claude/CLAUDE.md` to apply
them to every project on a machine. Project-specific rules are in each project's developer
guide.

## Adding a rule

A rule goes here if it applies beyond one project. A project-specific rule (names, physics,
module versions) goes in that project's developer guide.
