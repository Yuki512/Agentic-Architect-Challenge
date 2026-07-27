@echo off
setlocal

set "ROOT=%~dp0"
set "PART_DIR=%ROOT%part1"
set "SCRIPT=%PART_DIR%\scripts\run_web_app.py"
set "APP_URL=http://127.0.0.1:8000"
set "APP_PORT=8000"

call :find_python
if not defined PYTHON_EXE (
  echo Python could not be found.
  echo Install Python 3 or run this project from the Codex workspace.
  pause
  exit /b 1
)

if not exist "%SCRIPT%" (
  echo Part 1 server script was not found:
  echo %SCRIPT%
  pause
  exit /b 1
)

if /I "%~1"=="--check" (
  echo Part 1 launcher check passed.
  echo Python: %PYTHON_EXE%
  echo URL: %APP_URL%
  exit /b 0
)

call :server_is_running
if errorlevel 1 (
  start "Part 1 Server - close this window to stop" /D "%PART_DIR%" "%ComSpec%" /k ""%PYTHON_EXE%" "%SCRIPT%""
  call :wait_for_server
  if errorlevel 1 (
    echo Part 1 did not become ready within 12 seconds.
    echo Check the Part 1 Server window for the error.
    pause
    exit /b 1
  )
)

if /I not "%~1"=="--start-only" start "" "%APP_URL%"
exit /b 0

:find_python
set "PYTHON_EXE="

if exist "%PART_DIR%\.venv\Scripts\python.exe" (
  "%PART_DIR%\.venv\Scripts\python.exe" -c "import pdfplumber, langgraph" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=%PART_DIR%\.venv\Scripts\python.exe"
)

if not defined PYTHON_EXE if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -c "import pdfplumber, langgraph" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

for /f "delims=" %%P in ('python -c "import pdfplumber, langgraph, sys; print(sys.executable)" 2^>nul') do (
  if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
  for /f "delims=" %%P in ('py -3 -c "import pdfplumber, langgraph, sys; print(sys.executable)" 2^>nul') do (
    if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
  )
)
exit /b 0

:server_is_running
powershell -NoProfile -Command "$client = New-Object Net.Sockets.TcpClient; try { $client.Connect('127.0.0.1', %APP_PORT%); exit 0 } catch { exit 1 } finally { $client.Dispose() }" >nul 2>&1
exit /b %errorlevel%

:wait_for_server
powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(12); do { try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%APP_URL%/' -TimeoutSec 1; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 250 } while ((Get-Date) -lt $deadline); exit 1" >nul 2>&1
exit /b %errorlevel%
