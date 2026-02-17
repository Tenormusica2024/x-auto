@echo off
chcp 65001 >nul
echo [%date% %time%] content_evaluator started >> "C:\Users\Tenormusica\x-auto\logs\content_evaluator.log"
python -X utf8 "C:\Users\Tenormusica\x-auto\scripts\content_evaluator.py" >> "C:\Users\Tenormusica\x-auto\logs\content_evaluator.log" 2>&1
echo [%date% %time%] content_evaluator finished >> "C:\Users\Tenormusica\x-auto\logs\content_evaluator.log"
