@echo off
setlocal enabledelayedexpansion

:: Get the directory where the batch file is located
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

:: Check if app is running and kill it if it is
if exist ".app_running" (
    for /f "tokens=*" %%a in (.app_running) do (
        taskkill /F /PID %%a 2>nul
    )
    del ".app_running"
    exit /b
)

:: Create and activate virtual environment if needed
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

:: Start Flask server and save PID
start /b "" ".venv\Scripts\python.exe" file_server.py
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo list ^| find "PID:"') do (
    echo %%a > .app_running
)

:: Start Streamlit app and save PID
start /b "" ".venv\Scripts\streamlit.exe" run app.py
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq streamlit.exe" /fo list ^| find "PID:"') do (
    echo %%a >> .app_running
)

:: Keep the window open to show any errors
pause 