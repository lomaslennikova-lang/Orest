$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$localScanner = Join-Path $projectRoot ".venv\Scripts\detect-secrets.exe"

if (Test-Path $localScanner) {
    $scanner = $localScanner
} else {
    $scanner = "detect-secrets"
}

$scanJson = & $scanner scan --all-files --exclude-files '(\.env$|^\.venv[\\/]|^venv[\\/])'
$scan = $scanJson | ConvertFrom-Json
$findings = @()

foreach ($file in @($scan.results.PSObject.Properties)) {
    foreach ($finding in @($file.Value)) {
        $findings += [PSCustomObject]@{
            Filename = $finding.filename
            LineNumber = $finding.line_number
            Type = $finding.type
        }
    }
}

$excludedPathPattern = '(^|[\\/])(\.git|\.venv|venv|__pycache__)([\\/]|$)'
$telegramTokenPattern = '\b\d{8,10}:[0-9A-Za-z_-]{35}\b'
$projectRootPrefix = $projectRoot.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar

Get-ChildItem $projectRoot -Recurse -File |
    Where-Object {
        $relativePath = $_.FullName.Substring($projectRootPrefix.Length)
        $relativePath -ne ".env" -and $relativePath -notmatch $excludedPathPattern
    } |
    ForEach-Object {
        $relativePath = $_.FullName.Substring($projectRootPrefix.Length)
        $lineNumber = 0

        Get-Content $_.FullName -ErrorAction SilentlyContinue | ForEach-Object {
            $lineNumber += 1
            if ($_ -match $telegramTokenPattern) {
                $findings += [PSCustomObject]@{
                    Filename = $relativePath
                    LineNumber = $lineNumber
                    Type = "Telegram Bot Token"
                }
            }
        }
    }

$findings = @($findings | Sort-Object Filename, LineNumber, Type -Unique)

if ($findings.Count -eq 0) {
    Write-Output "Secrets found: 0"
    exit 0
}

Write-Output "Secrets found: $($findings.Count)"
foreach ($finding in $findings) {
    Write-Output ("{0}:{1} - {2}" -f $finding.Filename, $finding.LineNumber, $finding.Type)
}

exit 1
