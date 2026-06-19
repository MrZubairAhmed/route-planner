#Requires -Version 5.1
<#
.SYNOPSIS
  Push Route Planner to GitHub and open Render Blueprint deploy.

.USAGE
  1. Complete GitHub login if prompted: gh auth login
  2. Run: .\deploy.ps1
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

$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Write-Host "Creating private GitHub repository: route-planner"
    gh repo create route-planner --private --source=. --remote=origin --push
} else {
    Write-Host "Pushing to $remote"
    git push -u origin main
}

$repoUrl = (gh repo view --json url -q .url)
Write-Host ""
Write-Host "Repository: $repoUrl"
Write-Host ""
Write-Host "Deploy on Render:"
Write-Host "  1. Open https://dashboard.render.com/blueprint/new"
Write-Host "  2. Connect GitHub and select the route-planner repo"
Write-Host "  3. Click Deploy Blueprint (uses render.yaml)"
Write-Host ""
Write-Host "Your permanent URL will be: https://route-planner.onrender.com (or similar)"
