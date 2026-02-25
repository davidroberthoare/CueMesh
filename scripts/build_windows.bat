@echo off
REM Build CueMesh Controller for Windows x86_64
REM Usage: scripts\build_windows.bat

setlocal
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set DIST_DIR=%PROJECT_DIR%\dist

echo === CueMesh Windows x86_64 Build ===
echo Project: %PROJECT_DIR%

cd /d %PROJECT_DIR%

echo [1/3] Installing dependencies...
pip install pyinstaller PySide6 websockets zeroconf

echo [2/3] Building Controller...
pyinstaller --onedir --name CueMesh-Controller ^
  --add-data "shared;shared" ^
  --add-data "assets;assets" ^
  --distpath "%DIST_DIR%" ^
  controller/__main__.py

echo [3/3] Copying support files...
xcopy /E /I examples "%DIST_DIR%\CueMesh-Controller\examples"
xcopy /E /I docs "%DIST_DIR%\CueMesh-Controller\docs"
copy README.md "%DIST_DIR%\CueMesh-Controller\"

echo.
echo === Build complete ===
echo Controller: %DIST_DIR%\CueMesh-Controller\
endlocal
