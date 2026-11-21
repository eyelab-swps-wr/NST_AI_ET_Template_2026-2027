@echo off
rem Wersja HTML badania: uruchamia lokalny most Tobii (tobii_bridge.py) i otwiera strone w przegladarce.
rem Argumenty: --sim (dane syntetyczne, TYLKO test)  --no-browser  --port N
rem Wybor Pythona: 1) PSYCHOPY_PYTHON, 2) ..\PsychoPy\python.exe, 3) uv (tymczasowe srodowisko z tobii-research).
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHON_EXE=%~dp0..\PsychoPy\python.exe"
if defined PSYCHOPY_PYTHON set "PYTHON_EXE=%PSYCHOPY_PYTHON%"
if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" tobii_bridge.py %*
  goto end
)
where uv >nul 2>nul
if %errorlevel%==0 (
  echo Brak bundlowanego Pythona - uruchamiam przez uv...
  uv run --python 3.10 --with "tobii-research==2.1.0" python tobii_bridge.py %*
  goto end
)
echo Brak bundlowanego Pythona: %PYTHON_EXE%
echo Uruchom najpierw ..\setup_bundle.bat
:end
pause
