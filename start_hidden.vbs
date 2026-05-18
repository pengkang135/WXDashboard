Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
PythonExe = ScriptDir & "\.venv\Scripts\pythonw.exe"
LauncherPy = ScriptDir & "\start_hidden.py"

If Not FSO.FileExists(PythonExe) Then
    MsgBox "未找到 Python 虚拟环境:" & vbCrLf & PythonExe & vbCrLf & vbCrLf & "请先运行: python -m venv .venv && .venv\Scripts\python -m pip install flask openpyxl", 48, "WXDashboard - 启动失败"
    WScript.Quit 1
End If

If Not FSO.FileExists(LauncherPy) Then
    MsgBox "未找到启动脚本:" & vbCrLf & LauncherPy, 48, "WXDashboard - 启动失败"
    WScript.Quit 1
End If

WshShell.CurrentDirectory = ScriptDir
WshShell.Run """" & PythonExe & """ """ & LauncherPy & """", 0, False
