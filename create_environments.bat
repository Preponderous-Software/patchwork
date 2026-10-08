REM Script to run `python main.py` a number of times with incrementing sizes

echo off

setlocal enabledelayedexpansion
set "script=main.py"
REM Check if a max size argument was provided, otherwise use default
if "%~1"=="" (
    echo No max size provided, using default value.
    set "max_size=100"
) else (
    echo Max size provided: %~1
    set "max_size=%~1"
)
REM Delete environments.json before starting
echo Deleting environments.json if it exists...
if exist environments.json (
    echo environments.json found, deleting...
    del environments.json
) else (
    echo environments.json not found, nothing to delete.
)

set "size_of_next_env=1"
set "increment=1"
set "output_file=output.txt"
set "python_executable=python"
set "log_file=log.txt"
set "error_log_file=error_log.txt"

:loop
if !size_of_next_env! leq !max_size! (
    @echo Starting environment with size !size_of_next_env!
    %python_executable% %script% !size_of_next_env! --exit-after-create >> %output_file% 2>> %error_log_file%
    if errorlevel 1 (
        echo Error occurred while running with size !size_of_next_env!.
    ) else (
        echo Environment created successfully with size !size_of_next_env!.
    )
    set /a size_of_next_env+=%increment%
    goto loop
)