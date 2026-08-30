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
echo [3/4] Mit PyInstaller bauen (Ordner-Modus - weniger Virenscanner-Fehlalarme)...
set ICONOPT=
if exist "icon.ico" set ICONOPT=--icon "icon.ico"
set VEROPT=
if exist "version.txt" set VEROPT=--version-file "version.txt"
rmdir /s /q build dist >nul 2>&1
del /q "Ru-Curve.spec" >nul 2>&1
python -m PyInstaller --noconfirm --onedir --windowed --noupx ^
    --name "Ru-Curve" ^
    %ICONOPT% %VEROPT% ^
    --add-data "assets;assets" ^
    --collect-submodules rucurve ^
    main.py
if errorlevel 1 goto :ende_fehler

if not exist "dist\Ru-Curve\Ru-Curve.exe" (
    echo FEHLER: Build lief durch, aber dist\Ru-Curve\Ru-Curve.exe fehlt.
    goto :ende_fehler
)

echo.
echo [4/4] ZIP-Paket erstellen...
if exist "LIESMICH-Download.txt" copy /y "LIESMICH-Download.txt" "dist\Ru-Curve\LIESMICH.txt" >nul
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Ru-Curve' -DestinationPath 'dist\Ru-Curve.zip' -Force"
if not exist "dist\Ru-Curve.zip" goto :ende_fehler

echo.
echo Fertig!
echo   Ordner:  %cd%\dist\Ru-Curve\  (Ru-Curve.exe darin starten)
echo   ZIP:     %cd%\dist\Ru-Curve.zip  (zum Weitergeben / Herunterladen)
echo.
pause
exit /b 0

:ende_fehler
echo.
echo Build ABGEBROCHEN. Fehler oben lesen/beheben und erneut ausfuehren.
pause
exit /b 1
