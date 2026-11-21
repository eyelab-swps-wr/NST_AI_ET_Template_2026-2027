# AI Template App - Tobii Pro Spectrum

This template uses the official Tobii Pro SDK Python package `tobii-research`
2.1.0, which supports the Tobii Pro Spectrum. The older SDK bundled for
X3-120 is not used by this app.

## Setup on Windows

1. Use the app's bundled PsychoPy Python or the shared PsychoPy Python. It
   must be 64-bit Python 3.10. Install Tobii Pro Eye Tracker Manager.
2. Install the app dependencies into that same bundled environment. For the
   existing shared layout:

   ```powershell
   ..\PsychoPy\python.exe -m pip install -r requirements.txt
   ```

   For an app-local runtime, use its `python.exe` path (for example,
   `.\PsychoPy\python.exe` or `.\python.exe`). For a shared runtime elsewhere,
   set `PSYCHOPY_PYTHON` to its full path, then use it to install dependencies
   and launch the app:

   ```bat
   set "PSYCHOPY_PYTHON=C:\path\to\PsychoPy\python.exe"
   "%PSYCHOPY_PYTHON%" -m pip install -r requirements.txt
   run_app.bat
   ```

3. Connect the Pro Spectrum, then run `run_app.bat`. On this workstation it
   also checks the shared runtime at
   `%USERPROFILE%\Desktop\ST_AI_ET_Template_2026-2027\Template-AI-Apps\PsychoPy\python.exe`.
   It does not use a system Python installation.

The Tobii SDK is distributed under Tobii's license and is installed through
the official `tobii-research` package; it is not copied into this template.
