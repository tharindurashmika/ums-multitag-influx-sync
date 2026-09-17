@echo off
title UMS Multi-Tag & Influx Repopulation Studio
echo ===================================================================
echo   Starting UMS Multi-Tag & Influx Repopulation Studio
echo ===================================================================
echo.
echo Opening Web UI on http://127.0.0.1:8080 ...
start http://127.0.0.1:8080
python ui_server.py
pause
