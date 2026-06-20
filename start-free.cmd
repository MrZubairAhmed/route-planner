@echo off
cd /d "%~dp0"
title Route Planner - Free Public URL

echo.
echo  Route Planner - starting local server + public URL...
echo.

where dotnet >nul 2>&1
if errorlevel 1 (
  echo ERROR: .NET SDK not found. Install from https://dotnet.microsoft.com/download
  pause
  exit /b 1
)

if not exist "tools\cloudflared.exe" (
  echo ERROR: tools\cloudflared.exe not found.
  pause
  exit /b 1
)

echo [1/2] Building app...
dotnet build src\RoutePlanner.Web\RoutePlanner.Web.csproj -c Release -v q
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo [2/2] Starting web app on port 8080...
start "RoutePlanner-Web" /MIN cmd /c "cd /d %~dp0 && set ASPNETCORE_ENVIRONMENT=Production && dotnet run --project src\RoutePlanner.Web -c Release --no-launch-profile --urls http://0.0.0.0:8080"

timeout /t 6 /nobreak >nul

echo.
echo Starting Cloudflare tunnel (free public URL)...
echo Copy the https://....trycloudflare.com link when it appears below.
echo Keep this window open. Press Ctrl+C to stop.
echo.

tools\cloudflared.exe tunnel --url http://127.0.0.1:8080
