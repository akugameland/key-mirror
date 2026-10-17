@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Tus Yansit / Key Mirror - kurulum / setup
echo Ek paket gerekmez; yalnizca Python 3.12 kullanilir. / No extra packages; only Python 3.12 is used.
echo.
set "PY="
if exist ".venv\kurulum_tamam" del ".venv\kurulum_tamam"

echo [1/2] Python 3.12
if exist ".venv\Scripts\pythonw.exe" (
  ".venv\Scripts\python.exe" -c "import sys, tkinter; sys.exit(sys.version_info[:2] != (3, 12))" 2>nul && goto tamam
  echo [UYARI] Python ortami bozuk ya da farkli surum, yeniden kuruluyor
)
call :python_bul
if defined PY goto ortam

rem Python 3.12 yok: winget ile kullanici hesabina kur (yonetici izni gerekmez)
rem No Python 3.12: install it for this user with winget (no admin rights needed)
echo [UYARI] Python 3.12 bulunamadi, otomatik kuruluyor (birkac dakika)...
echo         Python 3.12 not found, installing it automatically (a few minutes)...
where winget >nul 2>nul || goto elle_kur
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
call :python_bul
if defined PY goto ortam

:elle_kur
echo.
echo [HATA] Python 3.12 otomatik kurulamadi. Lutfen elle kurun:
echo   https://www.python.org/downloads/release/python-31210/ - "Windows installer (64-bit)",
echo   ilk ekranda "Add python.exe to PATH" kutusunu isaretleyin, sonra KURULUM.bat'i yeniden calistirin.
echo Could not install Python 3.12 automatically. Install it from the link above
echo (tick "Add python.exe to PATH") and run KURULUM.bat again.
pause
exit /b 1

:ortam
echo [TAMAM] Python: %PY%
echo [2/2] Python ortami (.venv) / environment
"%PY%" -m venv --clear --without-pip .venv
if errorlevel 1 goto hata
".venv\Scripts\python.exe" -c "import tkinter" || goto hata

:tamam
echo [TAMAM] Python 3.12 ortami hazir / environment ready
echo ok> ".venv\kurulum_tamam"
echo.
echo Kurulum tamam. BASLAT.bat ile acin. / Setup complete. Start with BASLAT.bat.
pause
exit /b 0

:hata
echo.
echo [HATA] Kurulum tamamlanamadi; yukaridaki mesaja bakin ve KURULUM.bat'i yeniden calistirin.
echo Setup failed; see the message above and run KURULUM.bat again.
pause
exit /b 1

rem PY: bulunan Python 3.12. Yeni kurulan Python bu pencerenin PATH'inde henuz gorunmez,
rem bu yuzden once bilinen kurulum klasorlerine bakilir.
:python_bul
set "PY="
for %%P in ("%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%ProgramFiles%\Python312\python.exe") do (
  if not defined PY if exist %%P set "PY=%%~P"
)
if defined PY exit /b 0
for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%P"
if defined PY exit /b 0
rem Microsoft Store'un sahte python.exe'si bir sey yazmaz, yanlislikla secilmez
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable if sys.version_info[:2] == (3, 12) else '')" 2^>nul') do set "PY=%%P"
exit /b 0
