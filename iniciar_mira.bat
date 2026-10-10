@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python iniciar_mira.py
  goto :end
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 iniciar_mira.py
  goto :end
)
echo Instala Python desde https://www.python.org y marca la opcion tcl/tk.
pause
:end
