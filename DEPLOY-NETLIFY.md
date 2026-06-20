# Deploy to Netlify

The site is static (runs in the browser). Netlify serves the `docs/` folder.

## Option A — Connect GitHub (recommended, auto-deploy on push)

1. Go to [app.netlify.com](https://app.netlify.com)
2. **Add new site** → **Import an existing project**
3. Choose **GitHub** → authorize → select **MrZubairAhmed/route-planner**
4. Netlify reads `netlify.toml` automatically:
   - **Publish directory:** `docs`
   - **Build command:** (empty or echo — no build needed)
5. Click **Deploy site**

Your URL will be like `https://random-name.netlify.app`. You can rename it under **Site settings → Domain management**.

## Option B — Deploy from your PC (CLI)

```powershell
npm install -g netlify-cli
netlify login
cd C:\Users\zubair.ahmed\Projects\school-route-planner
netlify deploy --prod --dir=docs
```

## Notes

- **Free tier** — no credit card for static sites
- Same app as GitHub Pages: https://mrzubair.ahmed.github.io/route-planner/
- Excel processing runs in the browser (no server)
