cmake_minimum_required(VERSION 3.15...4.4)
project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

# Compile libnghttp2 into the extension so wheels do not need a system copy.
set(ENABLE_LIB_ONLY ON CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(BUILD_STATIC_LIBS ON CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(ENABLE_FAILMALLOC OFF CACHE BOOL "" FORCE)
add_subdirectory(vendor/nghttp2 EXCLUDE_FROM_ALL)
# Static objects must be position-independent when linked into a Python module.
set_property(TARGET nghttp2_static PROPERTY POSITION_INDEPENDENT_CODE ON)

find_package(
  Python
  COMPONENTS Interpreter Development.Module
  REQUIRED)
find_package(Cython MODULE REQUIRED VERSION 3.1)
include(UseCython)

option(NGH2_COVERAGE "Enable Cython line tracing for coverage" OFF)
if(NGH2_COVERAGE)
  set(_ngh2_cython_args --directive linetrace=True)
endif()

cython_transpile(
  src/${SKBUILD_PROJECT_NAME}/_core.pyx
  LANGUAGE C
  CYTHON_ARGS ${_ngh2_cython_args}
  OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/_core.c"
  OUTPUT_VARIABLE _core_c)
cython_transpile(
  src/${SKBUILD_PROJECT_NAME}/events.pyx
  LANGUAGE C
  CYTHON_ARGS ${_ngh2_cython_args}
  OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/events.c"
  OUTPUT_VARIABLE events_c)

python_add_library(_core MODULE "${_core_c}" WITH_SOABI)
python_add_library(events MODULE "${events_c}" WITH_SOABI)
target_link_libraries(_core PRIVATE nghttp2)
target_compile_definitions(_core PRIVATE NGHTTP2_NO_SSIZE_T)

if(NGH2_COVERAGE)
  target_compile_definitions(_core PRIVATE CYTHON_TRACE=1)
  target_compile_definitions(events PRIVATE CYTHON_TRACE=1)
endif()

install(TARGETS _core events DESTINATION ${SKBUILD_PROJECT_NAME})
