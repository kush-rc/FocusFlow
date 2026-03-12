@echo off
REM FocusFlow Build & Run Script for Windows
REM This script compiles the C++ module and launches the Streamlit app

echo 🎯 FocusFlow - Building and Running...

REM Step 1: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Step 2: Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Step 3: Install Python dependencies
echo 📥 Installing Python dependencies...
pip install -r requirements.txt

REM Step 4: Build C++ module
echo ⚡ Building C++ engagement module...
cd cpp_modules

REM Create build directory
if not exist "build" mkdir build
cd build

REM Get Pybind11 CMake directory
FOR /F "tokens=*" %%g IN ('python -c "import pybind11; print(pybind11.get_cmake_dir())"') do (SET PYBIND11_DIR=%%g)

REM Run CMake and build
cmake .. -Dpybind11_DIR="%PYBIND11_DIR%"
cmake --build . --config Release

REM Copy the compiled module to parent directory
copy /Y engagement_cpp*.pyd ..\..\  2>nul || echo ⚠️  C++ module build may have failed

cd ..\..

REM Step 5: Launch FastAPI Web Server
echo 🚀 Launching FocusFlow Web Application...
REM Automatically kill anything squatting on port 8000 before starting
FOR /F "tokens=5" %%a in ('netstat -aon ^| find "8000" ^| find "LISTENING"') do taskkill /f /pid %%a 2>nul
uvicorn src.main:app --host 0.0.0.0 --port 8000
