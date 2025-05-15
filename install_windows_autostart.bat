@echo off
setlocal

:: Get the directory where the script is located
set "SCRIPT_DIR=%~dp0"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

:: Create the shortcut
echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%STARTUP_FOLDER%\SharedInit.lnk" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "wscript.exe" >> CreateShortcut.vbs
echo oLink.Arguments = """"%SCRIPT_DIR%launch_windows_background.vbs""" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> CreateShortcut.vbs
echo oLink.Description = "SharedInit LAN File Sharing" >> CreateShortcut.vbs
echo oLink.WindowStyle = 7 >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs

:: Run the VBS script
cscript //nologo CreateShortcut.vbs
del CreateShortcut.vbs

echo Autostart shortcut has been created in the Windows Startup folder.
pause 