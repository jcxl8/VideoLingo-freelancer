@echo off
cd /D "%~dp0"

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m streamlit run st.py
) else (
    call conda activate videolingo
    if errorlevel 1 (
        echo ERROR: No .venv or legacy Conda environment was found.
        echo Run: python setup_env.py
        pause
        exit /b 1
    )
    python -m streamlit run st.py
)
pause
