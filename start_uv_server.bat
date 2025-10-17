@echo off
setlocal

rem Change to the directory that contains this script
pushd "%~dp0"

rem Verify that uv is installed
where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Could not find the uv command. Install UV from https://docs.astral.sh/uv/ and try again.
    goto :end
)

echo [INFO] Launching FastAPI server...
start "" /B cmd /c "cd /d ""%~dp0"" && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"

rem Give the server a moment to start before opening the browser
timeout /t 3 /nobreak >nul

set "CHROME_URL=http://localhost:8000/"
echo [INFO] Opening Chrome at %CHROME_URL%

rem Try the chrome command on PATH first
where chrome >nul 2>&1
if %errorlevel%==0 (
    start "" chrome %CHROME_URL%
    goto :end
)

rem Fall back to common Chrome install locations
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" %CHROME_URL%
    goto :end
)

if not "%ProgramFiles(x86)%"=="" if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" %CHROME_URL%
    goto :end
)

echo [WARN] Chrome was not found. Please open %CHROME_URL% manually.

:end
echo.
echo Service is running in this window. Press any key here to stop it.
pause >nul
popd
