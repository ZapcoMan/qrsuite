@echo off
chcp 65001 >nul
title QRSuite v2
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

where python >nul 2>nul || (echo [ERROR] Python not found in PATH & pause & exit /b 1)

rem --- drag & drop a file / folder onto this bat ---
if not "%~1"=="" (
  python -m qrsuite %*
  echo.
  pause
  exit /b
)

:menu
cls
echo ============================================================
echo   QRSuite v2   Multi-Engine QR / Barcode Scanner
echo ============================================================
echo   1. Open Web UI        (browser drag ^& drop, local service)
echo   2. Interactive scan   (type image path or URL)
echo   3. Fast scan a folder (--mode fast, lowest CPU)
echo   4. Deep scan a folder (all variants + all engines)
echo   5. Download WeChatQRCode models (optional engine)
echo   6. Run benchmark      (v1-style pipeline vs v2)
echo   0. Exit
echo ============================================================
set /p c=Choose [0-6]: 
if "%c%"=="1" ( python -m qrsuite --serve & pause & goto menu )
if "%c%"=="2" ( python -m qrsuite & pause & goto menu )
if "%c%"=="3" ( set /p d=Folder path: & python -m qrsuite "%d%" --mode fast -v & pause & goto menu )
if "%c%"=="4" ( set /p d=Folder path: & python -m qrsuite "%d%" --mode deep -v & pause & goto menu )
if "%c%"=="5" ( python -m qrsuite --fetch-models & pause & goto menu )
if "%c%"=="6" ( set /p d=Folder path: & set /p v1=Path to old qrsuite.py (optional): & python tests\bench.py "%d%" "%v1%" & pause & goto menu )
if "%c%"=="0" exit /b
goto menu
