param(
    [string]$Worktree = (Join-Path (Split-Path -Parent $PSScriptRoot) '..\AEGIS--.worktrees\copilot-worktree-2026-05-29T02-23-08'),
    [string]$Branch = 'copilot/worktree-2026-05-29T02-23-08',
    [string]$Baseline = 'bd9450be'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Git {
    param(
        [string]$Repo,
        [string[]]$GitArgs,
        [switch]$AllowFailure
    )

    $output = & git -C $Repo @GitArgs 2>&1
    $exitCode = $LASTEXITCODE
    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "git -C $Repo $($GitArgs -join ' ') failed: $($output -join [Environment]::NewLine)"
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Lines    = @($output | ForEach-Object { $_.ToString().TrimEnd() } | Where-Object { $_ -ne '' })
        Text     = (($output | ForEach-Object { $_.ToString().TrimEnd() }) -join [Environment]::NewLine).Trim()
    }
}

function Get-UniqueInOrder {
    param([string[]]$Items)

    $seen = [System.Collections.Generic.HashSet[string]]::new()
    $ordered = [System.Collections.Generic.List[string]]::new()
    foreach ($item in $Items) {
        if ([string]::IsNullOrWhiteSpace($item)) {
            continue
        }
        if ($seen.Add($item)) {
            $ordered.Add($item)
        }
    }
    return $ordered.ToArray()
}

function Get-ChangedFilesFromDiff {
    param(
        [string]$Repo,
        [string[]]$DiffArgs = @()
    )

    $args = @('diff', '--name-only') + $DiffArgs
    return (Invoke-Git -Repo $Repo -GitArgs $args).Lines
}

function Get-Subsystem {
    param([string]$Path)

    switch -Regex ($Path) {
        '^sovereign-omega-v2/' { return 'sovereign-omega-v2' }
        '^aegis-cl-psi/' { return 'aegis-cl-psi' }
        '^aegis-runtime/' { return 'aegis-runtime' }
        '^\.github/' { return 'github-workflows' }
        '^(\.claude/|\.agent/)' { return 'repo-config' }
        '^CLAUDE\.md$' { return 'repo-config' }
        '^cockpit/' { return 'cockpit' }
        '^platform-picker/' { return 'platform-picker' }
        '^hook-generator/' { return 'hook-generator' }
        '^content-calendar/' { return 'content-calendar' }
        '^hub/' { return 'hub' }
        '^packages/shared/' { return 'packages-shared' }
        '^studio/' { return 'studio' }
        default { return 'other' }
    }
}

function Get-FirstRustModule {
    param(
        [string[]]$ChangedFiles,
        [string]$Prefix
    )

    foreach ($file in $ChangedFiles) {
        if (-not $file.StartsWith($Prefix) -or -not $file.EndsWith('.rs')) {
            continue
        }
        $parts = $file -split '[\\/]'
        if ($parts -notcontains 'src') {
            continue
        }
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($file)
        if ($stem -in @('lib', 'main', 'mod')) {
            continue
        }
        return $stem
    }
    return $null
}

