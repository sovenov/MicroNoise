@echo off
setlocal

cd /d "%~dp0"

rem --- Поиск компилятора Inno Setup (ISCC.exe) ---
set "ISCC_PATH="
for %%I in (ISCC.exe) do set "ISCC_PATH=%%~$PATH:I"

if not defined ISCC_PATH if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if not defined ISCC_PATH (
    echo ISCC.exe не найден. Установите Inno Setup 6 или добавьте его в PATH.
    pause
    exit /b 1
)

rem --- Проверка, что готовая сборка существует ---
if not exist "..\dist\MicroNoise\MicroNoise.exe" (
    echo Не найден ..\dist\MicroNoise\MicroNoise.exe
    echo Сначала соберите программу (build.bat / PyInstaller).
    pause
    exit /b 1
)

"%ISCC_PATH%" "MicroNoise.iss"
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
    echo.
    echo Установщик собран. Результат: ..\installer_output\MicroNoiseSetup.exe
) else (
    echo.
    echo Сборка установщика завершилась с ошибкой, код %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
