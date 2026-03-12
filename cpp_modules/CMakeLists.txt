cmake_minimum_required(VERSION 3.15)
project(engagement_cpp)

# Set C++ Standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Python
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Find pybind11
find_package(pybind11 CONFIG REQUIRED)

# Create Python module
pybind11_add_module(engagement_cpp engagement.cpp)

# Installation
install(TARGETS engagement_cpp LIBRARY DESTINATION .)
