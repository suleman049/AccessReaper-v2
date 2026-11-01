@echo off
setlocal
title AccessReaper v2 — Install Auto-Start Task

echo =======================================================================
echo          AccessReaper v2 — Windows Task Scheduler Auto-Start
echo =======================================================================
echo.
echo This registers AccessReaper v2 to automatically start in the background
echo whenever you log into Windows, ensuring 24-hour automatic IAM audits
echo and the countdown timer remain active continuously.
echo.
echo Note: For true 24/7 server environments with automated recovery,
echo see docs\DEPLOYMENT.md (Stage 6 Docker / VPS setup).
echo.

set "TASK_NAME=AccessReaper-v2-AutoStart"
set "LAUNCHER_PATH=%~dp0..\Start-AccessReaper-v2.cmd"

if not exist "%LAUNCHER_PATH%" (
    echo [ERROR] Launcher not found at "%LAUNCHER_PATH%".
    pause
    exit /b 1
)

echo [*] Registering scheduled task '%TASK_NAME%' to run at logon...
schtasks /Create /TN "%TASK_NAME%" /TR "cmd.exe /c start /min \"\" \"%LAUNCHER_PATH%\"" /SC ONLOGON /RL HIGHEST /F

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Auto-start task '%TASK_NAME%' registered successfully!
    echo AccessReaper v2 will now launch automatically on logon.
    echo To uninstall, run tools\Remove-AutoStart.cmd.
) else (
    echo.
    echo [ERROR] Failed to register task. Make sure to run this script as Administrator.
)

echo.
pause
