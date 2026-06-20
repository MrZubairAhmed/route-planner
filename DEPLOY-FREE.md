# Free deployment options

Render has a free tier, but it often asks for a credit card. These options are **genuinely free** for this app.

## Option A — Instant test URL (no signup, PC must stay on)

Double-click or run:

```powershell
start-free.cmd
```

This starts the app locally and prints a public URL like `https://xxxx.trycloudflare.com`. Share that link to test. The URL stops working when you close the window or shut down your PC.

---

## Option B — Koyeb (recommended permanent free hosting)

**Hobby plan: free, no credit card**, 512 MB RAM, always on.

### Steps

1. **Push code to GitHub** (public or private repo):
   ```powershell
   gh auth login
   deploy.cmd
   ```
   Or create a repo manually on github.com and push.

2. **Sign up at [koyeb.com](https://www.koyeb.com)** — use **Continue with GitHub** (Hobby plan, no card).

3. **Create Web Service**:
   - Deployment: **GitHub** → select your `route-planner` repo
   - Branch: `main`
   - Builder: **Dockerfile**
   - Port: **8080**
   - Instance: **Free / Eco** (512 MB)
   - Region: Washington DC or Frankfurt (free regions)

4. Click **Deploy**. Your permanent URL will be:
   `https://<your-app-name>.koyeb.app`

### Koyeb settings (if asked)

| Setting | Value |
|---------|-------|
| Exposed port | 8080 |
| Health check path | `/health` |
| Environment | `PORT=8080`, `ASPNETCORE_URLS=http://0.0.0.0:8080` |

---

## Option C — Oracle Cloud Always Free (most power, more setup)

Free forever: up to **4 ARM CPUs + 24 GB RAM** VM. Requires Oracle account (card for verification only, free tier won't charge if you stay within limits).

1. Create an **Ampere A1** VM on [Oracle Cloud](https://www.oracle.com/cloud/free/)
2. Install Docker on the VM
3. Clone repo and run:
   ```bash
   docker build -t route-planner .
   docker run -d -p 80:8080 -e PORT=8080 route-planner
   ```
4. Open port 8080 in Oracle security list / firewall

---

## Which to choose?

| Need | Use |
|------|-----|
| Test now, share link for a few hours | `start-free.cmd` |
| Permanent URL, no credit card | **Koyeb** |
| Large Excel files (10k+ rows), always on | **Oracle Cloud** free VM |

---

## Notes for free tiers

- **512 MB RAM** (Koyeb) is enough for small/medium Excel files. Very large files may need Oracle or a paid plan.
- Free tiers may have **cold starts** or **bandwidth limits** — fine for testing and moderate use.
