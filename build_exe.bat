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
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name "Ru-Curve" ^
    --icon "icon.ico" ^
    --add-data "assets;assets" ^
    --collect-submodules rucurve ^
    main.py
if errorlevel 1 goto :ende_fehler

if not exist "dist\Ru-Curve.exe" (
    echo FEHLER: Build lief durch, aber dist\Ru-Curve.exe fehlt.
    goto :ende_fehler
)

echo.
echo [4/4] Fertig!  ->  %cd%\dist\Ru-Curve.exe
echo.
pause
exit /b 0

:ende_fehler
echo.
echo Build ABGEBROCHEN. Fehler oben lesen/beheben und erneut ausfuehren.
pause
exit /b 1
