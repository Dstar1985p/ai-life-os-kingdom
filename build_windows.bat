@echo off
echo ============================================
echo   Kingdom ^— AI Life OS  ^|  Windows Builder
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11 from https://python.org
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: pip install failed. Check your internet connection.
    pause
    exit /b 1
)

echo [2/4] Installing PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo ERROR: PyInstaller install failed.
    pause
    exit /b 1
)

echo [3/4] Building Kingdom.exe ...
pyinstaller kingdom.spec --noconfirm --clean
if errorlevel 1 (
    echo ERROR: PyInstaller build failed. See output above.
    pause
    exit /b 1
)

echo [4/4] Done!
echo.
echo =====================================================
echo  Your app is ready at:  dist\Kingdom\Kingdom.exe
echo  Double-click Kingdom.exe to launch the Kingdom!
echo =====================================================
echo.
pause
