@echo off
cd /d "%~dp0"
set PYTHONPATH=.
streamlit run app/ui/streamlit_app.py
