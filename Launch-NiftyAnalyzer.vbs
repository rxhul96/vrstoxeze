' Nifty Analyzer 2.0 — silent desktop app launcher (signal-only).
' Used by the Desktop / Start Menu shortcut. No console window.
Option Explicit

Dim fso, sh, root, pyw, py, desk, install
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root

pyw = root & "\.venv\Scripts\pythonw.exe"
py = root & "\.venv\Scripts\python.exe"
desk = root & "\desktop.py"
install = root & "\install.ps1"

If Not fso.FileExists(pyw) And Not fso.FileExists(py) Then
  If fso.FileExists(install) Then
    sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & install & """", 1, True
  End If
End If

If fso.FileExists(pyw) Then
  sh.Run """" & pyw & """ """ & desk & """", 0, False
ElseIf fso.FileExists(py) Then
  sh.Run """" & py & """ """ & desk & """", 1, False
Else
  MsgBox "Nifty Analyzer could not start." & vbCrLf & vbCrLf _
    & "Install Python 3.12+ from python.org (check Add to PATH)," & vbCrLf _
    & "then double-click INSTALL.bat in:" & vbCrLf & root, _
    16, "Nifty Analyzer"
  WScript.Quit 1
End If
