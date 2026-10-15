<#
.SYNOPSIS
    Reset the demo data's shared requirements (semester 13) to match v4.

.DESCRIPTION
    Demo step e (reassigning a teacher in a DRAFT version) also rewrites the
    semester-wide class_subject_requirements.required_teacher_id, so after a
    demo run the ARCHIVED v4 and the PUBLISHED v11 report H6 (required
    teacher mismatch). This script runs reset_demo_requirements.sql, which
    sets each mismatching requirement back to the teacher on v4's rows.

    Hard-coded ids (inside the .sql): semester_id = 13, schedule_version_id
    = 24 (v4). Only for this demo dataset -- NOT a general-purpose tool.

    Default is a DRY RUN: the .sql is followed by ROLLBACK, nothing is saved.
    Pass -Commit to append COMMIT instead.

    Runs psql inside the running "postgres" compose service; the database
    user and name come from that container's own environment variables
    (POSTGRES_USER / POSTGRES_DB), so .env is never read here.

    This file is ASCII-only on purpose: Windows PowerShell 5.1 reads a
    BOM-less .ps1 in the system code page and pipes strings to native
    programs as ASCII by default.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\reset_demo_requirements.ps1
    (dry run)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\reset_demo_requirements.ps1 -Commit
#>
param(
    [switch]$Commit
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$sqlPath = Join-Path $PSScriptRoot 'reset_demo_requirements.sql'
$sql = Get-Content -Raw -Encoding UTF8 -Path $sqlPath

if ($Commit) {
    $ending = 'COMMIT;'
} else {
    $ending = 'ROLLBACK;'
}
$psqlInput = "\set ON_ERROR_STOP on`n" + $sql + "`n" + $ending + "`n"

$previousOutputEncoding = $OutputEncoding
$previousConsoleEncoding = [Console]::OutputEncoding
Push-Location $repoRoot
try {
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $OutputEncoding = $utf8
    [Console]::OutputEncoding = $utf8

    $output = $psqlInput | docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB'
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-Output $_ }
} finally {
    Pop-Location
    $OutputEncoding = $previousOutputEncoding
    [Console]::OutputEncoding = $previousConsoleEncoding
}

if ($exitCode -ne 0) {
    Write-Output ''
    Write-Output "FAILED: psql exited with code $exitCode. Nothing was committed."
    exit $exitCode
}

$updateLine = $output | Where-Object { $_ -match '^UPDATE (\d+)$' } | Select-Object -First 1
if ($updateLine -match '^UPDATE (\d+)$') {
    $repaired = [int]$Matches[1]
} else {
    $repaired = -1
}

Write-Output ''
Write-Output '===== Summary ====='
if ($repaired -lt 0) {
    Write-Output 'Repaired requirements: unknown (no "UPDATE n" line found in psql output)'
} else {
    Write-Output "Repaired requirements: $repaired"
}
if ($Commit) {
    Write-Output 'Mode: COMMIT (changes saved)'
} else {
    Write-Output 'Mode: DRY RUN (rolled back, nothing saved; rerun with -Commit to save)'
}
