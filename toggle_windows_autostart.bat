@echo off
setlocal

:: Get the directory where the script is located
set "SCRIPT_DIR=%~dp0"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_FILE=%STARTUP_FOLDER%\SharedInit.lnk"

:: Create PowerShell script content
echo $ErrorActionPreference = 'Stop' > "%TEMP%\ToggleAutostart.ps1"
echo. >> "%TEMP%\ToggleAutostart.ps1"
echo $shortcutPath = "%SHORTCUT_FILE%" >> "%TEMP%\ToggleAutostart.ps1"
echo. >> "%TEMP%\ToggleAutostart.ps1"
echo if (Test-Path $shortcutPath) { >> "%TEMP%\ToggleAutostart.ps1"
echo     Remove-Item $shortcutPath -Force >> "%TEMP%\ToggleAutostart.ps1"
echo     Write-Host "Autostart has been disabled. The shortcut has been removed from the Windows Startup folder." >> "%TEMP%\ToggleAutostart.ps1"
echo } else { >> "%TEMP%\ToggleAutostart.ps1"
echo     $WshShell = New-Object -ComObject WScript.Shell >> "%TEMP%\ToggleAutostart.ps1"
echo     $Shortcut = $WshShell.CreateShortcut($shortcutPath) >> "%TEMP%\ToggleAutostart.ps1"
echo     $Shortcut.TargetPath = "wscript.exe" >> "%TEMP%\ToggleAutostart.ps1"
echo     $Shortcut.Arguments = """%SCRIPT_DIR%SharedInit - Windows Launcher.vbs""" >> "%TEMP%\ToggleAutostart.ps1"
echo     $Shortcut.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\ToggleAutostart.ps1"
echo     $Shortcut.Description = "SharedInit LAN File Sharing" >> "%TEMP%\ToggleAutostart.ps1"
echo     $Shortcut.WindowStyle = 7 >> "%TEMP%\ToggleAutostart.ps1"
echo     $Shortcut.Save() >> "%TEMP%\ToggleAutostart.ps1"
echo     Write-Host "Autostart has been enabled. A shortcut has been created in the Windows Startup folder." >> "%TEMP%\ToggleAutostart.ps1"
echo } >> "%TEMP%\ToggleAutostart.ps1"

:: Run PowerShell script
powershell -ExecutionPolicy Bypass -File "%TEMP%\ToggleAutostart.ps1"

:: Clean up
del "%TEMP%\ToggleAutostart.ps1"

pause