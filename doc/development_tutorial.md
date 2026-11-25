# Developing scientific software on the ONERA clusters: a tutorial

This tutorial explains the tools used to develop, build, test and deploy the projects of the team
(numbat, pomac, MARCeL, CLOVIS, dspod...): **git**, **git submodules**, **CMake**,
**project_utils**, **std_e**, **pybind11**, **modulefiles**, **GitLab** and its **CI**. Each
part says what the tool is, why we use it, how we use it, with commands and real examples from
these projects, and the mistakes that newcomers make.

It is written for a developer who knows some C++ and Python, but not necessarily these tools.
The parts can be read separately; part 1 gives the big picture, and the last part walks through
complete examples that use everything together.

**Contents**

1. [The big picture](#1-the-big-picture)
2. [Git](#2-git)
3. [Git submodules](#3-git-submodules)
4. [CMake](#4-cmake)
5. [project_utils](#5-project_utils)
6. [std_e](#6-std_e)
7. [pybind11](#7-pybind11)
8. [Modulefiles](#8-modulefiles)
9. [GitLab](#9-gitlab)
10. [Continuous integration (GitLab CI)](#10-continuous-integration-gitlab-ci)
11. [Putting it all together](#11-putting-it-all-together)
12. [Glossary](#12-glossary)
13. [References](#13-references)


## 1. The big picture

A project such as numbat is a **Python package with compiled C++ kernels**. Users write Python;
the heavy computations run in C++. Such a project depends on other projects of the team (pomac,
MARCeL) and of ONERA (maia, ParaDiGM, std_e, cpp_cgns), which are built together with it.

```
                       GitLab (gitlab.onera.net)
                       the official repositories, merge requests, CI pipelines
                                  ^ git push / git pull
                                  |
  your clone ───────────────────────────────────────────────────────────────────────────┐
  │  numbat/            the project's sources (C++ in *.cpp/*.hpp, Python in *.py)       │
  │  numbat/*.pybind.cpp   the C++ functions exposed to Python (pybind11)                │
  │  external/          the dependencies, as git submodules:                             │
  │     project_utils   CMake helpers (dependencies, tests, Python modules, source.sh)  │
  │     std_e           C++ utilities (logging, arrays...)                               │
  │     pomac, maia, paradigm, ...                                                       │
  │  CMakeLists.txt     how to build it all (CMake)                                      │
  │  modulefiles/       how to set up the environment on the clusters                    │
  │  .gitlab-ci.yml     what the CI runs at every push                                   │
  └──────────────────────────────────────────────────────────────────────────────────────┘
        │ module load (compilers, MPI, Python)     │ cmake: configure, build, test, install
        v                                           v
  the cluster's software stack (socle)        build/  (source.sh)  -->  <root>/socle7/dev/
                                                                         the install, loaded
                                                                         by users with module load
```

What each tool answers:

| Question | Tool |
|---|---|
| How do we keep the history of the code and work in parallel? | git |
| How does a project use an exact version of another project? | git submodules |
| How is the C++ compiled, the Python packaged, the tests registered? | CMake |
| How do our projects find their dependencies and write their test environment? | project_utils |
| Where do the shared C++ utilities (logging, arrays) come from? | std_e |
| How does Python call the C++? | pybind11 |
| How do we get the right compilers, MPI and Python on a cluster, and use an installed version? | modulefiles |
| Where is the code shared and reviewed? | GitLab |
| Who checks that every change builds and passes the tests? | GitLab CI |

A typical day: `git pull` the latest changes, update the submodules, load the build
environment (`module load`), rebuild (`cmake --build`), change the code, run the tests
(`ctest`), commit and push to a branch; the CI builds and tests the branch on the cluster; once
it is green and reviewed, the branch is merged, and the new version is installed for the users.


## 2. Git

### 2.1 What git is

Git records the history of a set of files. Each **commit** is a snapshot of all the files, with
an author, a date, a message, and a link to its parent commit(s). The history is therefore a
graph of commits. A commit is identified by a hash (`95a988a5fc...`, shortened to `95a988a`).

A **branch** is a movable name pointing to a commit: committing on a branch moves it forward.
`HEAD` is the commit you have checked out, usually through a branch. A **remote** (`origin`) is
another copy of the repository, e.g. on GitLab; `origin/dev` is your copy of the remote's
`dev` branch, as of your last `git fetch`.

Your clone has three areas:

```
 working tree  --git add-->  staging area (index)  --git commit-->  history (.git)
 (your files)                (the next commit)                     --git push--> remote
```

### 2.2 The everyday commands

| Command | What it does |
|---|---|
| `git clone <url>` | copies a repository, with its whole history |
| `git status` | what changed, what is staged, which branch you are on |
| `git diff` / `git diff --cached` | the changes not staged / staged |
| `git add <file>` | stages a change for the next commit |
| `git commit` | records the staged changes (an editor opens for the message) |
| `git log --oneline --graph` | the history, one line per commit |
| `git switch <branch>` / `git switch -c <new>` | moves to a branch / creates one from here |
| `git fetch` | downloads the remote's new commits, without touching your branches |
| `git pull` | `fetch`, then merges the remote branch into yours |
| `git push -u origin <branch>` | sends your branch to the remote (`-u` the first time) |
| `git merge <branch>` | joins another branch's history into yours |
| `git stash` / `git stash pop` | puts uncommitted changes aside / brings them back |
| `git restore <file>` | discards the uncommitted changes of a file (careful: lost) |

### 2.3 Branches and merges in our projects

- **One topic per branch**, with an explicit name: `fix/keymapper-key-zero`,
  `thermal/wall-conduction`, `doc/user-manual`. A branch starts from the current tip of the
  integration branch (e.g. `dev/official` in numbat).
- **Merges are merge commits**, with a title saying what the branch brings:
  `git merge --no-ff fix/keymapper-key-zero -m "Merge fix/keymapper-key-zero: no key below 1
  reaches maia's KeyMapper"`. `--no-ff` keeps the branch visible in the history even when a
  fast-forward was possible.
- **Never rewrite published history**: no `git rebase`, `git commit --amend` or
  `git push --force` on a branch that was pushed. Others may have built on it; rewriting it
  breaks their clones. To bring in new commits of the integration branch, merge it into yours.
- **Validate before pushing**: build, run the tests and the linters locally (part 11). The CI
  checks again, but a red CI costs everyone time.

### 2.4 A good commit

One commit, one logical change, that builds and passes the tests. Its message has a title line
(what it does, under ~70 characters), a blank line, then the why: what was wrong, how it showed,
what changed, how it was checked. A real example:

```
KeyMapper: no key below 1 reaches maia (grid lines crashed in PDM_gnum_locate)

maia's KeyMapper locates the keys with ParaDiGM's gnum location, which
takes the rank of a key from |key| - 1: a key 0 writes before its arrays
(a segmentation fault on Juno). The grid lines linked the volume entities
that are no foot by key 0, hence the crash on the official CI.
...
```

### 2.5 Pitfalls

- **Committing on the wrong branch**: check `git status` (first line) before committing. If it
  happened and nothing was pushed: `git switch -c <right-branch>` keeps the commit on a new
  branch.
- **Huge commits mixing topics**: hard to review and impossible to revert separately.
- **Generated files in git** (build directories, `__pycache__`, `.so`): they belong in
  `.gitignore`.
- **`git pull` with uncommitted changes**: commit or stash them first.
- **Secrets** (passwords, tokens) never go in a commit: the history keeps them forever.


## 3. Git submodules

### 3.1 What a submodule is

A submodule is a git repository placed inside another one, at a fixed path (e.g.
`external/pomac` inside numbat). The outer repository (the *superproject*) does not store the
submodule's files: it stores **one commit hash per submodule** (a *gitlink*). That hash is the
exact version of the dependency this version of the project works with.

The list of submodules, their paths and URLs, is in the file `.gitmodules`:

```ini
[submodule "external/pomac"]
	path = external/pomac
	url = https://github.com/gbegou/pomac.git
[submodule "external/maia"]
	path = external/maia
	url = git@gitlab.onera.net:numerics/mesh/maia.git
	branch = dev
```

`branch =` is only the branch that `git submodule update --remote` follows; a normal update
checks out the **recorded commit**, not the tip of that branch.

Why submodules rather than installed packages? Our libraries change together: a numbat change
often needs a pomac change. With submodules, a commit of numbat names the exact commit of pomac
it was tested with ("numbat at 00f6c4d works with pomac at 3891f70"), with no version numbers
to manage. This is the philosophy of project_utils (part 5): versions are commits.

### 3.2 The commands

| Command | What it does |
|---|---|
| `git clone <url>` then `git submodule update --init` | gets the project, then downloads every submodule at its recorded commit |
| `git submodule update --init external/pomac` | the same, for one submodule |
| `git submodule update --init --recursive` | also the submodules of the submodules |
| `git submodule status` | the recorded commit of each, with a marker (below) |
| `git submodule sync` | updates the local URLs after `.gitmodules` changed |
| `git diff --submodule` | shows a submodule change as a list of its commits |

`git submodule status` markers:

| Marker | Meaning |
|---|---|
| (space) | checked out at the recorded commit: all good |
| `-` | not initialized: the folder is empty (run `git submodule update --init <path>`) |
| `+` | checked out at another commit than the recorded one (after a `git pull` that moved it: run `git submodule update`) |
| `U` | merge conflict on the submodule's commit |

**After every `git pull`, update the submodules**: the pull may have moved their recorded
commits. Your checkouts stay where they were until you run `git submodule update` (or the
project's `tools/init_submodules.sh`).

### 3.3 Optional submodules

Some submodules are optional (`extensions/clovis-newton` in CLOVIS), or reserved to people
with access to them. `git clone --recurse-submodules` downloads every submodule and fails on
the first one you cannot access. A script with an explicit list of required and optional
submodules avoids this (CLOVIS's `tools/init_submodules.sh`):

```bash
tools/init_submodules.sh                        # the required submodules
tools/init_submodules.sh --with clovis-newton   # plus an optional one
tools/init_submodules.sh --list                 # what is required, what is optional
```

### 3.4 Updating a submodule to a newer commit

The superproject records a new commit for the submodule like any other change: `git add` the
submodule's path, then commit. The tool `git pin-submodule` (dev-tools, `tools/`) does the
whole thing, and says what it does:

```bash
git pin-submodule external/pomac                   # the tip of its recorded branch
git pin-submodule external/pomac -b dev/official   # switch to another branch, pin its tip
git pin-submodule external/eigen -b 5.0 -t 5.0.1   # a release tag
git diff --cached                                  # review
git commit -m "pomac: dev/official (3891f70), which holds thermo/wall-conduction"
```

By hand, the same is:

```bash
cd external/pomac && git fetch origin && git checkout <commit> && cd ../..
git add external/pomac && git commit
```

### 3.5 Working inside a submodule

A submodule is checked out in **detached HEAD** (on a commit, not on a branch). To change its
code:

1. `cd external/pomac`, `git switch -c my/topic` (a branch, so the commits are not lost);
2. commit, and **push the submodule's branch first**;
3. back in the superproject, `git add external/pomac` and commit: it records the new commit.

If you push the superproject before the submodule, the recorded commit exists only on your
machine, and every other clone and the CI fail to fetch it.

### 3.6 Renaming, adding, removing

- **Add**: `git submodule add -b <branch> <url> <path>`, or `git pin-submodule <path> -u <url>
  -b <branch>`.
- **Remove**: `git rm <path>` (removes the gitlink and the `.gitmodules` entry), then
  `rm -rf .git/modules/<path>`.
- **Rename** (e.g. `external/MARCeL` to `external/marcel`):
  `git mv external/MARCeL external/marcel`, then rename the section of `.gitmodules`:
  `git config -f .gitmodules --rename-section submodule.external/MARCeL submodule.external/marcel`.
  Everything that names the path changes too: here `CMakeLists.txt`
  (`project_add_dependency(marcel)`, which looks for the folder by name, part 5) and the CI
  scripts that initialize the submodule. Existing clones then run `git submodule sync` and
  `git submodule update --init external/marcel`.

### 3.7 Pitfalls

- **`git pull` inside a submodule**: it refuses on a detached HEAD; on a branch, it may create a
  merge commit that exists only on your machine. Update with `git pin-submodule` (or fetch and
  check out a commit), never with `git pull`.
- **Forgetting `git submodule update` after a pull**: you build with old dependencies; the
  errors look unrelated (a missing function in pomac, say).
- **Committing a submodule by accident**: `git add -A` stages a submodule that you moved while
  testing. Check `git diff --cached` before committing.
- **An empty `external/...` folder**: the submodule was never initialized. CMake then stops
  (project_utils: `Could not find folder for dependency`).


## 4. CMake

### 4.1 What CMake is

CMake does not compile anything itself. It reads the `CMakeLists.txt` files of a project,
finds the compilers and the dependencies, and **generates** the instructions of the build for
a build tool (Make or Ninja). That build tool then calls the compiler.

CMake works with three folders, kept apart:

| Tree | What it is | Made by |
|---|---|---|
| source tree | the clone: `CMakeLists.txt`, the code | git |
| build tree | the compiled objects, the libraries, the test programs, `CMakeCache.txt`, `source.sh` | `cmake -S . -B build` then `cmake --build build` |
| install tree | the final, self-contained copy, at `CMAKE_INSTALL_PREFIX` | `cmake --install build` |

Building in a separate folder (*out-of-source build*) keeps the sources clean: delete `build/`
and everything generated is gone. Several build folders can coexist (`build`, `build-debug`).

### 4.2 The four steps

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$clovis_INSTALL_ROOT  # 1 configure
cmake --build build -j 8                                                                   # 2 build
ctest --test-dir build --output-on-failure -j 8                                            # 3 test
cmake --install build                                                                      # 4 install
```

1. **Configure** (`cmake -S <source> -B <build> -D...`): checks the compilers, finds the
   dependencies, evaluates the `CMakeLists.txt` and writes the build instructions. Run once per
   build folder, and again to change an option.
2. **Build** (`cmake --build <build> -j N`): compiles what changed since the last build, `N`
   files at a time. Run after every change of the code.
3. **Test** (`ctest --test-dir <build>`): runs the tests the `CMakeLists.txt` registered.
   There is no `cmake --test`: CTest is CMake's test runner. `cd build && ctest` is the same.
4. **Install** (`cmake --install <build>`): copies the libraries, programs and Python packages
   to `CMAKE_INSTALL_PREFIX`. Run when a version is validated: users get it then.

### 4.3 Options and the cache

`-D<NAME>=<value>` sets a variable at configure time. CMake stores them in
`build/CMakeCache.txt`, so the next configures of that folder reuse them. The usual ones:

| Option | Meaning |
|---|---|
| `CMAKE_BUILD_TYPE` | `Release` (optimized), `Debug` (no optimization, debug information: for a debugger), `RelWithDebInfo` (both) |
| `CMAKE_INSTALL_PREFIX` | where `cmake --install` copies the result |
| `CMAKE_CXX_COMPILER` | the C++ compiler, when not the default one |
| `<project>_ENABLE_TESTS` | builds and registers the tests (`numbat_ENABLE_TESTS=ON`) |
| `<project>_ENABLE_DOCUMENTATION` | the documentation target |
| `<project>_ENABLE_WARNINGS_AS_ERRORS` | a compiler warning stops the build (the CI uses it) |

`cmake -LH build` lists the options of a build folder with their help; `ccmake build` edits
them in a terminal interface. A project's options are declared in its `CMakeLists.txt` with
`option(numbat_ENABLE_TESTS "Build the tests" OFF)`.

### 4.4 Reading a CMakeLists.txt

CMake is organized around **targets**: a library, a program, a Python module. Each target has
its sources, its include folders, its compile options and the targets it links to:

```cmake
cmake_minimum_required(VERSION 3.25)
project(numbat VERSION 0.0.3 LANGUAGES CXX)

add_library(numbat SHARED ${src_files})                # the C++ library libnumbat.so
target_include_directories(numbat PUBLIC ${PROJECT_SOURCE_DIR})
target_compile_features(numbat PUBLIC cxx_std_20)      # C++20
target_link_libraries(numbat
  PUBLIC  pomac::pomac std_e::std_e                    # numbat's users need them too
  PRIVATE some_internal_helper)                        # only numbat's own sources need it
```

- `PUBLIC`: the dependency is part of the target's interface: whoever links to `numbat` also
  gets `pomac`'s include folders and library. `PRIVATE`: used inside the target only.
  `INTERFACE`: for the users only (header-only libraries).
- `pomac::pomac`: a *namespaced* target, the convention for a target that another project
  exports. CMake checks that it exists (a typo is an error, not a silent missing library).
- `add_subdirectory(test)`: evaluates `test/CMakeLists.txt` too.
- `message(STATUS "...")`, `message(WARNING ...)`, `message(FATAL_ERROR ...)`: printed at
  configure time; `FATAL_ERROR` stops it.

### 4.5 Dependencies: three ways

| Way | How | When |
|---|---|---|
| `find_package(MPI REQUIRED)` | finds something already installed (the cluster's MPI, Python, numpy) | system libraries, cluster modules |
| `add_subdirectory(external/pomac)` | builds the dependency's sources with the project | our submodules (project_utils' `project_add_dependency`, part 5) |
| `FetchContent` | downloads the sources at configure time | small tools when there is no submodule (doctest; pybind11 when not a submodule) |

Our projects build their submodules with them (second way): one configure, one build, the same
compiler and flags for everything, and a change in pomac is rebuilt when you rebuild numbat.

### 4.6 Tests with CTest

`add_test(NAME <name> COMMAND <command>)` registers a test; `ctest` runs them and reports which
fail (a non-zero exit code is a failure). project_utils registers ours (part 5): the C++ tests
(doctest) as `numbat_doctest_unit_tests`, the Python tests (pytest) as
`numbat_pytest_unit_tests`, `numbat_pytest_func_tests`.

| `ctest` option | What it does |
|---|---|
| `--output-on-failure` | prints the output of the failing tests |
| `-j 8` | runs 8 tests at once |
| `-R <regex>` / `-E <regex>` | only the tests whose name matches / does not match |
| `-N` | lists the tests without running them |
| `--rerun-failed` | runs again only those that failed last time |
| `-V` | prints everything |

A test of a Python project needs an environment (the build tree on `PYTHONPATH`): our tests
take it from the shell, so source `build/source.sh` before running `ctest` (part 5). A C++ test
program can also be run by hand, with its own options: `build/test/numbat_doctest_unit_tests
-tc="*interpolation*"` runs only the doctest cases whose name matches.

### 4.7 Install

`install(TARGETS numbat LIBRARY DESTINATION lib)` and `install(FILES ...)` tell what
`cmake --install` copies, below `CMAKE_INSTALL_PREFIX`:

```
<prefix>/lib/libnumbat.so, libpomac.so...           the C++ libraries
<prefix>/lib/python3.12/site-packages/numbat/       the Python package
<prefix>/lib/python3.12/site-packages/cnumbat...so  its compiled module
<prefix>/bin/                                       programs, scripts
```

The modulefile of the version (part 8) puts exactly these folders on the paths.

### 4.8 When to configure again, when to start over

- Changed the code: `cmake --build build` only.
- Added a source file: our `CMakeLists.txt` collect sources with `file(GLOB ...
  CONFIGURE_DEPENDS)`, so the build sees it; otherwise configure again.
- Changed an option: configure again with the new `-D`.
- New submodule commits, other modules loaded, strange errors: `rm -rf build`, then configure
  and build from scratch (`cmake --fresh` does the same with CMake 3.24 or later).

### 4.9 Pitfalls

- **Configuring without the environment**: the module not loaded, CMake finds the system's old
  compiler or another Python. Load the module before configuring, in the same terminal.
- **An empty `CMAKE_INSTALL_PREFIX`** (the variable it was set from was empty): the install
  goes to a wrong place. `echo` the variable before configuring.
- **Mixing two Pythons**: a compiled module built for Python 3.12 does not import in 3.11. The
  Python that configures is the one that must run the code.
- **Editing `CMakeCache.txt` by hand**: use `-D` or `ccmake` instead.


## 5. project_utils

### 5.1 What it is

project_utils (ONERA, `external/project_utils`, MPL-2.0) is a set of CMake functions and git
tools shared by the projects built from submodules: maia, std_e, cpp_cgns, pomac, MARCeL, numbat,
CLOVIS. Its documentation (`external/project_utils/doc/Git_workflow.md`) describes a
**git-based dependency management workflow**: small libraries, each in its own repository,
developed together, whose versions are commits ("libA at commit 5f25414f works with libB at
commit f16af47b") rather than version numbers.

It is itself a submodule: the top `CMakeLists.txt` starts by checking it is there, then includes
its files:

```cmake
set(sub_repo_path "${PROJECT_ROOT}/external/project_utils")
file(GLOB sub_repo_files ${sub_repo_path}/*)
list(LENGTH sub_repo_files sub_repo_nb_files)
if(sub_repo_nb_files EQUAL 0)
  message(FATAL_ERROR "${sub_repo_path} is empty.
    Maybe you forgot to initialize it with \"git submodule update --init\"")
endif()
set(PROJECT_UTILS_CMAKE_DIR ${PROJECT_ROOT}/external/project_utils/cmake)
include(${PROJECT_UTILS_CMAKE_DIR}/dependency_management.cmake)
```

### 5.2 Dependencies: `project_add_dependency`

```cmake
project_add_dependency(std_e REQUIRED)
project_add_dependency(cpp_cgns REQUIRED)
project_add_dependency(pomac REQUIRED)
project_add_dependency(maia REQUIRED)
```

`project_add_dependency(<name>)` looks for a folder named exactly `<name>` holding a git
repository: first `external/<name>`, then anywhere in the project. It then builds it with the
project (`add_subdirectory`), in `build/external/<name>`, and records it, so that `source.sh`
puts it on the paths. Its name is a folder name: `project_add_dependency(MARCeL)` does not find
`external/marcel` (part 3.6). A dependency that another one already added (std_e, which several
of them use) is not added twice.

`project_find_package(<name>)` is `find_package` for the dependencies found installed (Python,
MPI, mpi4py), recorded so that the CMake configuration file of the installed project
(`<project>Config.cmake`, written by `target_install`) lists them for the projects that use it.

### 5.3 Tests: `create_doctest` and `create_pytest`

```cmake
include(${PROJECT_UTILS_CMAKE_DIR}/doctest_pytest.cmake)
create_doctest(TESTED_TARGET numbat LABEL unit_tests
               SOURCES numbat_unit_tests.cpp ${test_files} N_PROC 4)
create_pytest(TESTED_FOLDER ${PROJECT_SOURCE_DIR}/numbat LABEL unit_tests N_PROC 4)
```

- `create_doctest` builds one program from the C++ test files (`*.test.cpp`, written with the
  doctest library) and registers it as the test `<target>_doctest_<label>`, run as
  `mpirun -np <N_PROC> <program>` (directly with `SERIAL_RUN true`).
- `create_pytest` registers `pytest <folder>` as the test `<project>_pytest_<label>`, run the
  same way. pytest takes its environment from the shell that runs `ctest`: source `source.sh`
  first (the build tree on `PYTHONPATH`, the pytest_parallel plugin for the MPI tests), as the
  CI does.

These names are what the CI selects with `ctest -R` (part 10): `numbat_doctest_*`,
`numbat_pytest_*`.

### 5.4 Python modules

```cmake
include(${PROJECT_UTILS_CMAKE_DIR}/python_wrapping.cmake)
compile_install_pybind_module(numbat)
install_python_modules(numbat)
```

- `compile_install_pybind_module(numbat)` compiles every `numbat/**/*.pybind.cpp` into **one**
  Python module, `cnumbat` (the `c` prefix: the compiled part, distinct from the pure Python
  package `numbat`), linked to the C++ library, and installs it.
- `install_python_modules(numbat)` installs the `.py` files of the package, keeping the folder
  layout, in `<prefix>/lib/python3.X/site-packages`.

### 5.5 `source.sh`: the environment of the build tree

The last call of the `CMakeLists.txt`:

```cmake
include(${PROJECT_UTILS_CMAKE_DIR}/write_build_env_file.cmake)
write_build_env_file()
```

writes `build/source.sh`. Sourcing it (`source build/source.sh`) puts the build tree on the
paths of the current terminal, so that the project runs without being installed:

```bash
export LD_LIBRARY_PATH=<build>/external/pomac:...:<build>:$LD_LIBRARY_PATH   # the compiled libraries
export PYTHONPATH=<src>/external/pomac:<build>/external/pomac:...:<build>:<src>:$PYTHONPATH
export PATH=<src>/external/.../bin:<src>/bin:$PATH
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTEST_PLUGINS=pytest_parallel.plugin
export NUMBAT_SOURCE_DIR=<src>
export NUMBAT_BINARY_DIR=<build>
export POMAC_SOURCE_DIR=<src>/external/pomac
...
```

The `.py` files come from the **sources** (a Python change is seen at once, without building)
and the compiled modules from the **build tree** (a C++ change needs `cmake --build`). It is
written last so that every dependency added before is in it.

### 5.6 Other helpers

| File | What it gives |
|---|---|
| `find_or_fetch.cmake` | `find_or_fetch_pybind11()`, `find_or_fetch_doctest()`: an installed one, else downloaded |
| `default_flags.cmake`, `additional_build_types.cmake` | compiler flags, extra build types (e.g. with sanitizers) |
| `check_python_module.cmake` | checks at configure time that a Python module imports |
| `CodeCoverage.cmake` | coverage reports (`<project>_ENABLE_COVERAGE`) |
| `git/` | scripts and a cheat sheet for submodules |


## 6. std_e

### 6.1 What it is

std_e ("standard extended", ONERA, `external/std_e`, MPL-2.0) is a C++ library of
general-purpose data structures and algorithms, used by maia, cpp_cgns and our projects. Its
folders give an idea of its content:

| Folder | Content |
|---|---|
| `logging/` | loggers, printers (stdout, stderr, file), timers |
| `multi_array/`, `multi_index/` | multi-dimensional arrays |
| `graph/` | graph algorithms |
| `interval/` | intervals and interval sequences (e.g. offsets) |
| `parallel/` | MPI helpers |
| `algorithm/`, `iterator/`, `utils/` | algorithms, iterators, `to_string`, enums... |
| `unit_test/` | helpers for doctest, MPI tests |

### 6.2 How our projects use it: logging

pomac and numbat log through std_e's logger pool. The loggers are registered by pomac and
routed to Python's `logging` module (by `numbat.logging` for numbat's), so that a C++ message
appears in the same place as the Python ones. numbat's wrapper (`numbat/utils/logging.hpp`):

```cpp
#include "std_e/logging/log.hpp"
#include "std_e/logging/time_logger.hpp"
#include "std_e/utils/to_string.hpp"

namespace numbat::logging {
  inline const std::string info_logger = "numbat";
  inline const std::string time_logger = "numbat.time";

  template <typename... Ts>
  void info(const Ts&... xs) {
    ensure_loggers();
    std_e::log(info_logger, std_e::to_string(xs..., std::string("\n")));
  }

  [[nodiscard]] inline auto timed(std::string msg) -> std_e::time_logger {
    ensure_loggers();
    return std_e::time_logger(time_logger, std::move(msg));
  }
}
```

Used as:

```cpp
numbat::logging::info("lines: ", n_points, " points");
{
  auto t = numbat::logging::timed("intersection");   // "intersection", then
  compute_intersection();                            // "intersection - done. [1.2 s]"
}
```

### 6.3 The rule

Before writing a helper (a logger, a string conversion, an array type), look in std_e: it is
already a dependency, tested, and used the same way by the other projects.


## 7. pybind11

### 7.1 What it is

pybind11 is a header-only C++ library that exposes C++ functions and classes to Python. The
user calls them like Python functions; the computation runs at C++ speed. It converts the
arguments and results (numbers, strings, `std::vector`, numpy arrays...) and turns C++
exceptions into Python ones.

### 7.2 A minimal module

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
namespace py = pybind11;

double norm(py::array_t<double> x) {                      // a numpy array, without copy
  double s = 0.0;
  for (py::ssize_t i = 0; i < x.size(); ++i) s += x.data()[i] * x.data()[i];
  return std::sqrt(s);
}

struct Wall {
  double thickness;
  double heat_flux(double dT) const { return 1.5 * dT / thickness; }
};

PYBIND11_MODULE(example, m) {                             // the module "example"
  m.doc() = "An example";
  m.def("norm", &norm, py::arg("x"), "Euclidean norm of x");
  py::class_<Wall>(m, "Wall")
    .def(py::init<double>(), py::arg("thickness"))
    .def_readonly("thickness", &Wall::thickness)
    .def("heat_flux", &Wall::heat_flux, py::arg("dT"));
}
```

```python
import numpy as np, example
example.norm(np.array([3.0, 4.0]))        # 5.0
example.Wall(0.01).heat_flux(dT=20.0)     # 3000.0
```

Exceptions: a C++ `std::invalid_argument` becomes a Python `ValueError`, `std::out_of_range`
an `IndexError`, any other `std::exception` a `RuntimeError`, with the C++ message.

### 7.3 How our projects are organized

- The bindings are in files `<package>/<topic>/<topic>.pybind.cpp`, next to the C++ they expose;
  each defines a function `register_<topic>_module(py::module_& parent)` that adds a submodule.
- One file holds the `PYBIND11_MODULE` and calls them (`numbat/cnumbat.pybind.cpp`):

  ```cpp
  PYBIND11_MODULE(cnumbat, m) {
    m.doc() = "Compiled part of numbat";
    cnumbat::register_interpolation_module(m);
    cnumbat::register_intersection_module(m);
    cnumbat::register_stream_module(m);
    cnumbat::register_algo_module(m);  // after stream: its functions take stream.CellMesh
  }
  ```

- project_utils compiles them all into the module `cnumbat` (part 5.4). The Python package
  `numbat` imports what it needs from `cnumbat` and gives it a Pythonic interface
  (docstrings, defaults, checks): users import `numbat`, never `cnumbat` directly.
- Large arrays cross the boundary as numpy arrays (`py::array_t<double>`), read in place, not
  copied element by element.

### 7.4 Versions and type stubs

- pybind11 is a **submodule** (`external/pybind11`, pinned), not the one installed in the Python
  environment: the result does not depend on the machine.
- **Type stubs**: a compiled module has no Python source, so type checkers (basedpyright) and
  editors cannot see its functions. `pybind11-stubgen` (also a pinned submodule) writes them as
  `.pyi` files (`stubs/cnumbat/*.pyi`), committed with the code. A test
  (`numbat_stubs_up_to_date`) fails when they no longer match the compiled module: after
  changing a binding, regenerate them (`cmake --build build --target numbat_stubs`) and commit
  them. The same stubs generator version gives the same stubs, hence the pin.

### 7.5 MPI and Python

A Python process that imports an MPI module (mpi4py, maia...) runs through `mpiexec -np 1`,
even for one process: on some cluster nodes (Omni-Path on juno), Open MPI cannot start a lone
process otherwise. The tests, the documentation build and the commands of the developer guides
follow this rule: `mpiexec -np 1 python my_script.py`.

### 7.6 Pitfalls

- **A binding changed, stubs not regenerated**: the stubs test fails in the CI.
- **The wrong Python**: a module compiled for one Python version does not import in another
  (`ImportError: ... undefined symbol` or `No module named cnumbat`).
- **A missing library at import** (`ImportError: libpomac.so: cannot open shared object
  file`): `LD_LIBRARY_PATH` lacks the build or install tree: `source build/source.sh` (or load
  the module).
- **Long C++ calls block Python's other threads**: for long computations, release the GIL
  (`py::call_guard<py::gil_scoped_release>()`), but then never touch Python objects inside.


## 8. Modulefiles

### 8.1 What `module` does

A cluster has many versions of compilers, MPI, Python... installed side by side, none active by
default. **Environment Modules** (the `module` command) makes some of them active in the current
terminal by changing environment variables, according to small scripts in the Tcl language:
**modulefiles**. Nothing is installed; only the environment changes, and only in that terminal.

| Variable | Used for | A module adds |
|---|---|---|
| `PATH` | the programs the shell finds | `bin/` folders |
| `LD_LIBRARY_PATH` | the compiled libraries found when a program starts | `lib/` folders |
| `PYTHONPATH` | the packages Python imports | `site-packages/` folders |

| Command | What it does |
|---|---|
| `module avail [name]` | lists the available modules |
| `module load <module>` | loads a module, and those it needs |
| `module list` | the loaded modules |
| `module unload <module>` | undoes a load |
| `module purge` | unloads everything |
| `module use <folder>` | adds a folder of modulefiles (`$MODULEPATH`) |
| `module show <module>` | what loading it would do |
| `module switch <a> <b>` | replaces a loaded module by another |

### 8.2 Our modulefiles

Each project has its modulefiles in `modulefiles/`, deployed (copied) to
`<root>/modulefiles` by `modulefiles/deploy.sh`. One module per architecture and version:

```
modulefiles/
├── deploy.sh
└── clovis/
    ├── .common         shared: install paths, run and build modes, the summary printed
    └── socle7/         an architecture: the cluster's socle 7 (juno and sator alike)
        ├── .common     the cluster modules to load, extra paths and variables
        ├── dev         a version (its name is the file's name)
        └── main
```

`module load clovis/socle7/dev` runs `dev`, which runs `socle7/.common`, which runs
`clovis/.common`. They pass information down through environment variables:

```tcl
# clovis/socle7/dev
setenv CURRENT_MODULE_VERSION [file tail $ModulesCurrentModulefile]      ;# "dev"
source [file dirname $ModulesCurrentModulefile]/.common

# clovis/socle7/.common
setenv CURRENT_MODULE_DEPENDS [join {
    socle-cfd/7.0-gnu850-ompi502
    cmake/3.29.3
    gmsh/4.15.1-gnu850
} "|"]
setenv CURRENT_MODULE_ARCH [file tail [file dirname [file normalize [info script]]]]  ;# "socle7"
source [file dirname [file normalize [info script]]]/../.common
```

The shared `.common` then loads the listed modules, computes the install folder
`<root>/<arch>/<version>`, exports it as `<project>_INSTALL_ROOT`, and, in **run mode**, puts
it on `PATH`, `LD_LIBRARY_PATH` and `PYTHONPATH`.

### 8.3 Run mode and build mode

| | Run mode (default) | Build mode (`LOAD_MODE=build module load ...`) |
|---|---|---|
| for | users, running the installed version | developers, building and testing |
| loads the cluster modules | yes | yes |
| sets `<project>_INSTALL_ROOT` | yes | yes (the `CMAKE_INSTALL_PREFIX` to build with) |
| puts the installed project on the paths | yes | **no**: `build/source.sh` puts the one being built instead |

Build mode prevents the classic mistake of testing the installed version instead of the one you
just built. `LOAD_MODE=build` is written in front of the command only, never exported in
`~/.bashrc` (every load would then be a build load).

### 8.4 One module, undone whole

The two `.common` files are run with Tcl's `source`, not loaded with `module load`, so that the
three files form **one** module. Loaded as modules of their own, Environment Modules 5 unloaded
the architecture's `.common` with the version, but kept the shared one, with its paths: after
`module unload`, the "unloaded" install was still on `PYTHONPATH`. With `source`, `module unload`
restores the environment exactly.

### 8.5 Changing a modulefile

1. Edit the files of your clone (never the deployed copy: the next deploy overwrites it).
2. Deploy to a test folder and try: `modulefiles/deploy.sh /tmp_user/<cluster>/<login>/test-mf`,
   `module use` it, `module show`, `module load`, check, `module unload`, check again.
3. Deploy for real, commit, push. The others get it with `git pull` and a deploy.

### 8.6 Pitfalls

- `Unable to locate a modulefile`: the folder is not on `$MODULEPATH` (`module use`), or the
  modulefiles are not deployed.
- A module loaded in a terminal does not exist in another: load it in each new terminal.
- `module purge` also unloads modules you loaded yourself for something else.


## 9. GitLab

### 9.1 What it is

GitLab (`gitlab.onera.net` at ONERA) hosts git repositories and everything around them:

| Concept | What it is |
|---|---|
| project | a repository, with its issues, merge requests, pipelines, wiki, pages |
| group | a folder of projects with shared members and permissions (`numerics/solver/...`) |
| members and roles | who may read (Reporter), push (Developer), configure (Maintainer) |
| protected branch | a branch only some roles may push to, or merge into (`main`, `dev`) |
| merge request (MR) | a request to merge a branch into another: the diff, the discussion, the review, the pipeline's result |
| issue | a bug report or a task |
| pipeline | the CI jobs run for a commit (part 10) |
| runner | the machine, or the cluster account, that runs the jobs |
| CI/CD variables | values given to the jobs (paths, tokens), set in the project's settings, never in the repository |
| pages | a static website built by the CI (e.g. the documentation) |

### 9.2 Merge requests

The usual way to bring a branch into the integration branch:

1. push the branch (`git push -u origin fix/my-topic`); GitLab prints a link to open a merge
   request;
2. describe what it changes and how it was checked; assign a reviewer;
3. the pipeline runs; the reviewer comments on lines; you answer with new commits (not with a
   rewritten history);
4. when it is approved and green, merge (a merge commit).

### 9.3 SSH keys

The clone URLs `git@gitlab.onera.net:...` use SSH. Create a key once (`ssh-keygen -t ed25519`),
add the public key (`~/.ssh/id_ed25519.pub`) to your GitLab user settings, *SSH Keys*; check with
`ssh -T git@gitlab.onera.net`. Submodules with SSH URLs need it too.

### 9.4 The official repository and its GitHub copy

Some projects have two repositories that share no git history: the **official** one on
`gitlab.onera.net` (which the cluster CI builds), and a **GitHub copy** where part of the
development happens. Files are copied between them, without history, by
`tools/sync_project.sh` (this repository), then committed on the official side:

```bash
sync_project.sh <name> to-official origin/<tip>           # dry run: what would change
sync_project.sh --apply <name> to-official origin/<tip>   # copy the files
git -C <name> add . && git -C <name> commit -m "..."      # commit on the official side
```

`doc/official_and_github.md` gives the whole workflow, including the submodules.


## 10. Continuous integration (GitLab CI)

### 10.1 What it is

At every push, GitLab reads `.gitlab-ci.yml` and runs a **pipeline**: jobs that build the
project and run its tests on a runner. A red pipeline means a change broke something; the
author fixes it before merging. The CI also catches what a local check cannot: the real
dependencies, another machine, a clean environment.

| Keyword | Meaning |
|---|---|
| `stages` | the ordered phases (`init`, `build`, `test`...); a stage starts when the previous one succeeded |
| job | a named entry with a `script` (shell commands) |
| `needs` | the jobs a job waits for (and whose artifacts it receives) |
| `artifacts` | files a job hands over (test reports, a `build.env` of variables) |
| `rules` | when a job (or the pipeline) runs |
| `allow_failure` | a failure that does not make the pipeline red (orange); `exit_codes` restricts it to some codes |
| `extends` | reuses a hidden template job (`.with_hpc_modules`) |
| `variables` | environment variables of the jobs |
| `tags` | which runner runs the job (`juno-shell`) |
| `include` | other YAML files of the configuration |

### 10.2 Our layout

The CI runs on the cluster itself (Jacamar runners: the jobs run under your own account on
juno), with the cluster modules; the template is in `templates/gitlab-ci/` of this repository.

```
.gitlab-ci.yml          stages: init, build, test, quality, doc, deploy; includes:
.gitlab/ci/workflow.yml   when to create pipelines (not for merge-request events: no duplicates)
.gitlab/ci/common.yml     variables, runner tag, the module template, the test template
.gitlab/ci/init.yml       job:init     clone, submodules, first configure
.gitlab/ci/build.yml      job:build    configure with all tests, compile once
.gitlab/ci/test.yml       job:test-*   one job per group of tests (ctest -R)
.gitlab/ci/quality.yml    job:stubs, job:lint: optional tools, allowed to fail (orange)
.gitlab/ci/doc.yml        job:doc      the documentation, in its own build folder; pages
```

The rules behind it, and why:

- **`GIT_STRATEGY: none` and a manual clone** in `job:init`, into a workspace on the cluster's
  scratch filesystem (`/tmp_user/juno/<user>/.jacamar-ci/builds/<project>/<pipeline>`), never in
  the home directory: builds, Python imports and coverage write many small files, which the home
  filesystem serves 10 to 450 times slower (measured on numbat). The paths are passed to the
  next jobs in a `dotenv` artifact (`build.env`).
- **Every job loads the same modules** (`extends: .with_hpc_modules`): the environment comes
  from the modules, not from a virtual environment, so the CI tests what users run.
- **Configure and compile once** (`job:build`, `Debug`, all tests, warnings as errors). The test
  jobs never configure again: they run in parallel in the same build folder, and a new configure
  would rewrite it under their feet.
- **One test job per group of tests**, selected by name: `ctest -R "^numbat_pytest.*"`
  (`CTEST_LABEL: "numbat_pytest"`), with `--no-tests=error` (a job whose pattern selects nothing
  fails: a renamed test is noticed). A red job names the failing group.
- **Red means a real failure**: the tests are in `test`, and fail red. Checks that depend on
  optional tools (the stubs, ruff and basedpyright) are in `quality`, and exit with code 3 (tool
  missing) or 4 (lint findings): allowed failures, orange. The `test` stage reads green or red
  at a glance.
- **The documentation** has its own build folder (enabling it reconfigures), and is deployed to
  GitLab pages from the main development branch.

### 10.3 When the CI fails

1. Open the failed job: its log shows the commands and their output. Look for the first error,
   not the last line.
2. Reproduce on the cluster with the same modules: load them as `.with_hpc_modules` does,
   configure as `job:build` does, run the same `ctest -R`.
3. Fix, check locally, push: a new pipeline runs.

A real case: after a merge, numbat's CI crashed with a *segmentation fault* in
`PDM_gnum_locate`, inside maia's `KeyMapper`, called by the grid lines. Locally the tests
passed, because the local environment used a simplified stand-in for that maia function. The
crash came from a key 0 ("no link") that ParaDiGM indexes as `0 - 1`: a write before the start
of an array. The fix kept keys below 1 away from maia; the local stand-in was changed to call
ParaDiGM like the real one, and reproduced the crash before the fix. Lesson: the CI, with the
real dependencies, catches what local substitutes hide; when the two disagree, make the local
check closer to the real one.

### 10.4 Before pushing a change to the CI files

YAML has traps: an unquoted `: ` inside a script line turns it into a mapping, and the job
fails before running anything. `tools/check_ci.py` (this repository) reads the CI files and
fails on these, and on `needs`/`extends` that do not resolve:

```bash
python tools/check_ci.py           # in the project's root
```


## 11. Putting it all together

### 11.1 First day: from nothing to an installed project

```bash
# 1. the sources (git, submodules)
git clone git@gitlab.onera.net:numerics/solver/clovis.git && cd clovis
tools/init_submodules.sh

# 2. the modulefiles (once), and the build environment (each terminal)
modulefiles/deploy.sh
module use <root>/modulefiles
LOAD_MODE=build module load clovis/socle7/dev

# 3. configure, build (CMake; project_utils builds the submodules and writes source.sh)
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$clovis_INSTALL_ROOT \
      -Dclovis_ENABLE_TESTS=ON
cmake --build build -j 8

# 4. use and test the build tree
source build/source.sh
python -c "import clovis; print(clovis.__file__)"      # from the clone or build/
ctest --test-dir build --output-on-failure -j 8

# 5. install: users get it with "module load clovis/socle7/dev"
cmake --install build
```

### 11.2 A C++ function made available in Python

An example: a new C++ function `wall_flux`, in a `thermal` part of numbat.

1. A branch: `git switch -c feature/wall-flux`.
2. The C++: `numbat/thermal/flux.hpp` and `.cpp`, with its doctest tests in `flux.test.cpp`
   (next to the source: `create_doctest` collects `*.test.cpp`).
3. The binding: in `numbat/thermal/thermal.pybind.cpp`, `m.def("wall_flux", ...)` in the
   `register_thermal_module` function; `cnumbat.pybind.cpp` calls it.
4. The Python interface: `numbat/thermal/flux.py` imports `cnumbat.thermal.wall_flux`, checks
   the arguments, documents it; its pytest tests in `numbat/thermal/test/test_flux.py`.
5. Build and test: `cmake --build build -j 8`, then `ctest --test-dir build -R numbat_doctest`
   and `-R numbat_pytest`.
6. The stubs: `cmake --build build --target numbat_stubs`, then `git add stubs/`.
7. Lint and types: `ruff check`, `ruff format`, `basedpyright`.
8. Commit (`git add`, `git commit` with a message saying what and why), push
   (`git push -u origin feature/wall-flux`), open a merge request.
9. The CI builds and tests on juno; the reviewer comments; you fix with new commits.
10. Merged and green: install it (`cmake --install build`) for the users.

### 11.3 Using a newer version of a dependency

pomac gained a function that numbat needs:

```bash
git switch -c build/pomac-latest
git pin-submodule external/pomac -b dev/official    # pin the tip of pomac's dev/official
git diff --cached                                    # the new commit of external/pomac
cmake --build build -j 8                             # pomac is rebuilt with numbat
ctest --test-dir build --output-on-failure -j 8
git commit -m "pomac: dev/official (3891f70), which holds thermo/wall-conduction"
git push -u origin build/pomac-latest
```

The others get it with `git pull`, then `git submodule update` (or `tools/init_submodules.sh`).


## 12. Glossary

| Term | Meaning |
|---|---|
| artifact | a file or variable a CI job hands over to later jobs |
| build tree | the folder where CMake compiles (`build/`) |
| `CMakeCache.txt` | the options of a build folder |
| commit | a snapshot of the files in git, identified by a hash |
| configure | CMake's first step: checks the environment, writes the build instructions |
| detached HEAD | a checkout on a commit rather than a branch (normal in submodules) |
| doctest | the C++ test library of our projects (`*.test.cpp`) |
| gitlink | the commit of a submodule, as recorded by the superproject |
| install tree | the final copy of a project, at `CMAKE_INSTALL_PREFIX` |
| Jacamar | the runners that run GitLab CI jobs under your account on the cluster |
| merge request | GitLab's request to merge a branch, with review and pipeline |
| modulefile | a Tcl script that `module load` runs to set up an environment |
| pipeline | the CI jobs run for a commit |
| pybind11 | the library that exposes C++ to Python |
| project_utils | ONERA's CMake helpers for projects built from submodules |
| pytest | the Python test runner (`test/test_*.py`) |
| run mode / build mode | the two ways our modules load a project: installed / for building |
| socle | the cluster's software stack (compilers, MPI, Python) as modules |
| `source.sh` | the environment of the build tree, written by project_utils |
| std_e | ONERA's C++ library of utilities (logging, arrays, graphs) |
| stubs | `.pyi` files describing a compiled module for type checkers |
| submodule | a git repository inside another, pinned to a commit |
| superproject | the repository that holds submodules |
| target | something CMake builds: a library, a program, a Python module |


## 13. References

- Git: *Pro Git*, https://git-scm.com/book/en/v2 (chapter *Git Tools - Submodules* for
  submodules).
- CMake: the reference documentation, https://cmake.org/cmake/help/latest/, and its tutorial,
  https://cmake.org/cmake/help/latest/guide/tutorial/index.html.
- CTest: https://cmake.org/cmake/help/latest/manual/ctest.1.html.
- pybind11: https://pybind11.readthedocs.io/.
- Environment Modules: https://modules.readthedocs.io/.
- GitLab CI/CD: https://docs.gitlab.com/ci/.
- Jacamar CI: https://gitlab.com/ecp-ci/jacamar-ci.
- project_utils: `external/project_utils/doc/Git_workflow.md` and the comments of its
  `cmake/*.cmake` files.
- std_e: `external/std_e/README.md`.
- This repository: `CLAUDE.md` (the rules of the projects), `doc/official_and_github.md`,
  `templates/gitlab-ci/`, `tools/`.
