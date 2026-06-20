@echo off
cd /d "%~dp0"
title Deploy to Netlify

echo.
echo  Deploy Route Planner to Netlify
echo  Site: https://stupendous-axolotl-ffbfb1.netlify.app/
echo.

where netlify >nul 2>&1
if errorlevel 1 (
  echo Installing Netlify CLI...
  npm install -g netlify-cli
)

echo Step 1: Log in to Netlify (browser will open)
netlify login

echo.
echo Step 2: Deploying docs folder...
netlify deploy --prod --dir=docs --site stupendous-axolotl-ffbfb1

echo.
echo Done. Open: https://stupendous-axolotl-ffbfb1.netlify.app/
pause
