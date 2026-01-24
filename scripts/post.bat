@echo off
chcp 65001 > nul

REM X Auto Posting - Claude in Chrome Execution
REM Task Scheduler経由で実行される

REM 環境変数クリア（サブスク型でのヘッドレス実行に必要）
set ANTHROPIC_API_KEY=

REM Claude in Chromeで投稿生成・実行
"C:\Users\Tenormusica\.bun\bin\claude.exe" --chrome --dangerously-skip-permissions -p "You are an X (Twitter) auto-posting agent. Execute the following workflow:

1. READ the skill file: C:\Users\Tenormusica\x-auto\skills\generate-tweet\PROMPT.md
2. GENERATE a tweet following the rules in the skill file
3. REVIEW the tweet using: C:\Users\Tenormusica\x-auto\skills\review-tweet\PROMPT.md
4. If review passes, POST to X.com using: C:\Users\Tenormusica\x-auto\skills\post-tweet\PROMPT.md
5. Take a screenshot after posting and save the result

Account: @sena_09_04
Language: Japanese

Important:
- Follow all posting rules strictly
- Use Japanese language for the tweet
- Include a quote link if available
- Take screenshots at each step for verification"
