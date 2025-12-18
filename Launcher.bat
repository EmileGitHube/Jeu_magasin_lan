@echo off
title Royaume des Kaplas - Serveur LAN
color 0A

echo.
echo ============================================================
echo      ROYAUME DES KAPLAS - MODE MULTIJOUEUR LAN
echo ============================================================
echo.

:: 1. DETECTION DE PYTHON
:: On cherche si 'python' ou 'py' est disponible
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY=python
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PY=py
    ) else (
        echo [ERREUR] Python n'est pas installe sur cet ordinateur.
        echo Veuillez l'installer depuis python.org (Cochez "Add to PATH")
        pause
        exit /b 1
    )
)
echo [OK] Python detecte (%PY%)

:: 2. INSTALLATION DES DEPENDANCES (Mise a jour complete)
echo.
echo [INFO] Verification des bibliotheques necessaires...
:: On installe tout d'un coup pour etre sur. Si c'est deja fait, ca ira tres vite.
%PY% -m pip install streamlit pandas Pillow qrcode gTTS >nul 2>&1

if %errorlevel% neq 0 (
    echo [ATTENTION] Une erreur est survenue lors de l'installation des dependances.
    echo Tentative d'installation avec affichage des erreurs...
    %PY% -m pip install streamlit pandas Pillow qrcode gTTS
    pause
) else (
    echo [OK] Toutes les dependances sont pretes.
)

:: 3. DETECTION INTELLIGENTE DE L'IP
echo.
echo [INFO] Recherche de l'adresse IP locale...
:: Priorite Wi-Fi, puis Ethernet, puis Localhost
set IP=
for /f "usebackq tokens=*" %%a in (`powershell -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -match 'Wi-Fi' -and $_.IPAddress -notmatch '169.254' } | Select-Object -ExpandProperty IPAddress -First 1"`) do set IP=%%a

if "%IP%"=="" (
    for /f "usebackq tokens=*" %%a in (`powershell -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -notmatch '169.254' } | Select-Object -ExpandProperty IPAddress -First 1"`) do set IP=%%a
)

if "%IP%"=="" set IP=localhost

echo.
echo ============================================================
echo ADRESSES DE CONNEXION DETECTEES
echo ============================================================
echo.
echo  ORDINATEUR MAITRE (Vous) : http://localhost:8501
echo.
echo  JOUEURS (Tel / Tablette) : http://%IP%:8501
echo.
echo ============================================================
echo.

:: 4. LANCEMENT DE LA MUSIQUE (SI PRESENTE)
if exist "Music.mp3" (
    echo [AMBIANCE] Lancement de la musique de fond...
    start "" "Music.mp3"
    echo (Pensez a activer le mode BOUCLE / REPEAT sur votre lecteur audio !)
) else (
    echo [INFO] Fichier 'Music.mp3' non trouve (Mode silencieux).
)

:: 5. LANCEMENT DU SERVEUR DE JEU
echo.
echo [START] Demarrage du serveur Royaume des Kaplas...
echo Ne fermez PAS cette fenetre noire tant que vous jouez.
echo.

:: Lancement en tache de fond (/B)
start /B %PY% -m streamlit run app_royaume_lan_multiplayer.py --server.address=0.0.0.0 --server.port=8501 --browser.serverAddress=%IP% --server.headless=true --theme.base="light"

:: Petite pause pour laisser le serveur chauffer
timeout /t 3 /nobreak >nul

:: Ouverture automatique du navigateur du Maître
start http://localhost:8501

:: Boucle pour garder la fenetre ouverte
pause >nul
