# Route Planner

Upload an Excel file with location coordinates and get optimized visit routes with Google Maps navigation links.

## Excel format

| Column | Required |
|--------|----------|
| Latitude, Longitude | Yes |
| Start LAT, Start LNG | Recommended |
| Name | Recommended |
| District, Tehsil | Optional (auto batching) |

## Local development

```powershell
dotnet run --project src/RoutePlanner.Web -c Release --no-launch-profile --urls "http://0.0.0.0:8080"
```

Open http://localhost:8080

## Free deployment

See **[DEPLOY-PLATFORMS.md](DEPLOY-PLATFORMS.md)** for step-by-step guides.

| Platform | Card | Database | Best for |
|----------|------|----------|----------|
| **Northflank** | No | Not required | Free cloud hosting |
| **Zeabur** | Free credits | Not required | Docker from GitHub |
| **Back4app** | No | Not required | Small files (256MB RAM) |
| **Render** | Sometimes | Not required | Blueprint deploy |
| **start-free.cmd** | No | — | Instant test URL |

**Do not add PostgreSQL** on any platform — this app stores files on disk only.

## CLI

```powershell
dotnet run --project src/RoutePlanner.Cli -c Release -- -i "path\to\file.xlsx" -o output
```
