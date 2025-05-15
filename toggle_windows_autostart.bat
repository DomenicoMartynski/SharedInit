@echo off
setlocal

:: Get the directory where the script is located
set "SCRIPT_DIR=%~dp0"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_FILE=%STARTUP_FOLDER%\SharedInit.lnk"

:: Check if the shortcut already exists
if exist "%SHORTCUT_FILE%" (
    :: Shortcut exists, so disable autostart by removing it
    del "%SHORTCUT_FILE%"
    echo Autostart has been disabled. The shortcut has been removed from the Windows Startup folder.
) else (
    :: Shortcut does not exist, so enable autostart by creating it
    cscript //nologo CreateShortcut.vbs "%SHORTCUT_FILE%" "%SCRIPT_DIR%SharedInit - Windows Launcher.bat" "%SCRIPT_DIR%"
    echo Autostart has been enabled. A shortcut has been created in the Windows Startup folder.
)

pause