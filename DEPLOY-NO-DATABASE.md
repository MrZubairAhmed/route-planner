# SnapDeploy / Railway — skip the database

**Route Planner does NOT use PostgreSQL or any database.**  
Files are stored on disk only. If the deploy screen forces a database, you added it by mistake.

## Fix on SnapDeploy

1. **Cancel** the current deploy
2. Go to **Dashboard** → delete this container/project
3. Create a **new container**:
   - **Deploy from GitHub** → `MrZubairAhmed/route-planner`
   - Branch: `main`
   - Port: **8080**
   - **Do not** open Add-ons
   - **Do not** add PostgreSQL, MySQL, or Redis
   - **Do not** add `DATABASE_URL` in environment variables
4. Click **Deploy** (container only)

If you still see "Service Dependencies Detected → PostgreSQL", you linked a database in a previous step. Remove it under **Settings → Dependencies** or start a fresh container.

## Easier option (no cloud signup)

Double-click:

```
start-free.cmd
```

Copy the `https://....trycloudflare.com` URL. Works immediately, $0, no database needed.

Keep the window open while sharing the link.
