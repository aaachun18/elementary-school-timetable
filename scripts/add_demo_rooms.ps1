<#
.SYNOPSIS
    Give every lesson of the demo semester (13) its class's homeroom.

.DESCRIPTION
    The scheduler never assigns a room to a requirement without a required
    room type, so the demo versions (v4, v5, v8, v11) have no rooms and the
    timetable's "by room" view is empty. This script runs add_demo_rooms.sql,
    which creates one homeroom per [SEED] class that has none, sets it as
    the class's homeroom, and fills every empty room_id of semester 13's
    schedule rows with the class's homeroom. It aborts if that would put
    two lessons in one room at the same time slot. Safe to run again: a
    second run changes nothing.

    Hard-coded (inside the .sql): semester_id = 13 and classes named
    "[SEED] ...". Only for this demo dataset -- NOT a general-purpose tool.

    Default is a DRY RUN: the .sql is followed by ROLLBACK, nothing is saved.
    (Even a dry run advances the rooms id sequence; ids are never reused,
    which is harmless.) Pass -Commit to append COMMIT instead.

    Runs psql inside the running "postgres" compose service; the database
    user and name come from that container's own environment variables
    (POSTGRES_USER / POSTGRES_DB), so .env is never read here.

    This file is ASCII-only on purpose: Windows PowerShell 5.1 reads a
    BOM-less .ps1 in the system code page and pipes strings to native
    programs as ASCII by default.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\add_demo_rooms.ps1
    (dry run)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\add_demo_rooms.ps1 -Commit
#>
param(
    [switch]$Commit
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$sqlPath = Join-Path $PSScriptRoot 'add_demo_rooms.sql'
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

# psql prints, in order: "INSERT 0 n" (rooms created), "UPDATE n" (classes
# given a homeroom), "UPDATE n" (schedule rows given a room).
$insertLine = $output | Where-Object { $_ -match '^INSERT 0 (\d+)$' } | Select-Object -First 1
$updateLines = @($output | Where-Object { $_ -match '^UPDATE (\d+)$' })

function Get-Count([string]$line, [string]$pattern) {
    if ($line -match $pattern) {
        return [string][int]$Matches[1]
    }
    return 'unknown'
}

$roomsCreated = Get-Count $insertLine '^INSERT 0 (\d+)$'
$classesUpdated = 'unknown'
$rowsFilled = 'unknown'
if ($updateLines.Count -ge 2) {
    $classesUpdated = Get-Count $updateLines[0] '^UPDATE (\d+)$'
    $rowsFilled = Get-Count $updateLines[1] '^UPDATE (\d+)$'
}

Write-Output ''
Write-Output '===== Summary ====='
Write-Output "Rooms created: $roomsCreated"
Write-Output "Classes given a homeroom: $classesUpdated"
Write-Output "Schedule rows given a room: $rowsFilled"
if ($Commit) {
    Write-Output 'Mode: COMMIT (changes saved)'
} else {
    Write-Output 'Mode: DRY RUN (rolled back, nothing saved; rerun with -Commit to save)'
}
