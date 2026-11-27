@echo off
title YouTube Shorts AI Studio
cd /d "%~dp0"
echo =======================================================
echo          Starting YouTube Shorts AI Studio
echo =======================================================
if exist .venv\Scripts\streamlit.exe (
    .venv\Scripts\streamlit.exe run app.py
) else (
    streamlit run app.py
)
pause
