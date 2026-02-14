@echo off
chcp 65001 >nul
echo [%date% %time%] daily_metrics started >> "C:\Users\Tenormusica\x-auto\logs\daily_metrics.log"
python -X utf8 "C:\Users\Tenormusica\x-auto\scripts\daily_metrics.py" --count 20 >> "C:\Users\Tenormusica\x-auto\logs\daily_metrics.log" 2>&1
echo [%date% %time%] daily_metrics finished >> "C:\Users\Tenormusica\x-auto\logs\daily_metrics.log"