function Get-SuggestedCommands {
    param(
        [string[]]$Subsystems,
        [string[]]$ChangedFiles
    )

    $commands = [System.Collections.Generic.List[string]]::new()

    if ($Subsystems -contains 'github-workflows' -or $Subsystems -contains 'repo-config') {
        $commands.Add('Review YAML/config changes for branch names, path references, and trigger conditions.')
    }

    if ($Subsystems -contains 'sovereign-omega-v2') {
        $commands.Add('cd sovereign-omega-v2 && npm run test -- test/unit/<affected>.test.ts')
        $commands.Add('cd sovereign-omega-v2 && npm run typecheck')
        $commands.Add('cd sovereign-omega-v2 && npm run build')
    }

    if ($Subsystems -contains 'aegis-cl-psi') {
        $module = Get-FirstRustModule -ChangedFiles $ChangedFiles -Prefix 'aegis-cl-psi/'
        if ($module) {
            $commands.Add("cd aegis-cl-psi && cargo test $module")
        } else {
            $commands.Add('cd aegis-cl-psi && cargo test')
        }
    }

    if ($Subsystems -contains 'aegis-runtime') {
        $module = Get-FirstRustModule -ChangedFiles $ChangedFiles -Prefix 'aegis-runtime/'
        if ($module) {
            $commands.Add("cd aegis-runtime && cargo test $module")
        } else {
            $commands.Add('cd aegis-runtime && cargo test')
        }
    }

    $frontendApps = @{
        'cockpit' = 'cockpit'
        'platform-picker' = 'platform-picker'
        'hook-generator' = 'hook-generator'
        'content-calendar' = 'content-calendar'
        'hub' = 'hub'
        'studio' = 'studio'
    }

    foreach ($entry in $frontendApps.GetEnumerator()) {
        if ($Subsystems -contains $entry.Key) {
            $commands.Add("cd $($entry.Value) && npm run build")
        }
    }

    if ($Subsystems -contains 'packages-shared') {
        $commands.Add('Review dependent apps touched by packages/shared and run their smallest relevant build/test command.')
    }

    if ($commands.Count -eq 0) {
        $commands.Add('Review changed files manually and choose the smallest subsystem-local validation command.')
    }

    return $commands.ToArray()
}

function Get-Findings {
    param(
        [string]$Repo,
        [string]$ExpectedBranch,
        [string]$Head,
        [string]$BaselineRef,
        [string[]]$Subsystems,
        [string[]]$ChangedFiles
    )

    $findings = [System.Collections.Generic.List[string]]::new()
    $currentBranch = (Invoke-Git -Repo $Repo -GitArgs @('rev-parse', '--abbrev-ref', 'HEAD')).Text
    if ($currentBranch -ne $ExpectedBranch) {
        $findings.Add("T0 | branch/worktree contamination risk | expected ``$ExpectedBranch``, found ``$currentBranch``")
    }

    if ($Head -eq $BaselineRef -and $ChangedFiles.Count -eq 0) {
        $findings.Add('T2 | no reviewable repo changes | Copilot worktree still matches baseline commit')
    }

    if ($Subsystems.Count -gt 1) {
        $findings.Add("T1 | multi-subsystem change set | touched subsystems: $($Subsystems -join ', ')")
    }

    if ($ChangedFiles | Where-Object { $_ -like '.github/*' }) {
        $findings.Add('T1 | workflow/config regression risk | validate triggers, paths, and branch names before broader tests')
    }

    $codeChanged = $ChangedFiles | Where-Object { $_ -match '\.(ts|tsx|js|jsx|rs|py)$' }
    $testsChanged = $ChangedFiles | Where-Object {
        $normalized = $_.ToLowerInvariant()
        $normalized.Contains('/test') -or
        $normalized.Contains('/tests') -or
        $normalized.Contains('.test.') -or
        $normalized.Contains('.spec.')
    }
    if ($codeChanged -and -not $testsChanged) {
        $findings.Add('T1 | missing-test risk | code changed without any obvious test file changes')
    }

    return $findings.ToArray()
}

function Write-Section {
    param(
        [string]$Title,
        [string[]]$Lines
    )

    Write-Output $Title
    if (-not $Lines -or $Lines.Count -eq 0) {
        Write-Output '(none)'
    } else {
        $Lines | ForEach-Object { Write-Output $_ }
    }
    Write-Output ''
}

$resolvedWorktree = [System.IO.Path]::GetFullPath($Worktree)
if (-not (Test-Path -LiteralPath $resolvedWorktree)) {
    Write-Error "Worktree does not exist: $resolvedWorktree"
    exit 2
}

