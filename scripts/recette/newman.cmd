@echo off
REM ---------------------------------------------------------------------------
REM Recette finale — Phase 3 : la collection Postman (88 assertions).
REM
REM Il n'existait aucun lanceur pour ce "88/88" : le chiffre etait cite partout
REM mais rejouable par personne. C'est desormais une commande.
REM
REM Prerequis : newman installe (npm i -g newman) + MS7/MS1/MS2/MS8 demarres.
REM ---------------------------------------------------------------------------
setlocal
set RACINE=%~dp0..\..
set RES=%~dp0resultats
if not exist "%RES%" mkdir "%RES%"

echo.
echo === Recette Phase 3 — collection Postman v4 ===
echo.

newman run "%RACINE%\scripts\postman\transport-scolaire_postman_collection_v4.json" ^
  -e "%RACINE%\scripts\postman\transport-scolaire_postman_environment_v2.json" ^
  -r cli,json --reporter-json-export "%RES%\newman.json"

set CODE=%ERRORLEVEL%
echo.
if %CODE%==0 (
  echo Resultat : toutes les assertions passent.
) else (
  echo Resultat : au moins une assertion echoue ^(code %CODE%^).
  echo Reference 26/08/2026 : 87/88 — l'assertion 13 "Eleves - Access without token fails"
  echo echoue car GET /api/eleves est devenu permitAll sur MS2. Voir docs/RECETTE_FINALE.md
  echo defaut CRITIQUE n. 2.
)
echo Rapport JSON : %RES%\newman.json
exit /b %CODE%
