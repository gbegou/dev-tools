# ------------------------------------------------------------------------------
# project_sphinx_documentation: the <project>_sphinx target, which builds the Sphinx manual
# ------------------------------------------------------------------------------
# Copy to <project>/cmake/sphinx_documentation.cmake (as numbat and dspod do), then in the top
# CMakeLists.txt:
#
#   if(${PROJECT_NAME}_ENABLE_DOCUMENTATION)
#     include(${PROJECT_SOURCE_DIR}/cmake/sphinx_documentation.cmake)
#     # Sphinx imports the project: build everything first (cmake --build build), then the
#     # documentation (cmake --build build --target <project>_sphinx)
#     project_sphinx_documentation(DEPENDS c${PROJECT_NAME}
#                                  MODULES sphinx sphinx_rtd_theme)
#   endif()
#
# Same as project_utils' build_sphinx_documentation, but
#   - runs Sphinx as `python -m sphinx` with the interpreter the project is configured with:
#     Sphinx, its theme and extensions are packages of that interpreter (a venv with the "doc"
#     dependency group of pyproject.toml), and a sphinx-build script found on the PATH may have
#     another interpreter in its shebang;
#   - checks at configuration that this interpreter imports MODULES (the packages conf.py
#     loads), and stops with a message naming the "doc" dependency group otherwise;
#   - runs through bash: `source` does not exist in /bin/sh on Debian/Ubuntu (dash);
#   - sources the source.sh that project_utils writes in the build directory, so that the
#     target works from a fresh shell (the CI doc job does not source it);
#   - runs Python through `${MPIEXEC_EXECUTABLE} ${MPIEXEC_NUMPROC_FLAG} 1` when
#     MPIEXEC_EXECUTABLE is set: importing a project that starts MPI (mpi4py, maia...) from a
#     lone process fails on some nodes (Open MPI on Omni-Path, juno: "Error obtaining unique
#     transport key from PMIX"); the project sets it (FindMPI, or find_program(mpirun mpiexec)
#     for an MPI-free C++), and the documentation test of test/CMakeLists.txt runs the same way;
#   - treats warnings as errors (-W --keep-going): a missing snippet marker, a broken
#     cross-reference or a figure script that fails;
#   - is not part of the default build (no ALL) and installs only if built (OPTIONAL).
function(project_sphinx_documentation)
  set(options)
  set(one_value_args)
  set(multi_value_args DEPENDS MODULES)
  cmake_parse_arguments(ARGS "${options}" "${one_value_args}" "${multi_value_args}" ${ARGN})

  set(modules sphinx ${ARGS_MODULES})
  list(REMOVE_DUPLICATES modules)
  list(JOIN modules ", " modules_import)
  execute_process(COMMAND ${Python_EXECUTABLE} -c "import ${modules_import}"
                  RESULT_VARIABLE sphinx_status OUTPUT_QUIET ERROR_QUIET)
  if(NOT sphinx_status EQUAL 0)
    list(JOIN modules ", " modules_text)
    message(FATAL_ERROR "The documentation needs ${modules_text} for ${Python_EXECUTABLE} "
                        "(the \"doc\" dependency group of pyproject.toml: pip install --group doc "
                        "in a venv, then configure with its python)")
  endif()

  set(sphinx_source ${PROJECT_SOURCE_DIR}/doc)
  set(sphinx_build ${PROJECT_BINARY_DIR}/doc/sphinx/html)
  set(sphinx_index_file ${sphinx_build}/index.html)
  set(launcher "")
  if(MPIEXEC_EXECUTABLE)
    # the rank not bound to a core (Open MPI 5 and 4 names): the figures use every core
    set(launcher "export PRTE_MCA_hwloc_default_binding_policy=none OMPI_MCA_hwloc_base_binding_policy=none && ${MPIEXEC_EXECUTABLE} ${MPIEXEC_NUMPROC_FLAG} 1 ")
  endif()

  file(GLOB_RECURSE doc_files CONFIGURE_DEPENDS ${sphinx_source}/*)
  add_custom_command(
    OUTPUT  ${sphinx_index_file}
    COMMAND bash -c "source ${PROJECT_BINARY_DIR}/source.sh && ${launcher}${Python_EXECUTABLE} -m sphinx -W --keep-going -b html ${sphinx_source} ${sphinx_build}"
    WORKING_DIRECTORY ${PROJECT_BINARY_DIR}
    DEPENDS ${doc_files} ${ARGS_DEPENDS}
    COMMENT "Generating the Sphinx documentation"
    VERBATIM
  )
  # no ALL: the documentation is not built by default
  add_custom_target(${PROJECT_NAME}_sphinx DEPENDS ${sphinx_index_file})
  # OPTIONAL: the project installs even when the documentation is not built
  install(DIRECTORY ${sphinx_build}
          DESTINATION ${CMAKE_INSTALL_PREFIX}/share/doc/${PROJECT_NAME}
          OPTIONAL)
endfunction()
