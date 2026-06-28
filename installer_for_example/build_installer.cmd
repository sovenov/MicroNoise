@echo off
setlocal

cd /d "%~dp0"

set "ISCC_PATH="
for %%I in (ISCC.exe) do set "ISCC_PATH=%%~$PATH:I"

if not defined ISCC_PATH if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if not defined ISCC_PATH (
    echo ISCC.exe not found. Install Inno Setup 6 or add it to PATH.
    pause
    exit /b 1
)

if not exist "..\dist\TranscriptorDesktop\TranscriptorDesktop.exe" (
    echo dist\TranscriptorDesktop\TranscriptorDesktop.exe not found.
    echo Build the PyInstaller binary first.
    pause
    exit /b 1
)

"%ISCC_PATH%" "TranscriptorDesktop.iss"
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
    echo.
    echo Installer build completed. Output: ..\installer_output
) else (
    echo.
    echo Installer build failed with exit code %EXIT_CODE%.
)

pause
exit /b %EXIT_CODE%
