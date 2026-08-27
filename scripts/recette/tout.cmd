@echo off
REM ---------------------------------------------------------------------------
REM Recette finale — enchainement complet.
REM
REM   tout.cmd offline   suites qui ne demandent PAS la stack
REM   tout.cmd live      tout ce qui interroge la stack (elle doit tourner)
REM   tout.cmd           les deux, dans l'ordre
REM
REM Le detail des resultats attendus est dans docs/RECETTE_FINALE.md.
REM ---------------------------------------------------------------------------
setlocal EnableDelayedExpansion
set RACINE=%~dp0..\..
set RES=%~dp0resultats
set PY=C:\Users\Anass\.conda\envs\nlp\python.exe
set PYTHONIOENCODING=utf-8
if not exist "%RES%" mkdir "%RES%"

set MODE=%1
if "%MODE%"=="" set MODE=tout

if /I "%MODE%"=="live" goto :live

REM ═══════════════════════ HORS LIGNE ═══════════════════════
echo.
echo ############ PHASE 1 — suites hors ligne ############
echo.

echo --- pytest MS6 (attendu 75)  [depuis ms6-clustering/, PAS la racine : cf. defaut n.14]
pushd "%RACINE%\ms6-clustering" && "%PY%" -m pytest tests -q & popd

echo.
echo --- pytest MS9 (attendu 36)
pushd "%RACINE%\ms9-llm" && "%PY%" -m pytest tests -q & popd

echo.
echo --- MS9 rapport garde SQL (attendu 29 cas, 0 ecart)
"%PY%" "%RACINE%\ms9-llm\eval\rapport_sql_guard.py"

echo.
echo --- mvn test  (attendu 18 : MS4 17 + MS10 1 ; 5 modules ont skipTests=true, defaut n.6)
pushd "%RACINE%" && call mvnw.cmd test -q & popd

echo.
echo --- flutter chauffeur (attendu : 93 tests ; analyze remonte 5 erreurs, defaut n.15)
pushd "%RACINE%\frontend\chauffeur-mobile" && call flutter analyze & call flutter test & popd

echo.
echo --- flutter parent (attendu : 38 tests ; analyze remonte 3 infos)
pushd "%RACINE%\frontend\parent-mobile" && call flutter analyze & call flutter test & popd

echo.
echo --- web-admin : typecheck + lint
pushd "%RACINE%\frontend\web-admin" && call bun run build & call bun run lint & popd

if /I "%MODE%"=="offline" goto :fin

REM ═══════════════════════ STACK VIVANTE ═══════════════════════
:live
echo.
echo ############ PHASES 2 a 8 — contre la stack vivante ############
echo.

echo --- Phase 2 : contrats HTTP et RBAC (attendu 67/67)
"%PY%" "%~dp0contrats.py"

echo.
echo --- Phase 2bis : scenarios ACTEUR a ACTEUR (attendu 39/39)
echo     (ajoute --sans-llm pour sauter les 6 questions envoyees a MS9)
"%PY%" "%~dp0scenarios.py"

echo.
echo --- Phase 2ter : justesse des 5 briques IA (attendu 35/35)
echo     (contraintes metier, coherence des grandeurs, determinisme, NL2SQL exact)
"%PY%" "%~dp0ia.py"

echo.
echo --- Phase 3 : Newman (attendu 88/88)
call "%~dp0newman.cmd"

echo.
echo --- Phase 4 : e2e integration (attendu 11/12 — G1 depend du contexte meteo, defaut n.12)
pushd "%RACINE%" && "%PY%" e2e_integration_test.py & popd

echo.
echo --- Phase 5 : chaine temps reel (attendu 10/12)
"%PY%" "%~dp0temps_reel.py"

echo.
echo --- Phase 7 : MS13 configuration a chaud et MS4 canal push (attendu 13/13)
"%PY%" "%~dp0config_et_push.py"

echo.
echo --- Phase 8 : balayage des 27 routes web-admin dans Chrome (attendu 42/42)
echo     (web-admin doit tourner sur :5173)
pushd "%RACINE%" && node "scripts\recette\balayage_front.mjs" & popd

echo.
echo --- Phase 8bis : les interfaces affichent-elles les BONNES valeurs (attendu 17/17)
echo     (compare le texte rendu a l'ecran avec la verite lue dans l'API)
pushd "%RACINE%" && node "scripts\recette\donnees_front.mjs" & popd

:fin
echo.
echo ############ Termine ############
echo Resultats bruts : %RES%
echo Rapport redige  : %RACINE%\docs\RECETTE_FINALE.md
endlocal
