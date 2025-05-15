@echo off
setlocal

:: Get the directory where the script is located
set "SCRIPT_DIR=%~dp0"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_FILE=%STARTUP_FOLDER%\SharedInit.lnk"

:: Run PowerShell commands directly
powershell -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference = 'Stop'; ^
    $shortcutPath = '%SHORTCUT_FILE%'; ^
    if (Test-Path $shortcutPath) { ^
        Remove-Item $shortcutPath -Force; ^
        Write-Host 'Autostart has been disabled. The shortcut has been removed from the Windows Startup folder.'; ^
    } else { ^
        $WshShell = New-Object -ComObject WScript.Shell; ^
        $Shortcut = $WshShell.CreateShortcut($shortcutPath); ^
        $Shortcut.TargetPath = 'wscript.exe'; ^
        $Shortcut.Arguments = '%SCRIPT_DIR%SharedInit - Windows Launcher.vbs'; ^
        $Shortcut.WorkingDirectory = '%SCRIPT_DIR%'; ^
        $Shortcut.Description = 'SharedInit LAN File Sharing'; ^
        $Shortcut.WindowStyle = 7; ^
        $Shortcut.Save(); ^
        Write-Host 'Autostart has been enabled. A shortcut has been created in the Windows Startup folder.'; ^
    }"

pause