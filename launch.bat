cd %~dp0
start /wait "" python -m pip install -r requirements.txt
start "" pythonw main.py