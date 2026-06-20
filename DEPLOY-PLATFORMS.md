# Deploy Route Planner — free platforms (no database)

This app **does not use PostgreSQL or any database**. Deploy the **Docker container only**.  
Do not add database add-ons on any platform.

Repo: **https://github.com/MrZubairAhmed/route-planner**

| Platform | Credit card | DB required? | RAM | Sleeps? | URL |
|----------|-------------|--------------|-----|---------|-----|
| **Northflank** | No (sandbox) | No | ~512MB | No | `*.code.run` |
| **Zeabur** | Free credits | No | varies | Maybe | `*.zeabur.app` |
| **Back4app** | No | No | 256MB | No | `*.back4app.io` |
| **Render** | Sometimes | No | 512MB | Yes (15 min) | `*.onrender.com` |
| **PC + tunnel** | No | No | Your PC | PC must run | `*.trycloudflare.com` |

---

## 1. Northflank (recommended — no DB popup)

1. Sign up: https://app.northflank.com (free Developer Sandbox)
2. **Create project** → **Add service** → **Combined service**
3. Connect **GitHub** → repo `route-planner`, branch `main`
4. **Build**: Dockerfile (root `/`)
5. **Port**: `8080` HTTP, publicly exposed
6. **Environment** (optional):
   - `PORT=8080`
   - `ASPNETCORE_URLS=http://0.0.0.0:8080`
7. **Do not** add any database addon
8. **Create service**

URL: `https://your-service-xxxxx.code.run`

Health check path: `/health`

---

## 2. Zeabur

1. Sign up: https://zeabur.com (GitHub login)
2. **New Project** → **Deploy from GitHub** → `route-planner`
3. Zeabur auto-detects `Dockerfile` (see `zbpack.json`)
4. Set **port 8080** when prompted
5. **Do not** add PostgreSQL/MySQL/Redis services
6. Deploy

URL: `https://your-service.zeabur.app`

Uses free monthly credits. No database needed.

---

## 3. Back4app Containers

1. Sign up: https://www.back4app.com
2. **New App** → **Containers as a Service**
3. Import GitHub repo `route-planner`
4. Branch: `main`, Dockerfile at root
5. **No environment variables required** (leave empty)
6. **Create App**

URL: shown in Back4app dashboard

**Note:** Free tier is only **256 MB RAM**. Fine for small Excel files; large files (1000+ rows) may fail. Upgrade or use Northflank/PC if needed.

---

## 4. Render

Uses `render.yaml` in this repo (already configured, no database).

1. Sign up: https://render.com
2. **New → Blueprint**
3. Connect GitHub → `route-planner`
4. **Deploy Blueprint**

URL: `https://route-planner-xxxx.onrender.com`

Free tier sleeps after 15 min idle (~30 sec wake). May ask for card on signup.

---

## 5. Your PC (instant, $0, no signup)

```powershell
start-free.cmd
```

Copy the `https://....trycloudflare.com` URL. Keep the window open.

Auto-start at Windows login:

```powershell
setup-windows-host.cmd
```

---

## Avoid these (for this app)

| Platform | Problem |
|----------|---------|
| SnapDeploy | Often forces PostgreSQL add-on |
| Railway | Trial credits, DB prompts |
| Koyeb | Pushes paid plans |

---

## Settings for all platforms

| Setting | Value |
|---------|-------|
| Builder | Dockerfile |
| Port | **8080** |
| Health check | `/health` |
| Database | **None** |
| Env vars | `PORT=8080`, `ASPNETCORE_URLS=http://0.0.0.0:8080` |

---

## Quick pick

- **Best free cloud (no DB hassle):** Northflank  
- **No signup at all:** `start-free.cmd`  
- **Smallest files only:** Back4app  
