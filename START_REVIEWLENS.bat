@echo off
setlocal
cd /d "%~dp0"
echo Starting ReviewLens...
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements-tested.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto failed
goto end
:failed
echo.
echo Setup could not finish. Keep this window open and share the error above.
pause
:end
endlocal
