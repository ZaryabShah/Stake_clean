@echo off
REM Stake.com Game Thumbnail Scraper - Windows Batch Runner
REM This batch file makes it easy to run the scraper on Windows

echo.
echo ========================================
echo  Stake.com Game Thumbnail Scraper
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://python.org
    pause
    exit /b 1
)

REM Check if Node.js is available
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

echo Python and Node.js found!
echo.

REM Run setup test first
echo Running setup test...
python test_setup.py
if errorlevel 1 (
    echo.
    echo Setup test failed. Please fix the issues above.
    pause
    exit /b 1
)

echo.
echo Setup test passed!
echo.

REM Ask user what to do
echo What would you like to do?
echo.
echo 1. Run complete scraper (recommended)
echo 2. Run with clean start (removes existing data)
echo 3. Test setup only (already done)
echo 4. Show help
echo.

set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo.
    echo Running complete scraper...
    python main.py
) else if "%choice%"=="2" (
    echo.
    echo Running with clean start...
    python main.py --clean
) else if "%choice%"=="3" (
    echo.
    echo Setup test already completed above.
) else if "%choice%"=="4" (
    echo.
    python main.py --help
) else (
    echo Invalid choice. Running complete scraper...
    python main.py
)

echo.
echo Scraper execution completed.
echo Check the 'stake_thumbnails_final' folder for downloaded images.
echo Check the 'logs' folder for detailed execution logs.
echo.
pause
