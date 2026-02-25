@echo off
REM ============================================================================
REM  VPyD Full Test Suite Runner
REM  Runs ALL tests in the tests/ folder — existing + import pipeline tests
REM ============================================================================

setlocal enabledelayedexpansion

set PYTHON=C:\VPyD\.venv\Scripts\python.exe
set ROOT=C:\VPyD

echo.
echo ============================================================
echo   VPyD Full Test Suite
echo   Date: %date% %time%
echo ============================================================
echo.
echo Running ALL test files in tests/ ...
echo.

%PYTHON% -m pytest %ROOT%\tests\ -v --tb=short

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   ALL TESTS PASSED
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo   SOME TESTS FAILED — see output above for details
    echo ============================================================
    exit /b 1
)

exit /b 0
