@echo off
rem Uruchamia aplikacje bundlowanym Pythonem PsychoPy (Template-AI-Apps\PsychoPy)
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0..\PsychoPy\python.exe"
if defined PSYCHOPY_PYTHON set "PYTHON_EXE=%PSYCHOPY_PYTHON%"
if not exist "%PYTHON_EXE%" (
  echo Brak bundlowanego Pythona: %PYTHON_EXE%
  echo Uruchom najpierw ..\setup_bundle.bat
  pause
  exit /b 1
)
"%PYTHON_EXE%" app4_malowanie_glosem_i_wzrokiem.py
pause
