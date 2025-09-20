@echo off
REM ============================================================
REM Pre-entrega: verificación pasiva (Windows)
REM Modos:
REM   - sin argumentos           -> proyecto local
REM   - argumento = ruta a ZIP   -> --zip
REM   - argumento = URL http(s)  -> --remote-zip  (requiere 'pip install requests')
REM Genera: reports\verify_report.html  y  reports\rounds_summary.csv
REM ============================================================

setlocal ENABLEDELAYEDEXPANSION
set PROJECT_ROOT=%~dp0
set REPORT_DIR=%PROJECT_ROOT%reports
set HTML=%REPORT_DIR%\verify_report.html
set CSV=%REPORT_DIR%\rounds_summary.csv

if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"

set MODE=local
set ARG=%~1

if not "%ARG%"=="" (
  echo Argumento detectado: %ARG%
  if exist "%ARG%" (
    set MODE=zip
  ) else (
    echo %ARG% | findstr /R /C:"^https\?://" >nul
    if %ERRORLEVEL%==0 (
      set MODE=remote
    ) else (
      REM Si no existe y no es http(s), igualmente tratamos como ZIP y fallará claro si no existe
      set MODE=zip
    )
  )
)

set CMD=python "%PROJECT_ROOT%verify_tournament.py" --strict --html "%HTML" --rounds-csv "%CSV" --open

if "%MODE%"=="zip"     set CMD=%CMD% --zip "%ARG%"
if "%MODE%"=="remote"  set CMD=%CMD% --remote-zip "%ARG%"

echo.
echo Ejecutando: %CMD%
echo.

%CMD%
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% NEQ 0 (
  echo.
  echo [!] Incidencias detectadas. Revisa:
  echo     %HTML%
  echo     %CSV%
  pause
  exit /b %EXITCODE%
) else (
  echo.
  echo [OK] Verificacion superada. Informes en:
  echo     %HTML%
  echo     %CSV%
  start "" "%HTML%"
  exit /b 0
)
