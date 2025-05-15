Set WshShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Check if app is running
Set fso = CreateObject("Scripting.FileSystemObject")
If fso.FileExists(strPath & "\.app_running") Then
    Set file = fso.OpenTextFile(strPath & "\.app_running", 1)
    Do Until file.AtEndOfStream
        pid = file.ReadLine
        WshShell.Run "taskkill /F /PID " & pid, 0, True
    Loop
    file.Close
    fso.DeleteFile strPath & "\.app_running"
    WScript.Quit
End If

' Create and activate virtual environment if needed
If Not fso.FolderExists(strPath & "\.venv") Then
    WshShell.Run "python -m venv .venv", 0, True
    WshShell.Run ".venv\Scripts\activate.bat && pip install -r requirements.txt", 0, True
End If

' Start Flask server
WshShell.Run ".venv\Scripts\python.exe " & strPath & "\file_server.py", 0, False
Set file = fso.CreateTextFile(strPath & "\.app_running", True)
file.WriteLine WshShell.Exec(".venv\Scripts\python.exe " & strPath & "\file_server.py").ProcessID

' Start Streamlit app
WshShell.Run ".venv\Scripts\streamlit.exe run " & strPath & "\app.py", 0, False
file.WriteLine WshShell.Exec(".venv\Scripts\streamlit.exe run " & strPath & "\app.py").ProcessID
file.Close 