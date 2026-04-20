@echo off
title ESRGAN Worker - Kurumi RTX3080

echo === ESRGAN Worker Starting ===
echo Queue: Z:\JAV\esrgan_queue
echo Done:  Z:\JAV\esrgan_done
echo.

:: Update to latest
cd /d C:\tools\jav-pipeline
git pull

:: Run worker
python esrgan_worker_win.py

pause
