@echo off
REM ============================================================================
REM  VPyD Import Pipeline Test Suite
REM  Runs all import-related tests: parsers, generators, ledger, e2e pipeline
REM ============================================================================

setlocal enabledelayedexpansion

set PYTHON=C:\VPyD\.venv\Scripts\python.exe
set ROOT=C:\VPyD
set PASS_COUNT=0
set FAIL_COUNT=0
set TOTAL_SUITES=5

echo.
echo ============================================================
echo   VPyD Import Pipeline Test Suite
echo   Date: %date% %time%
echo ============================================================
echo.

REM --------------------------------------------------------------------------
REM 1. Compile Check — verify all parsers, generators, and core files compile
REM --------------------------------------------------------------------------
echo [1/%TOTAL_SUITES%] COMPILE CHECK - All parsers, generators, and core files
echo ------------------------------------------------------------
%PYTHON% -m pytest %ROOT%\tests\test_compile_check.py -v --tb=short
if %errorlevel% equ 0 (
    echo.
    echo   [PASS] Compile check passed
    set /a PASS_COUNT+=1
) else (
    echo.
    echo   [FAIL] Compile check FAILED
    set /a FAIL_COUNT+=1
)
echo.
timeout /t 2 /nobreak >nul

REM --------------------------------------------------------------------------
REM 2. Parser Imports — all 16 language parsers capture imports correctly
REM --------------------------------------------------------------------------
echo [2/%TOTAL_SUITES%] PARSER IMPORTS - 16 language parsers capture module.imports
echo ------------------------------------------------------------
%PYTHON% -m pytest %ROOT%\tests\test_parser_imports.py -v --tb=short
if %errorlevel% equ 0 (
    echo.
    echo   [PASS] Parser imports passed
    set /a PASS_COUNT+=1
) else (
    echo.
    echo   [FAIL] Parser imports FAILED
    set /a FAIL_COUNT+=1
)
echo.
timeout /t 2 /nobreak >nul

REM --------------------------------------------------------------------------
REM 3. Generator Imports — all 17 generators emit module.imports in output
REM --------------------------------------------------------------------------
echo [3/%TOTAL_SUITES%] GENERATOR IMPORTS - 17 generators emit imports in output
echo ------------------------------------------------------------
%PYTHON% -m pytest %ROOT%\tests\test_generator_imports.py -v --tb=short
if %errorlevel% equ 0 (
    echo.
    echo   [PASS] Generator imports passed
    set /a PASS_COUNT+=1
) else (
    echo.
    echo   [FAIL] Generator imports FAILED
    set /a FAIL_COUNT+=1
)
echo.
timeout /t 2 /nobreak >nul

REM --------------------------------------------------------------------------
REM 4. Session Ledger Imports — record/retrieve, dedup, strategy resolution
REM --------------------------------------------------------------------------
echo [4/%TOTAL_SUITES%] SESSION LEDGER - Import recording, retrieval, and strategy
echo ------------------------------------------------------------
%PYTHON% -m pytest %ROOT%\tests\test_session_ledger_imports.py -v --tb=short
if %errorlevel% equ 0 (
    echo.
    echo   [PASS] Session ledger imports passed
    set /a PASS_COUNT+=1
) else (
    echo.
    echo   [FAIL] Session ledger imports FAILED
    set /a FAIL_COUNT+=1
)
echo.
timeout /t 2 /nobreak >nul

REM --------------------------------------------------------------------------
REM 5. End-to-End Pipeline — parser -> ledger -> generator round-trip
REM --------------------------------------------------------------------------
echo [5/%TOTAL_SUITES%] E2E PIPELINE - Full round-trip (parse, ledger, generate)
echo ------------------------------------------------------------
%PYTHON% -m pytest %ROOT%\tests\test_import_pipeline_e2e.py -v --tb=short
if %errorlevel% equ 0 (
    echo.
    echo   [PASS] E2E pipeline passed
    set /a PASS_COUNT+=1
) else (
    echo.
    echo   [FAIL] E2E pipeline FAILED
    set /a FAIL_COUNT+=1
)
echo.
timeout /t 2 /nobreak >nul

REM --------------------------------------------------------------------------
REM Summary
REM --------------------------------------------------------------------------
echo ============================================================
echo   FINAL RESULTS
echo ============================================================
echo.
echo   Suites passed:  %PASS_COUNT% / %TOTAL_SUITES%
echo   Suites failed:  %FAIL_COUNT% / %TOTAL_SUITES%
echo.

if %FAIL_COUNT% gtr 0 (
    echo   *** SOME SUITES FAILED — see output above for details ***
    echo.
    exit /b 1
) else (
    echo   ALL SUITES PASSED
    echo.
    exit /b 0
)
