@echo off
REM ============================================================
REM  Transport Scolaire Intelligent
REM  Lance les microservices manquants, chacun dans son terminal.
REM  A executer depuis la racine du projet.
REM
REM  RELANCE SANS RISQUE : le script recense d'abord les ports
REM  deja occupes et ne demarre QUE les services absents. On peut
REM  donc fermer une fenetre, relancer le .bat, et seul le service
REM  arrete redemarre -- sans le mur de "Port already in use" que
REM  produisait l'ancienne version.
REM
REM  Usage :
REM    start-all-ms.bat            demarre les services manquants
REM    start-all-ms.bat /clean     arrete TOUT puis redemarre tout
REM    start-all-ms.bat /stop      arrete tout et quitte
REM    start-all-ms.bat /status    affiche l'etat et quitte
REM ============================================================
setlocal enabledelayedexpansion
set ROOT=%~dp0
REM --- Python (env conda "nlp", Python 3.11) : chemin direct, pas besoin d'activation ---
set NLP_PY=C:\Users\Anass\.conda\envs\nlp\python.exe

REM Ports surveilles (doit rester aligne avec les appels a :lancer plus bas).
set PORTS=8080,8081,8082,8083,8084,8085,8086,8087,8088,8089,8090,8091,8092

set "F_ACTIFS=%TEMP%\ts-ports-actifs.txt"
set "F_ORPHELINS=%TEMP%\ts-ports-orphelins.txt"
set NB_LANCES=0
set NB_ACTIFS=0
set NB_ORPHELINS=0

if /I "%~1"=="/stop"   goto :mode_stop
if /I "%~1"=="/status" goto :mode_status
if /I "%~1"=="/clean"  goto :mode_clean
goto :mode_normal

:mode_stop
call :arreter_tout
echo.
echo   Tous les services du projet ont ete arretes.
goto :fin_courte

:mode_status
call :recenser
echo ============================================================
echo   Etat des microservices
echo ============================================================
call :afficher_etat
goto :fin_courte

:mode_clean
echo ============================================================
echo   Mode /clean : arret complet avant redemarrage
echo ============================================================
call :arreter_tout
echo.
goto :mode_normal

:mode_normal
echo ============================================================
echo   Demarrage Transport Scolaire - services manquants
echo ============================================================
echo.

REM ---------- 0) Recensement de ce qui tourne deja ----------
call :recenser

REM ---------- 1) Infrastructure (Docker + OSRM) ----------
REM  Ces deux commandes sont deja idempotentes : un conteneur deja
REM  demarre n'est pas relance, elles sont donc laissees telles quelles.
echo [1/4] Infrastructure : PostgreSQL / Redis / RabbitMQ + OSRM...
docker-compose up -d
docker start osrm_meknes >nul 2>&1
echo.

REM ---------- 2) Microservices Java (Spring Boot) ----------
REM   Si "mvn" est introuvable, remplacer par "mvnw.cmd spring-boot:run".
echo [2/4] Services Java (MS7 et MS13 d'abord)...
set AVANT=%NB_LANCES%
call :lancer "MS7 - Auth (8087)"          8087 ms7-auth        "mvn spring-boot:run"
REM MS13 tot dans l'ordre : tous les autres services lisent leur configuration chez lui
REM au demarrage. S'il est absent, ils partent sur les valeurs de leur .env (mode degrade).
call :lancer "MS13 - Parametres (8092)"   8092 ms13-parametres "mvn spring-boot:run"
REM Le delai n'a de sens que si l'un des deux vient d'etre lance : inutile de faire
REM patienter 5 s quelqu'un qui relance le script pour un seul service manquant.
if not "%AVANT%"=="%NB_LANCES%" timeout /t 5 >nul

call :lancer "MS1 - Bus (8081)"           8081 ms1-bus         "mvn spring-boot:run"
call :lancer "MS2 - Eleves (8082)"        8082 ms2-eleves      "mvn spring-boot:run"
call :lancer "MS3 - Localisation (8083)"  8083 ms3-localisation "mvn spring-boot:run"
call :lancer "MS10 - Incidents (8090)"    8090 ms10-incidents  "mvn spring-boot:run"
call :lancer "MS4 - Notifications (8084)" 8084 ms4-notifications "mvn spring-boot:run"
echo.

REM ---------- 3) Microservices Python (FastAPI, env nlp) ----------
echo [3/4] Services Python (clustering + ETA + anomalies + VRP + LLM)...
call :lancer "MS6 - Clustering (8086)"          8086 ms6-clustering    "%NLP_PY% -m uvicorn main:app --host 0.0.0.0 --port 8086 --reload"
call :lancer "MS12 - Prediction ETA (8088)"     8088 ms12-prediction   "%NLP_PY% -m uvicorn main:app --host 0.0.0.0 --port 8088 --reload"
call :lancer "MS11 - Analytique/Anomalies (8091)" 8091 ms11-analytique "%NLP_PY% -m uvicorn main:app --host 0.0.0.0 --port 8091 --reload"
call :lancer "MS5 - Planification/VRP (8085)"   8085 ms5-planification "%NLP_PY% -m uvicorn main:app --host 0.0.0.0 --port 8085 --reload"
call :lancer "MS9 - Assistant LLM (8089)"       8089 ms9-llm           "%NLP_PY% -m uvicorn main:app --host 0.0.0.0 --port 8089 --reload"
echo.

