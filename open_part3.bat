@echo off
setlocal

set "ROOT=%~dp0"
set "PART_DIR=%ROOT%part3"
set "PYTHON_EXE=%PART_DIR%\.venv\Scripts\python.exe"
set "SCRIPT=%PART_DIR%\scripts\run_web_app.py"
set "APP_URL=http://127.0.0.1:9000"
set "APP_PORT=9000"

if not exist "%PYTHON_EXE%" (
  echo Part 3 Python environment was not found:
  echo %PYTHON_EXE%
  echo Run the Part 3 setup before starting the app.
  pause
  exit /b 1
)

if not exist "%SCRIPT%" (
  echo Part 3 server script was not found:
  echo %SCRIPT%
  pause
  exit /b 1
)

"%PYTHON_EXE%" -c "import langgraph, pdfplumber, rank_bm25" >nul 2>&1
if errorlevel 1 (
  echo Part 3 dependencies are incomplete.
  echo Check part3\requirements.txt and the Part 3 virtual environment.
  pause
  exit /b 1
)

if /I "%~1"=="--check" (
  echo Part 3 launcher check passed.
  echo Python: %PYTHON_EXE%
  echo URL: %APP_URL%
  exit /b 0
)

call :server_is_running
if errorlevel 1 (
  start "Part 3 Server - close this window to stop" /D "%PART_DIR%" "%ComSpec%" /k ""%PYTHON_EXE%" "%SCRIPT%" --port %APP_PORT%"
  call :wait_for_server
  if errorlevel 1 (
    echo Part 3 did not become ready within 20 seconds.
    echo Check the Part 3 Server window for the error.
    pause
    exit /b 1
  )
)

if /I not "%~1"=="--start-only" start "" "%APP_URL%"
exit /b 0

:server_is_running
powershell -NoProfile -Command "$client = New-Object Net.Sockets.TcpClient; try { $client.Connect('127.0.0.1', %APP_PORT%); exit 0 } catch { exit 1 } finally { $client.Dispose() }" >nul 2>&1
exit /b %errorlevel%

:wait_for_server
powershell -NoProfile -Command "$deadline = (Get-Date).AddSeconds(20); do { try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%APP_URL%/api/health' -TimeoutSec 1; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 250 } while ((Get-Date) -lt $deadline); exit 1" >nul 2>&1
exit /b %errorlevel%
