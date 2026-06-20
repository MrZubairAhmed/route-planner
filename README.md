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

See **[DEPLOY-FREE.md](DEPLOY-FREE.md)** for all options.

| Method | Cost | Credit card | Always on |
|--------|------|-------------|-----------|
| `start-free.cmd` | Free | No | Only while PC runs |
| [Koyeb](https://www.koyeb.com) Hobby | Free | **No** | Yes |
| Oracle Cloud Free VM | Free | Verification only | Yes |

**Recommended:** Koyeb — sign up with GitHub, deploy from repo using the included `Dockerfile`, port **8080**.

After GitHub login:

```powershell
deploy.cmd
```

Then follow the Koyeb steps in `DEPLOY-FREE.md`.

## CLI

```powershell
dotnet run --project src/RoutePlanner.Cli -c Release -- -i "path\to\file.xlsx" -o output
```
