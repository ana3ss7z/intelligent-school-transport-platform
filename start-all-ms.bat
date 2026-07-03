@echo off
REM ============================================================
REM  Transport Scolaire Intelligent
REM  Lance TOUS les microservices disponibles, chacun dans son
REM  propre terminal. A executer depuis la racine du projet.
REM ============================================================
setlocal
set ROOT=%~dp0
REM --- Python (env conda "nlp", Python 3.11) : chemin direct, pas besoin d'activation ---
set NLP_PY=C:\Users\Anass\.conda\envs\nlp\python.exe

echo ============================================================
echo   Demarrage Transport Scolaire - tous les microservices
echo ============================================================
echo.

REM ---------- 1) Infrastructure (Docker + OSRM) ----------
echo [1/4] Infrastructure : PostgreSQL / Redis / RabbitMQ + OSRM...
docker-compose up -d
docker start osrm_meknes
echo.

REM ---------- 2) Microservices Java (Spring Boot) ----------
REM   Si "mvn" est introuvable, remplacer par "mvnw.cmd spring-boot:run".
echo [2/4] Services Java (MS7 d'abord)...
start "MS7 - Auth (8087)"           cmd /k "cd /d %ROOT%ms7-auth && mvn spring-boot:run"
timeout /t 5 >nul
start "MS1 - Bus (8081)"            cmd /k "cd /d %ROOT%ms1-bus && mvn spring-boot:run"
start "MS2 - Eleves (8082)"         cmd /k "cd /d %ROOT%ms2-eleves && mvn spring-boot:run"
start "MS3 - Localisation (8083)"   cmd /k "cd /d %ROOT%ms3-localisation && mvn spring-boot:run"
start "MS10 - Incidents (8090)"     cmd /k "cd /d %ROOT%ms10-incidents && mvn spring-boot:run"
start "MS4 - Notifications (8084)"  cmd /k "cd /d %ROOT%ms4-notifications && mvn spring-boot:run"
echo.

REM ---------- 3) Microservices Python (FastAPI, env nlp) ----------
echo [3/4] Services Python (clustering + prediction ETA)...
start "MS6 - Clustering (8086)"       cmd /k "cd /d %ROOT%ms6-clustering && %NLP_PY% -m uvicorn main:app --host 0.0.0.0 --port 8086 --reload"
start "MS12 - Prediction ETA (8088)"  cmd /k "cd /d %ROOT%ms12-prediction && %NLP_PY% -m uvicorn main:app --host 0.0.0.0 --port 8088 --reload"
start "MS11 - Analytique/Anomalies (8091)" cmd /k "cd /d %ROOT%ms11-analytique && %NLP_PY% -m uvicorn main:app --host 0.0.0.0 --port 8091 --reload"
echo.

REM ---------- 4) API Gateway (en DERNIER) ----------
echo [4/4] API Gateway (apres un court delai)...
timeout /t 10 >nul
start "MS8 - Gateway (8080)"        cmd /k "cd /d %ROOT%ms8-gateway && mvn spring-boot:run"

echo.
echo ============================================================
echo   Tous les services ont ete lances dans des terminaux
echo   separes. Fermez une fenetre pour arreter le service.
echo ============================================================
echo   Gateway   : http://localhost:8080
echo   Console   : html_tests\test-console.html
echo ============================================================
endlocal
