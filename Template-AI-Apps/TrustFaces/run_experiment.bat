@echo off
rem Zaufanie do twarzy - uruchomienie. Argumenty: --sim  --windowed  --autotest
rem Kolejnosc wyboru Pythona:
rem   1) zmienna PSYCHOPY_PYTHON, 2) bundlowany ..\PsychoPy\python.exe (setup_bundle.bat),
rem   3) awaryjnie: uv (jesli zainstalowany) z tymczasowym srodowiskiem Python 3.10 + PsychoPy.
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHON_EXE=%~dp0..\PsychoPy\python.exe"
if defined PSYCHOPY_PYTHON set "PYTHON_EXE=%PSYCHOPY_PYTHON%"
if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" trust_faces_experiment.py %*
  goto end
)
where uv >nul 2>nul
if %errorlevel%==0 (
  echo Brak bundlowanego Pythona - uruchamiam przez uv ^(pierwsze uruchomienie moze potrwac^)...
  uv run --python 3.10 --with "psychopy>=2024.2.0" --with "tobii-research==2.1.0" python trust_faces_experiment.py %*
  goto end
)
echo Brak bundlowanego Pythona: %PYTHON_EXE%
echo Uruchom najpierw ..\setup_bundle.bat
:end
pause
