Set shell = CreateObject("Wscript.Shell")
shell.CurrentDirectory = "C:\Users\tb\TraderDash"
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""C:\Users\tb\TraderDash\open-dashboard.ps1""", 0, False
