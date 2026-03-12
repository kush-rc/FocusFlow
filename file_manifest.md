# FocusFlow File Manifest

This document explains the purpose and importance of each file in the FocusFlow project.

## Core Backend (`/src`)
- **`main.py`**: The heart of the application. It runs the FastAPI server, manages WebSocket connections for real-time video streaming, and coordinates between the vision engine and the database.
- **`vision_engine.py`**: Contains the AI logic. It uses MediaPipe to detect faces, track eyes, and estimate head pose. It routes complex math to the C++ module.
- **`database.py`**: Manages the SQLite database. It handles saving session data, tracking distractions, and retrieving history for the dashboard.

## High-Performance Layer (`/cpp_modules`)
- **`engagement.cpp`**: Custom C++ code that calculates engagement scores at high speed. It ensures the app stays fast even when processing 30 frames per second.
- **`engagement_cpp.pyd`**: The compiled version of the C++ code that Python can understand.

## Modern Frontend (`/frontend`)
- **`index.html`**: The main interface. It uses a clean, asymmetric layout designed for professional focus.
- **`style.css`**: Defines the "FocusFlow aesthetic"—glassmorphism effects, warm color palette, and premium typography.
- **`script.js`**: Controls the browser-side logic, including camera access, screen sharing, and the WebSocket data bridge.

## Configuration & Tools
- **`requirements.txt`**: Lists all Python libraries needed (FastAPI, OpenCV, MediaPipe, etc.).
- **`run.bat`**: The "One-Click" launcher for Windows users.
- **`build_cpp.bat`**: A utility to re-compile the C++ module if you make changes to the C++ source code.
- **`setup.py`**: The "bridge" script used by Python to compile the C++ code.
- **`.gitignore`**: Tells Git which files to ignore (like the virtual environment or temporary cache).

## Data & Logs
- **`data/focus_flow.db`**: The local database file where all your session history is stored securely.
