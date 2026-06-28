@echo off
rem Запуск MicroNoise без окна консоли (через pythonw 3.8)
cd /d "%~dp0"
start "" pyw -3.8 main.py
