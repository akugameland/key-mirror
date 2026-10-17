@echo off
cd /d "%~dp0"
rem Ilk acilista ya da kurulum yarim kaldiysa kurulumu yapar / Runs the setup first if needed
if not exist ".venv\kurulum_tamam" (
  call KURULUM.bat
  if not exist ".venv\kurulum_tamam" exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" tus_yansit.py
