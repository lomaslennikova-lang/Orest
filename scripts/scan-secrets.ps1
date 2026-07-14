$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$localScanner = Join-Path $projectRoot ".venv\Scripts\detect-secrets.exe"

if (Test-Path $localScanner) {
    $scanner = $localScanner
} else {
    $scanner = "detect-secrets"
}

Push-Location $projectRoot
try {
    $gitFiles = @(
        git ls-files --cached --others --exclude-standard
    )
} finally {
    Pop-Location
}

$gitFiles = @($gitFiles | Where-Object { $_ -ne ".env.example" })

if ($gitFiles.Count -eq 0) {
    Write-Output "Secrets found: 0"
    exit 0
}

Push-Location $projectRoot
try {
    $scanJson = & $scanner scan $gitFiles
} finally {
    Pop-Location
}
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

$telegramTokenPattern = '\b\d{8,10}:[0-9A-Za-z_-]{35}\b'

foreach ($relativePath in $gitFiles) {
    $fullPath = Join-Path $projectRoot $relativePath

    if (-not (Test-Path $fullPath)) {
        continue
    }

    Get-Item $fullPath | Where-Object { -not $_.PSIsContainer } | ForEach-Object {
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