$status = (Invoke-Git -Repo $resolvedWorktree -GitArgs @('status', '--short', '--branch')).Text
$head = (Invoke-Git -Repo $resolvedWorktree -GitArgs @('rev-parse', '--short=8', 'HEAD')).Text
$logLines = @((Invoke-Git -Repo $resolvedWorktree -GitArgs @('log', '--oneline', '--decorate', '-n', '10')).Lines)
$committedFiles = @(Get-ChangedFilesFromDiff -Repo $resolvedWorktree -DiffArgs @("$Baseline..HEAD"))
$workingTreeFiles = @(Get-ChangedFilesFromDiff -Repo $resolvedWorktree)
$stagedFiles = @(Get-ChangedFilesFromDiff -Repo $resolvedWorktree -DiffArgs @('--cached'))
$allChangedFiles = @(Get-UniqueInOrder -Items ($committedFiles + $stagedFiles + $workingTreeFiles))
$subsystems = @(Get-UniqueInOrder -Items ($allChangedFiles | ForEach-Object { Get-Subsystem -Path $_ }))
$snapshotPath = Join-Path $resolvedWorktree '.memory\session_snapshot.md'
$snapshotPresent = Test-Path -LiteralPath $snapshotPath
$triggered = ($allChangedFiles.Count -gt 0) -or ($head -ne $Baseline) -or $snapshotPresent
$findings = @(Get-Findings -Repo $resolvedWorktree -ExpectedBranch $Branch -Head $head -BaselineRef $Baseline -Subsystems $subsystems -ChangedFiles $allChangedFiles)
$suggestedCommands = @(Get-SuggestedCommands -Subsystems $subsystems -ChangedFiles $allChangedFiles)

Write-Output 'Copilot Worktree Review'
Write-Output "worktree: $resolvedWorktree"
Write-Output "branch:   $Branch"
Write-Output "baseline: $Baseline"
Write-Output "head:     $head"
Write-Output "trigger:  $(if ($triggered) { 'YES' } else { 'NO' })"
Write-Output "snapshot: $(if ($snapshotPresent) { 'present' } else { 'missing' })"
Write-Output ''

Write-Section -Title 'Status' -Lines @($(if ($status) { $status } else { '(clean)' }))
Write-Section -Title 'Recent commits' -Lines $logLines

if ($triggered) {
    Write-Section -Title 'Changed files' -Lines $allChangedFiles

    $diffSummary = [System.Collections.Generic.List[string]]::new()
    $committedStat = (Invoke-Git -Repo $resolvedWorktree -GitArgs @('diff', '--stat', "$Baseline..HEAD") -AllowFailure).Text
    if ($committedStat) {
        $diffSummary.Add($committedStat)
    }
    $workingTreeStat = (Invoke-Git -Repo $resolvedWorktree -GitArgs @('diff', '--stat') -AllowFailure).Text
    if ($workingTreeStat) {
        $diffSummary.Add($workingTreeStat)
    }
    Write-Section -Title 'Changed file summary' -Lines $diffSummary.ToArray()
} else {
    Write-Section -Title 'Changed files' -Lines @()
}

Write-Section -Title 'Subsystems' -Lines $subsystems
Write-Section -Title 'Findings' -Lines $findings
Write-Section -Title 'Suggested validation' -Lines $suggestedCommands

Write-Output 'Integration guidance'
if ($triggered -and $head -ne $Baseline) {
    $commitRange = @((Invoke-Git -Repo $resolvedWorktree -GitArgs @('rev-list', '--reverse', "$Baseline..HEAD")).Lines)
    if ($commitRange.Count -gt 0) {
        Write-Output 'Prefer cherry-pick if the commit list below is clean and reviewable:'
        $commitRange | ForEach-Object { Write-Output $_ }
    } else {
        Write-Output 'No committed delta beyond baseline; review uncommitted work before any integration decision.'
    }
} else {
    Write-Output 'No integration action yet.'
}

exit $(if ($triggered) { 1 } else { 0 })
