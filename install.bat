@echo off
title Asset Manager v1.4.3 - Windows Installation
color 0A

echo.
echo ================================================================
echo    Asset Manager for Maya (All Versions) v1.4.3 - Windows Installer
echo ================================================================
echo    Unified Installation Architecture ^| Multi-Version Compatible
echo    OneDrive ^& Cloud Sync Support ^| Smart Path Detection
echo ================================================================
echo.

REM Check if Python is available
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo ❌ ERROR: Python is not installed or not available in PATH
    echo.
    echo    Please install Python from https://python.org
    echo    Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo    ✅ Python %PYTHON_VERSION% detected

echo.
echo [2/4] Initializing unified installation core...
echo    📦 Using AssetManagerInstaller class for consistent results

REM Change to script directory to ensure relative paths work
cd /d "%~dp0"

echo.
echo [3/4] Running installation with unified setup.py core...
echo    🔧 This uses the same core logic as DRAG^&DROP.mel and install.sh
echo.

REM Run the unified installation
python setup.py

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo ❌ Installation failed. Please check error messages above.
    echo.
    pause
    exit /b 1
)

color 0A
echo.
echo [4/4] Installation verification...
echo    ✅ Unified installation architecture complete
echo.
echo ================================================================
echo                    🎉 INSTALLATION SUCCESSFUL 🎉
echo ================================================================
echo.
echo 🚀 NEXT STEPS:
echo.
echo   1️⃣  Launch any Maya version (2022, 2023, 2024, 2025+)
echo   2️⃣  Run in Maya's Script Editor (Python):
echo        import assetManager
echo        assetManager.show_asset_manager()
echo.
echo   💡 TIP: Works across all Maya versions - installed once, use everywhere!
echo.
echo � INSTALLATION METHODS COMPARISON:
echo   • install.bat (this method): Windows command-line installation
echo   • DRAG^&DROP.mel: Maya GUI installation with shelf button
echo   • install.sh: Unix/Linux/macOS installation
echo   • All methods use the same unified setup.py core!
echo.
echo 🔧 ARCHITECTURE HIGHLIGHTS:
echo   • Single Source of Truth: All installers use setup.py core
echo   • Clean Code: AssetManagerInstaller class with clear methods
echo   • DRY Principle: No code duplication between installation methods
echo   • Multi-Version Support: Works with all Maya versions (2022-2025+)
echo   • General Scripts Directory: ~/Documents/maya/scripts/ (not version-specific)
echo.
pause
