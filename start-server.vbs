Set shell = CreateObject("Wscript.Shell")
shell.CurrentDirectory = "C:\Users\tb\TraderDash"
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""C:\Users\tb\TraderDash\ensure-server.ps1""", 0, False
