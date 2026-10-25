@echo off
rem Install everything (FFmpeg, Python 3.12, packages, Remotion and HyperFrames skills) without starting the app.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\bootstrap.ps1" -SetupOnly
pause
