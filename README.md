# Route Planner

Upload an Excel file with location coordinates and get optimized visit routes with Google Maps navigation links.

## Excel format

| Column | Required |
|--------|----------|
| Latitude, Longitude | Yes |
| Start LAT, Start LNG | Recommended |
| Name | Recommended |
| District, Tehsil | Optional (auto batching) |

## Free hosting on GitHub Pages

The app runs **entirely in your browser** (no server, no database). Deployed from the `docs/` folder.

**Live URL:** https://mrzubairahmed.github.io/route-planner/

To enable (one-time, after push):
1. GitHub repo → **Settings** → **Pages**
2. Source: **GitHub Actions**

Pushes to `main` auto-deploy via `.github/workflows/pages.yml`.

## Local development (.NET server version)

```powershell
dotnet run --project src/RoutePlanner.Web -c Release --no-launch-profile --urls "http://0.0.0.0:8080"
```

Open http://localhost:8080

## Free deployment ($0, no payment)

See **[DEPLOY-FREE.md](DEPLOY-FREE.md)**.

| Method | Payment | Credit card | PC must stay on |
|--------|---------|-------------|-----------------|
| `start-free.cmd` | None | No | Yes |
| `setup-windows-host.cmd` | None | No | Yes (auto-starts at login) |
| [SnapDeploy](https://snapdeploy.dev) | None | No | No (sleeps when idle) |

Cloud platforms like Koyeb and Render often show paid plans. For zero cost, use **your PC + Cloudflare tunnel** or **SnapDeploy free tier**.

## CLI

```powershell
dotnet run --project src/RoutePlanner.Cli -c Release -- -i "path\to\file.xlsx" -o output
```
