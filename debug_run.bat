@echo off
cd /d "C:\Users\Trova\Documents\QUIZZO"
call .venv\Scripts\activate.bat
echo Starting app with error debugging...
python -c "import traceback; import sys; sys.path.insert(0, '.'); exec(open('app.py').read())" 2>&1
pause