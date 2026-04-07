Option Explicit
Dim fso, sh, root, target
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
target = fso.BuildPath(root, "START_PNEUMO_APP.pyw")
If Not fso.FileExists(target) Then
  target = fso.BuildPath(root, "START_PNEUMO_APP.py")
End If
sh.Run Chr(34) & target & Chr(34), 0, False