REM ---------- 4) API Gateway (en DERNIER) ----------
echo [4/4] API Gateway...
set AVANT=%NB_LANCES%
call :lancer "MS8 - Gateway (8080)" 8080 ms8-gateway "mvn spring-boot:run"
REM Le delai ne sert que si d'autres services viennent d'etre lances : la passerelle
REM route vers eux, autant leur laisser une avance.
if not "%AVANT%"=="0" if not "%AVANT%"=="%NB_LANCES%" timeout /t 10 >nul

echo.
echo ============================================================
echo   Resultat : %NB_LANCES% demarre(s), %NB_ACTIFS% deja actif(s)
if not "%NB_ORPHELINS%"=="0" echo   ATTENTION : %NB_ORPHELINS% port(s) bloque(s) - relancer avec /clean
echo ============================================================
echo   Java   : MS7:8087  MS13:8092  MS1:8081  MS2:8082  MS3:8083  MS10:8090  MS4:8084  MS8(GW):8080
echo   Python : MS6:8086  MS12:8088  MS11:8091  MS5:8085  MS9:8089   (env nlp)
echo   ---------------------------------------------------------
echo   Gateway : http://localhost:8080
echo   Reglages: http://localhost:5173/settings   (config de tout le systeme)
echo   Console : html_tests\test-console.html
echo   OSRM    : http://localhost:5000
echo ============================================================
echo   Relancer ce script ne demarre que les services manquants.
echo   /clean pour tout redemarrer, /status pour voir l'etat.
echo ============================================================
goto :fin

REM ============================================================
REM  Sous-programmes
REM ============================================================

REM --- Recense les ports occupes -------------------------------
REM  Deux listes, et le critere qui les separe a ete choisi par l'experience :
REM   - ACTIFS  : le port repond en HTTP -> un service tourne, on ne le relance pas
REM   - BLOQUES : port en ecoute mais AUCUNE reponse HTTP -> un demarrage echouerait
REM               sur "Port already in use" sans que rien ne serve les requetes.
REM
REM  ATTENTION, piege : la premiere version testait si le PROCESSUS PROPRIETAIRE du
REM  socket etait vivant. C'est faux. "uvicorn --reload" lance un processus enfant
REM  qui herite du socket ; tuer le parent laisse l'enfant SERVIR NORMALEMENT, avec
REM  un socket dont le proprietaire declare est mort. MS9 a ainsi ete classe "bloque"
REM  alors qu'il repondait 200. Une fausse alerte est pire que pas d'alerte : elle
REM  envoie reparer ce qui marche. Seule une requete HTTP dit la verite.
REM
REM  Le cout reste faible : on n'interroge que les ports DEJA en ecoute. Tout eteint,
REM  aucune requete n'est emise.
:recenser
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ports=@(%PORTS%);" ^
 "$ecoute=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -ExpandProperty LocalPort -Unique);" ^
 "$vivants=@(); $morts=@();" ^
 "foreach ($p in $ecoute) { $ok=$false;" ^
 "  try { Invoke-WebRequest -Uri ('http://127.0.0.1:' + $p + '/') -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop | Out-Null; $ok=$true }" ^
 "  catch { if ($_.Exception.Response) { $ok=$true } };" ^
 "  if ($ok) { $vivants += $p } else { $morts += $p } };" ^
 "Set-Content -Path '%F_ACTIFS%' -Value $vivants;" ^
 "Set-Content -Path '%F_ORPHELINS%' -Value $morts"
