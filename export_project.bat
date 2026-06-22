@echo off
setlocal enabledelayedexpansion

set OUTPUT=important_project_dump.txt

echo =============================== > %OUTPUT%
echo IMPORTANT PROJECT EXPORT >> %OUTPUT%
echo =============================== >> %OUTPUT%
echo. >> %OUTPUT%

set ROOT=%cd%

echo Root: %ROOT% >> %OUTPUT%
echo. >> %OUTPUT%

REM Loop all files
for /r %%F in (*) do (

    set FILE=%%F

    REM Skip folders
    echo %%F | findstr /i "\\target\\ \\node_modules\\ \\.git\\ \\.mvn\\" >nul
    if errorlevel 1 (

        REM Only important extensions
        echo %%F | findstr /i ".java .xml .properties .yml .yaml" >nul
        if not errorlevel 1 (

            echo ===================================== >> %OUTPUT%
            echo FILE: %%F >> %OUTPUT%
            echo ===================================== >> %OUTPUT%
            echo. >> %OUTPUT%

            type "%%F" >> %OUTPUT% 2>nul

            echo. >> %OUTPUT%
            echo. >> %OUTPUT%
        )
    )
)

echo DONE!
echo Output saved to: %OUTPUT%
pause