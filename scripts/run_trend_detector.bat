@echo off
chcp 65001 >nul
echo [%date% %time%] trend_detector started >> "C:\Users\Tenormusica\x-auto\logs\trend_detector.log"
python -X utf8 "C:\Users\Tenormusica\x-auto\scripts\trend_detector.py" >> "C:\Users\Tenormusica\x-auto\logs\trend_detector.log" 2>&1
echo [%date% %time%] trend_detector finished >> "C:\Users\Tenormusica\x-auto\logs\trend_detector.log"
