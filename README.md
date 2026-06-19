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

## Deploy to Render (recommended)

1. Push this repo to GitHub.
2. Sign in at [render.com](https://render.com).
3. **New → Blueprint** and connect the GitHub repo (Render reads `render.yaml`).
4. Deploy. Your app will be available at `https://route-planner-xxxx.onrender.com`.

The included `Dockerfile` builds the ASP.NET Core web app for Linux containers.

## CLI

```powershell
dotnet run --project src/RoutePlanner.Cli -c Release -- -i "path\to\file.xlsx" -o output
```
