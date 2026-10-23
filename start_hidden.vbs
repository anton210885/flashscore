' Startet Flashscore (API + UI + Live-Pipeline) ohne Fenster und oeffnet den Browser.
' Argument /nobrowser: Browser nicht oeffnen (fuer den Autostart).
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

extra = ""
If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "/nobrowser" Then extra = " -NoBrowser"
End If

CreateObject("WScript.Shell").Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & root & "\start_hidden.ps1""" & extra, 0, False