if not exist "%F_ACTIFS%"    type nul > "%F_ACTIFS%"
if not exist "%F_ORPHELINS%" type nul > "%F_ORPHELINS%"
goto :eof

REM --- Demarre un service s'il n'ecoute pas deja ----------------
REM  Arguments : "titre de fenetre"  port  dossier  "commande"
:lancer
set "TITRE=%~1"
set "PORT=%~2"
set "DOSSIER=%~3"
set "COMMANDE=%~4"

REM  !TITRE! et non %TITRE% : les titres contiennent le port entre parentheses
REM  ("MS7 - Auth (8087)"). Or %VAR% est substitue AU MOMENT OU cmd analyse le bloc
REM  if ( ... ) ; la parenthese fermante de (8087) refermerait donc le bloc trop tot,
REM  et le script echouerait sur un "- was unexpected at this time" incomprehensible.
REM  L'expansion differee substitue apres l'analyse, ce qui supprime le probleme.
findstr /X /C:"%PORT%" "%F_ORPHELINS%" >nul 2>&1
if not errorlevel 1 (
    echo    [ BLOQUE  ] !TITRE! - port occupe mais aucune reponse HTTP
    set /a NB_ORPHELINS+=1
    goto :eof
)
findstr /X /C:"%PORT%" "%F_ACTIFS%" >nul 2>&1
if not errorlevel 1 (
    echo    [ DEJA OK ] !TITRE!
    set /a NB_ACTIFS+=1
    goto :eof
)
echo    [ DEMARRE ] !TITRE!
start "!TITRE!" cmd /k "cd /d %ROOT%!DOSSIER! && !COMMANDE!"
set /a NB_LANCES+=1
goto :eof

REM --- Affiche l'etat de chaque port ---------------------------
:afficher_etat
call :etat_un 8087 "MS7  - Auth"
call :etat_un 8092 "MS13 - Parametres"
call :etat_un 8081 "MS1  - Bus"
call :etat_un 8082 "MS2  - Eleves"
call :etat_un 8083 "MS3  - Localisation"
call :etat_un 8084 "MS4  - Notifications"
call :etat_un 8090 "MS10 - Incidents"
call :etat_un 8085 "MS5  - Planification"
call :etat_un 8086 "MS6  - Clustering"
call :etat_un 8088 "MS12 - Prediction ETA"
call :etat_un 8089 "MS9  - Assistant LLM"
call :etat_un 8091 "MS11 - Analytique"
call :etat_un 8080 "MS8  - Gateway"
goto :eof

:etat_un
findstr /X /C:"%~1" "%F_ORPHELINS%" >nul 2>&1
if not errorlevel 1 ( echo    [ BLOQUE  ] %~2  ^(%~1^) & goto :eof )
findstr /X /C:"%~1" "%F_ACTIFS%" >nul 2>&1
if not errorlevel 1 ( echo    [ ACTIF   ] %~2  ^(%~1^) & goto :eof )
echo    [ ARRETE  ] %~2  ^(%~1^)
goto :eof

REM --- Arrete tous les services du projet ----------------------
REM  Deux passes, la seconde etant indispensable : tuer le processus
REM  qui ecoute ne suffit pas quand "uvicorn --reload" a laisse un
REM  enfant detenteur du socket. Sans elle, le port reste bloque.
:arreter_tout
echo   Arret des services sur les ports du projet...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ports=@(%PORTS%);" ^
 "$ids=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -ExpandProperty OwningProcess -Unique);" ^
 "foreach ($i in $ids) { try { Stop-Process -Id $i -Force -ErrorAction Stop } catch {} };" ^
 "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'multiprocessing-fork|uvicorn' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} };" ^
 "Start-Sleep -Seconds 3;" ^
 "$restants=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort });" ^
 "if ($restants) { Write-Host ('  ' + $restants.Count + ' port(s) encore occupe(s)') } else { Write-Host '  Tous les ports sont libres' }" 2>nul
goto :eof

:fin_courte
echo.
endlocal
exit /b 0

:fin
endlocal
