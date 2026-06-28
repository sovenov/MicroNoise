@echo off
rem Установка зависимостей MicroNoise в Python 3.8
cd /d "%~dp0"
echo === Установка зависимостей (numpy, sounddevice) в Python 3.8 ===
py -3.8 -m pip install -r requirements.txt
echo.
echo Готово. Для запуска используйте run.bat
pause
