@echo off
setlocal
title AccessReaper v2 — Remove Auto-Start Task

echo =======================================================================
echo          AccessReaper v2 — Remove Windows Auto-Start Task
echo =======================================================================
echo.

set "TASK_NAME=AccessReaper-v2-AutoStart"

echo [*] Removing scheduled task '%TASK_NAME%'...
schtasks /Delete /TN "%TASK_NAME%" /F

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Auto-start task '%TASK_NAME%' was removed successfully.
) else (
    echo.
    echo [INFO] Task '%TASK_NAME%' was not found or already removed.
)

echo.
pause
