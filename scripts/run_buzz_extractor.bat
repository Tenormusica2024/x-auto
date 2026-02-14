@echo off
chcp 65001 >nul 2>&1
cd /d "C:\Users\Tenormusica\x-auto\scripts"
python -X utf8 buzz_tweet_extractor.py >> "C:\Users\Tenormusica\x-auto\logs\buzz_extractor_%date:~0,4%%date:~5,2%%date:~8,2%.log" 2>&1
