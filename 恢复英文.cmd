@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0manage.py" restore
    goto done
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0manage.py" restore
    goto done
)
echo Python 3.9+ is required. Please install Python from python.org.
:done
echo.
pause
endlocal
