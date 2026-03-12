"""
FocusFlow C++ Module Build Configuration

This setup.py compiles the C++ engagement calculator module
and makes it importable from Python.

Usage:
    pip install -e .
    OR
    python setup.py build_ext --inplace
"""

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import sys
import pybind11

# Get pybind11 include path
pybind11_include = pybind11.get_include()

# Define the C++ extension module
ext_modules = [
    Extension(
        "engagement_cpp",  # Module name (what you'll import in Python)
        sources=["cpp_modules/engagement.cpp"],  # Source file
        include_dirs=[
            pybind11_include,  # pybind11 headers
        ],
        language="c++",
        extra_compile_args=[
            "-std=c++11",  # Use C++11 standard
        ] if sys.platform != "win32" else [
            "/std:c++14",  # MSVC flag for Windows
        ],
    ),
]

# Setup configuration
setup(
    name="focusflow-cpp",
    version="0.1.0",
    author="Your Name",
    description="FocusFlow C++ Engagement Calculator",
    ext_modules=ext_modules,
    install_requires=[
        "pybind11>=2.11.1",
    ],
    python_requires=">=3.8",
    zip_safe=False,
)
