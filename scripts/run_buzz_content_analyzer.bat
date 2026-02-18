@echo off
chcp 65001 >nul
echo [%date% %time%] buzz_content_analyzer started >> "C:\Users\Tenormusica\x-auto\logs\buzz_content_analyzer.log"
python -X utf8 "C:\Users\Tenormusica\x-auto\scripts\buzz_content_analyzer.py" >> "C:\Users\Tenormusica\x-auto\logs\buzz_content_analyzer.log" 2>&1
echo [%date% %time%] buzz_content_analyzer finished >> "C:\Users\Tenormusica\x-auto\logs\buzz_content_analyzer.log"
