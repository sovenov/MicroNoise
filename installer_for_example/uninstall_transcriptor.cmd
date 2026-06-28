@echo off
setlocal
set "APP_DIR=%~dp0"

for %%F in ("%APP_DIR%unins*.exe") do (
    if exist "%%~fF" (
        start "" "%%~fF"
        exit /b 0
    )
)

echo Transcriptor Desktop uninstaller was not found.
pause
exit /b 1
