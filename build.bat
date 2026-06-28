@echo off
rem Сборка MicroNoise папкой (onedir) для Windows, Python 3.8 x64.
rem Результат: dist\MicroNoise\ — запускается без установленного Python,
rem в т.ч. на Windows 7 (UCRT включается в сборку автоматически).
rem Распространять нужно всю папку dist\MicroNoise целиком.
cd /d "%~dp0"

echo === Зависимости ===
py -3.8 -m pip install -r requirements.txt
echo === PyInstaller (5.x — последняя ветка с поддержкой Windows 7) ===
py -3.8 -m pip install "pyinstaller==5.13.2"

echo === Сборка ===
py -3.8 -m PyInstaller --noconfirm --clean MicroNoise.spec

echo.
echo Готово: dist\MicroNoise\MicroNoise.exe
echo Распространяйте всю папку dist\MicroNoise целиком.
pause
