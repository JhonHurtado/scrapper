@echo off
rem run.bat — arranque para Windows (cmd o doble clic). Delega en run.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
