@echo off
rem Stop Litchi Head services started by start.bat.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" -Stop
pause
