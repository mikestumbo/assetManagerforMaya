@echo off
echo Asset Manager for Maya 2025.3 v1.1.3 - Installation Script
echo =========================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python or add it to your PATH
    pause
    exit /b 1
)

echo Installing Asset Manager plugin...
echo.

REM Run the installation script
python setup.py

echo.
echo Installation complete!
echo.
echo Next steps:
echo 1. Open Maya 2025.3
echo 2. Go to Windows ^> Settings/Preferences ^> Plug-in Manager
echo 3. Find 'assetManager.py' and enable it
echo 4. The Asset Manager menu will appear in Maya's menu bar
echo.
pause
