@echo off
rem Double-click to open the Video Editor. First run installs FFmpeg, Python 3.12 and packages.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\bootstrap.ps1"
if errorlevel 1 pause
