@echo off
cd /D "%~dp0"

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m streamlit run st.py
) else (
    echo ERROR: .venv was not found.
    echo Run this setup command first:
    echo   python setup_env.py
)
pause
