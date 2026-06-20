#Requires -Version 5.1
<#
.SYNOPSIS
  Push Route Planner to GitHub and open Render Blueprint deploy.

.USAGE
  1. Complete GitHub login if prompted: gh auth login
  2. Run: deploy.cmd
     Or: powershell -ExecutionPolicy Bypass -File .\deploy.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is required. Install: winget install GitHub.cli"
}

gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitHub login required. Complete the browser/device flow, then re-run this script."
    gh auth login --hostname github.com --git-protocol https --web
    gh auth status
}

$remote = $null
try {
    $remote = git remote get-url origin 2>$null
    if ($LASTEXITCODE -ne 0) { $remote = $null }
} catch {
    $remote = $null
}

$branch = (git branch --show-current)
if (-not $branch) { $branch = "main" }

$dirty = git status --porcelain
if ($dirty) {
    Write-Host "Committing local changes..."
    git add -A
    git commit -m "Prepare for deployment"
}

if (-not $remote) {
    Write-Host "Creating private GitHub repository: route-planner"
    gh repo create route-planner --private --source=. --remote=origin --push
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Repo may already exist. Linking origin and pushing..."
        $user = gh api user -q .login
        git remote add origin "https://github.com/$user/route-planner.git"
        git push -u origin $branch
    }
} else {
    Write-Host "Pushing to $remote"
    git push -u origin $branch
}

$repoUrl = (gh repo view --json url -q .url)
Write-Host ""
Write-Host "Repository: $repoUrl"
Write-Host ""
Write-Host "FREE deployment (no credit card): Koyeb"
Write-Host "  1. Sign up: https://www.koyeb.com (Continue with GitHub, Hobby plan)"
Write-Host "  2. Create Web Service -> GitHub -> route-planner repo"
Write-Host "  3. Builder: Dockerfile | Port: 8080 | Instance: Free/Eco"
Write-Host "  4. Deploy -> URL: https://YOUR-APP.koyeb.app"
Write-Host ""
Write-Host "Instant test URL (PC must stay on): run start-free.cmd"
Write-Host ""
Write-Host "Full guide: DEPLOY-FREE.md"
