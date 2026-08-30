@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   Ru-Curve - EXE Build
echo ============================================
echo Arbeitsordner: %cd%
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python wurde nicht gefunden.
    echo Bitte Python von https://www.python.org/downloads/ installieren
    echo und beim Setup "Add Python to PATH" anhaken.
    goto :ende_fehler
)
echo [OK] Python gefunden:
python --version

echo.
echo [1/4] Abhaengigkeiten installieren (pygame-ce, numpy, pyinstaller)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :ende_fehler
echo [OK] Abhaengigkeiten installiert.

echo.
echo [2/4] Assets erzeugen (Sounds, Musik, Icon)...
python tools\make_assets.py
if errorlevel 1 echo   (Assets-Generator meldete einen Fehler - Build laeuft trotzdem weiter)

echo.
echo [3/4] EXE mit PyInstaller bauen...
set ICONOPT=
if exist "icon.ico" set ICONOPT=--icon "icon.ico"
rmdir /s /q build dist >nul 2>&1
del /q "Ru-Curve.spec" >nul 2>&1
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name "Ru-Curve" ^
    %ICONOPT% ^
    --add-data "assets;assets" ^
    --collect-submodules rucurve ^
    main.py
if errorlevel 1 goto :ende_fehler

for %%A in ("dist\Ru-Curve.exe") do set EXESIZE=%%~zA
if not defined EXESIZE goto :ende_fehler
if %EXESIZE% LSS 3000000 (
    echo FEHLER: dist\Ru-Curve.exe ist nur %EXESIZE% Bytes gross - Build kaputt.
    echo Tipp: "icon.ico" loeschen und erneut bauen.
    goto :ende_fehler
)

if not exist "dist\Ru-Curve.exe" (
    echo FEHLER: Build lief durch, aber dist\Ru-Curve.exe fehlt.
    goto :ende_fehler
)

echo.
echo [4/4] ZIP-Paket erstellen (zum Weitergeben - umgeht den Download-Fehlalarm)...
powershell -NoProfile -Command "Copy-Item 'LIESMICH-Download.txt' 'dist\LIESMICH.txt' -ErrorAction SilentlyContinue; Compress-Archive -Path 'dist\Ru-Curve.exe','dist\LIESMICH.txt' -DestinationPath 'dist\Ru-Curve.zip' -Force -ErrorAction SilentlyContinue; if (-not (Test-Path 'dist\Ru-Curve.zip')) { Compress-Archive -Path 'dist\Ru-Curve.exe' -DestinationPath 'dist\Ru-Curve.zip' -Force }"

echo.
echo Fertig!
echo   EXE:  %cd%\dist\Ru-Curve.exe
echo   ZIP:  %cd%\dist\Ru-Curve.zip   (fuer den Download / zum Weitergeben)
echo.
pause
exit /b 0

:ende_fehler
echo.
echo Build ABGEBROCHEN. Fehler oben lesen/beheben und erneut ausfuehren.
pause
exit /b 1
