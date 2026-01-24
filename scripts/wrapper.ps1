# X Auto Posting - Task Scheduler Wrapper
# Task Schedulerから呼び出されるPowerShellスクリプト

$ErrorActionPreference = "Stop"

# ログファイルパス
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = "C:\Users\Tenormusica\x-auto\logs\$timestamp.log"

# ログ関数
function Write-Log {
    param([string]$message)
    $logMessage = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $message"
    Add-Content -Path $logFile -Value $logMessage
    Write-Host $logMessage
}

Write-Log "X Auto Posting started"

try {
    # バッチファイル実行
    $batPath = "C:\Users\Tenormusica\x-auto\scripts\post.bat"
    
    Write-Log "Executing: $batPath"
    
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c $batPath" -Wait -NoNewWindow
    
    Write-Log "Execution completed successfully"
}
catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    exit 1
}

Write-Log "X Auto Posting finished"
