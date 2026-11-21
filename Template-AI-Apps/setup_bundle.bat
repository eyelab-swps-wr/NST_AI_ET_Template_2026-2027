@echo off
rem ==========================================================================
rem  Buduje przenosny Python 3.10 (64-bit) + PsychoPy + Tobii Pro SDK 2.1.0
rem  w folderze Template-AI-Apps\PsychoPy. Nic nie instaluje w systemie.
rem  Builds a portable Python 3.10 + PsychoPy + Tobii Pro SDK (Spectrum) bundle.
rem ==========================================================================
setlocal
cd /d "%~dp0"
set "PY_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20251014/cpython-3.10.19+20251014-x86_64-pc-windows-msvc-install_only.tar.gz"
set "PY_EXE=%~dp0PsychoPy\python.exe"

if exist "%PY_EXE%" goto deps
echo [1/2] Pobieranie przenosnego Pythona 3.10 ...
curl.exe -L --fail -o "%TEMP%\psychopy_bundle_py.tar.gz" "%PY_URL%" || goto fail
tar.exe -xzf "%TEMP%\psychopy_bundle_py.tar.gz" -C "%~dp0" || goto fail
ren "%~dp0python" PsychoPy || goto fail
del "%TEMP%\psychopy_bundle_py.tar.gz"

:deps
echo [2/2] Instalacja PsychoPy + tobii-research do bundla ...
"%PY_EXE%" -m pip install --no-warn-script-location -r requirements-students.txt || goto fail
"%PY_EXE%" -c "import psychopy, tobii_research as tr; print('OK  PsychoPy', psychopy.__version__, '| Tobii SDK', tr.__version__)" || goto fail
set "VOSK_DIR=%~dp0App 4 - Malowanie Glosem i Wzrokiem\models"
if not exist "%VOSK_DIR%\vosk-model-small-en-us-0.15" (
  echo Pobieranie modelu mowy Vosk dla App 4 ...
  if not exist "%VOSK_DIR%" mkdir "%VOSK_DIR%"
  curl.exe -L --fail -o "%TEMP%\vosk_model.zip" "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" || goto fail
  "%PY_EXE%" -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "%TEMP%\vosk_model.zip" "%VOSK_DIR%" || goto fail
  del "%TEMP%\vosk_model.zip"
)
echo.
echo Gotowe. Uruchamiaj aplikacje przez run_*.bat w folderach App.
pause
exit /b 0

:fail
echo.
echo BLAD - instalacja nie powiodla sie.
pause
exit /b 1
