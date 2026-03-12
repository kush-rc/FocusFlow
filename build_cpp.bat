@echo off
REM Build script for FocusFlow C++ module (Windows)

echo ========================================
echo Building FocusFlow C++ Module
echo ========================================

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install/upgrade build dependencies
echo.
echo Installing build dependencies...
pip install --upgrade pip setuptools wheel pybind11

REM Build the C++ extension in-place
echo.
echo Compiling C++ module...
python setup.py build_ext --inplace

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Build successful!
    echo ========================================
    echo.
    echo You can now import the module in Python:
    echo     import engagement_cpp
    echo     score = engagement_cpp.calculate_engagement_score(0.8, 0.7, 0.9)
) else (
    echo.
    echo ========================================
    echo Build failed! Check errors above.
    echo ========================================
    exit /b 1
)
