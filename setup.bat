@echo off
echo Configurando entorno Python 3.11...
py -3.11 -m venv venv
call .\venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install
echo Entorno configurado correctamente!
pause