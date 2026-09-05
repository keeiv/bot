@echo off
REM Startup script for New Bot project
REM Changes current dir to script dir, uses venv python when available
cd /d "%~dp0"
setlocal EnableExtensions EnableDelayedExpansion
title New Bot Control Panel

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set "LOCK_FILE=%~dp0bot.lock"
set "LOG_DIR=%~dp0data\logs"

:MENU
cls
color 0B
echo.
echo   ==========================================================
echo                 N E W   B O T   C O N T R O L
echo   ==========================================================
echo.
call :SHOW_STATUS_LINE
echo.
echo       [1] Start bot in a new window
echo       [2] Stop bot
echo       [3] Restart bot
echo       [4] Show bot status
echo       [5] View latest bot log files
echo.
echo       [6] Install or update dependencies
echo       [7] Run test suite
echo       [8] Check code formatting
echo       [9] Check Cog imports
echo.
echo       [D] Developer commands guide
echo       [S] Open project folder
echo       [L] Open data and logs folder
echo       [Q] Exit
echo.
echo   ----------------------------------------------------------
choice /c 123456789DSLQ /n /m "  Select an action: "
set "MENU_CHOICE=!errorlevel!"

if !MENU_CHOICE! == 13 goto EXIT
if !MENU_CHOICE! == 12 goto OPEN_DATA
if !MENU_CHOICE! == 11 goto OPEN_PROJECT
if !MENU_CHOICE! == 10 goto DEVELOPER_GUIDE
if !MENU_CHOICE! == 9 goto CHECK_COGS
if !MENU_CHOICE! == 8 goto FORMAT_CHECK
if !MENU_CHOICE! == 7 goto TESTS
if !MENU_CHOICE! == 6 goto INSTALL
if !MENU_CHOICE! == 5 goto VIEW_LOGS
if !MENU_CHOICE! == 4 goto STATUS
if !MENU_CHOICE! == 3 goto RESTART
if !MENU_CHOICE! == 2 goto STOP
if !MENU_CHOICE! == 1 goto START
goto MENU

:START
cls
color 0A
call :IS_RUNNING
if !RUNNING! == 1 (
	echo.
	echo   [INFO] Bot is already running.
	pause
	goto MENU
)
echo.
echo   Starting bot in a separate window with:
echo   %PYTHON_EXE%
echo.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList '-m','src.main' -WorkingDirectory '%~dp0' -PassThru; $p.Id"`) do set "STARTED_PID=%%P"
if defined STARTED_PID (
	echo !STARTED_PID!>"%LOCK_FILE%"
	echo   [OK] Bot started with PID !STARTED_PID!.
) else (
	echo   [ERROR] Could not start the bot.
)
pause
goto MENU

:STOP
cls
color 0C
call :GET_LOCK_PID
if not defined BOT_PID (
	echo.
	echo   [INFO] No bot lock file was found.
	pause
	goto MENU
)
call :IS_PID_RUNNING "!BOT_PID!"
if !RUNNING! == 0 (
	echo.
	echo   [INFO] PID !BOT_PID! is no longer running.
	del /q "%LOCK_FILE%" 2>nul
	pause
	goto MENU
)
echo.
echo   Stopping bot PID !BOT_PID!...
taskkill /PID !BOT_PID! /T /F >nul 2>&1
if errorlevel 1 (echo   [ERROR] Failed to stop the bot.) else (echo   [OK] Bot stopped.&del /q "%LOCK_FILE%" 2>nul)
pause
goto MENU

:RESTART
call :STOP_SILENT
timeout /t 2 /nobreak >nul
goto START

:STATUS
cls
color 0B
echo.
echo   Bot status
echo   ----------------------------------------------------------
call :GET_LOCK_PID
if not defined BOT_PID (echo   Status: STOPPED&pause&goto MENU)
call :IS_PID_RUNNING "!BOT_PID!"
if !RUNNING! == 1 (echo   Status: RUNNING&echo   PID: !BOT_PID!&tasklist /FI "PID eq !BOT_PID!" /FO TABLE) else (echo   Status: STOPPED ^(stale lock file^))
pause
goto MENU

:VIEW_LOGS
cls
color 0E
echo.
echo   Recent log files
echo   ----------------------------------------------------------
if not exist "%LOG_DIR%" (echo   No log directory found.) else (dir /o-d /b "%LOG_DIR%" 2>nul&start "" explorer "%LOG_DIR%")
pause
goto MENU

:INSTALL
cls
color 0E
echo.
echo   Installing dependencies into the selected Python environment...
echo   ----------------------------------------------------------
"%PYTHON_EXE%" -m pip install -r requirements.txt
echo.
pause
goto MENU

:TESTS
cls
color 0D
echo.
echo   Running tests...
echo   ----------------------------------------------------------
set "PYTHONPATH=."
"%PYTHON_EXE%" -m pytest
set "PYTHONPATH="
echo.
pause
goto MENU

:FORMAT_CHECK
cls
color 09
echo.
echo   Checking code format with Black...
echo   ----------------------------------------------------------
"%PYTHON_EXE%" -m black --check src tests
echo.
pause
goto MENU

:CHECK_COGS
cls
color 0B
echo.
echo   Checking all Cog imports...
echo   ----------------------------------------------------------
"%PYTHON_EXE%" -c "import importlib, pkgutil, src.cogs; modules = [info.name for info in pkgutil.walk_packages(src.cogs.__path__, 'src.cogs.') if not info.ispkg]; [importlib.import_module(name) for name in modules]; print(f'[OK] Verified {len(modules)} Cog modules')"
echo.
pause
goto MENU

:DEVELOPER_GUIDE
cls
color 0D
echo.
echo   Developer commands are executed inside Discord by accounts
echo   listed in src/config/constants.py as DEVELOPER_IDS.
echo.
echo       /dev-status    View bot developer status
echo       !dev-status    View bot developer status
echo       ^>^>^>info         Open the interactive developer panel
echo.
echo   Use [5] from this panel to check Cog imports locally.
echo.
pause
goto MENU

:OPEN_PROJECT
start "" explorer "%~dp0"
goto MENU

:OPEN_DATA
start "" explorer "%~dp0data"
start "" explorer "%~dp0data\logs"
goto MENU

:SHOW_STATUS_LINE
call :GET_LOCK_PID
if not defined BOT_PID (
	echo   Status: [STOPPED]
) else (
	call :IS_PID_RUNNING "!BOT_PID!"
	if !RUNNING! == 1 (echo   Status: [RUNNING] PID !BOT_PID!) else (echo   Status: [STOPPED - stale lock])
)
exit /b

:GET_LOCK_PID
set "BOT_PID="
if exist "%LOCK_FILE%" set /p "BOT_PID="<"%LOCK_FILE%"
exit /b

:IS_RUNNING
call :GET_LOCK_PID
if not defined BOT_PID (set "RUNNING=0"&exit /b)
call :IS_PID_RUNNING "!BOT_PID!"
exit /b

:IS_PID_RUNNING
set "RUNNING=0"
for /f "tokens=2 delims=," %%P in ('tasklist /FI "PID eq %~1" /FO CSV /NH 2^>nul') do if "%%~P" == "%~1" set "RUNNING=1"
exit /b

:STOP_SILENT
call :GET_LOCK_PID
if not defined BOT_PID exit /b
call :IS_PID_RUNNING "!BOT_PID!"
if !RUNNING! == 1 taskkill /PID !BOT_PID! /T /F >nul 2>&1
del /q "%LOCK_FILE%" 2>nul
exit /b

:EXIT
color 07
endlocal
exit /b
