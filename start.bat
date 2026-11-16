@echo off
rem Litchi Head one-click launcher (Windows). Double-click to start.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 pause
