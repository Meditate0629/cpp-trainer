@echo off
rem ============================================================
rem  Train Site launcher  (Windows)
rem
rem  KEEP THE CONTENT OF THIS FILE PURE ASCII.
rem  cmd.exe mis-parses .cmd/.bat files that contain multi-byte
rem  characters: it splits "rem" into "em" and drops whole lines,
rem  and the whole script runs shifted. English only, please.
rem
rem  Double-click to start. Opens http://127.0.0.1:8756/ in a browser.
rem  Close the black window to stop the server.
rem
rem  Looks for Python in this order:
rem    1. env var TS_PYTHON   (full path to python.exe)
rem    2. "py -3"             (python.org installer puts this on PATH)
rem    3. "python"            (conda / other installs)
rem  Nothing hard-coded, so this works on any machine.
rem ============================================================
setlocal
title Train Site

cd /d "%~dp0"

set "RUNNER="
if defined TS_PYTHON (
  if exist "%TS_PYTHON%" set RUNNER="%TS_PYTHON%"
)

if not defined RUNNER (
  where py >nul 2>nul
  if not errorlevel 1 set RUNNER=py -3
)
if not defined RUNNER (
  where python >nul 2>nul
  if not errorlevel 1 set RUNNER=python
)

if not defined RUNNER goto :nopython

echo.
echo   Starting the train site ...
echo.
echo   Code lives in the bank root: practice folder, S1 .. S9
echo   (VS Code opens exactly the same file), and progress goes back to
echo   the progress table csv in the bank root.
echo.
echo   Close this window (or press Ctrl+C) to stop the server.
echo.

%RUNNER% "server.py"
goto :done

:nopython
echo.
echo   Python 3 was not found.
echo.
echo   Install it from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" during setup.
echo.
echo   Already installed somewhere else? Set the full path first, e.g.
echo     set TS_PYTHON=C:\Python313\python.exe
echo     start.bat
echo.

:done
echo.
echo   Server stopped.
pause >nul
