@echo off
REM Gibt Ru-Curve in der Windows-Firewall frei (Spielen ueber LAN).
REM Muss als Administrator ausgefuehrt werden: Rechtsklick -> "Als Administrator ausfuehren"
setlocal
cd /d "%~dp0.."

echo ============================================
echo   Ru-Curve - Firewall fuer LAN freigeben
echo ============================================
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Diese Datei muss als Administrator laufen.
    echo Rechtsklick auf firewall_freigeben.bat  ->  "Als Administrator ausfuehren"
    echo.
    pause
    exit /b 1
)

echo Entferne alte Regeln ...
netsh advfirewall firewall delete rule name="Ru-Curve LAN" >nul 2>&1

echo Erlaube eingehende Verbindungen ...
netsh advfirewall firewall add rule name="Ru-Curve LAN" dir=in action=allow protocol=TCP localport=51738-51745 profile=any
netsh advfirewall firewall add rule name="Ru-Curve LAN" dir=in action=allow protocol=UDP localport=51737 profile=any

if exist "dist\Ru-Curve\Ru-Curve.exe" (
    echo Erlaube das Programm selbst ...
    netsh advfirewall firewall add rule name="Ru-Curve LAN" dir=in action=allow program="%cd%\dist\Ru-Curve\Ru-Curve.exe" enable=yes profile=any
)

echo.
echo Fertig. Beide Rechner muessen im selben Netz sein (gleiches WLAN).
echo Auf dem Host-PC:  Hauptmenue -> "Uber LAN hosten"
echo Auf dem anderen:  Hauptmenue -> "Uber LAN beitreten"
echo.
pause
