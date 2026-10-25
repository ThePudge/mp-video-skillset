@echo off
rem Rebuilds "MP Studio.exe" (repo root) from Launcher.cs with the C# compiler that ships with Windows.
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
"%CSC%" /nologo /target:winexe /optimize+ /win32icon:"%~dp0mp.ico" /out:"%~dp0..\..\..\MP Studio.exe" "%~dp0Launcher.cs"
