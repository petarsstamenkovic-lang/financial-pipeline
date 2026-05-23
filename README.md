# Financial Intelligence Pipeline

Daily financial email + interactive dashboard. Runs on GitHub Actions (free), sends to Gmail at 13:00 CET.

---

## Setup (15 minutes)

### 1. Create GitHub repo

1. Create a new **public** repo on GitHub (e.g. `financial-pipeline`)
2. Push this entire folder to it:
   ```bash
   git init
   git add .
   git commit -m "init"
   git remote add origin https://github.com/YOUR_USERNAME/financial-pipeline.git
   git push -u origin main
   ```

---

### 2. Enable GitHub Pages

- Go to repo → **Settings** → **Pages**
- Source: **Deploy from a branch** → branch: `main` → folder: `/docs`
- Save. Your dashboard will be at:  
  `https://YOUR_USERNAME.github.io/financial-pipeline/`

---

### 3. Get a NewsAPI key (free)

- Register at [newsapi.org](https://newsapi.org) → free tier (100 req/day)
- Copy your API key

---

### 4. Create Gmail App Password

Google no longer allows plain Gmail passwords for SMTP. You need an App Password:

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** (required)
3. Search for **App passwords** → create one for "Mail"
4. Copy the 16-character password (no spaces)

---

### 5. Set GitHub Secrets

Go to repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret name         | Value                                              |
|---------------------|----------------------------------------------------|
| `GMAIL_USER`        | `petar.s.stamenkovic@gmail.com`                    |
| `GMAIL_APP_PASSWORD`| your 16-char App Password                         |
| `RECIPIENT_EMAIL`   | `petar.s.stamenkovic@gmail.com`                    |
| `NEWS_API_KEY`      | your NewsAPI key                                   |
| `DASHBOARD_URL`     | `https://YOUR_USERNAME.github.io/financial-pipeline/` |

---

### 6. Fix CET vs CEST timing

The workflow has two cron lines. Europe/Belgrade is:
- **CET (UTC+1)**: Oct–Mar → use `0 12 * * 1-5`  
- **CEST (UTC+2)**: Mar–Oct → use `0 11 * * 1-5`

Edit `.github/workflows/daily_run.yml` to keep only the appropriate one for the current season, or add logic to run both and deduplicate.

---

### 7. Test manually

Go to repo → **Actions** → **Daily Financial Pipeline** → **Run workflow** → click **Run workflow**

Check:
- ✅ Action completes without errors
- ✅ `docs/data/latest.json` appears in the repo
- ✅ Email arrives in your inbox
- ✅ Dashboard loads at your GitHub Pages URL

---

## Architecture

```
GitHub Actions (cron 12:00 UTC)
        │
        ├─ pipeline/fetch_data.py
        │     ├─ yfinance: indices, FX, commodities, large-cap, sectors
        │     ├─ feedparser: Reuters, FT, ECB, NBS, Blic, N1, Novosti...
        │     └─ NewsAPI: macro + Serbia queries
        │     └─ writes docs/data/latest.json + daily_YYYY-MM-DD.json
        │
        ├─ pipeline/send_email.py
        │     └─ builds HTML email → Gmail SMTP → your inbox
        │
        └─ git push → docs/data/ → GitHub Pages reads JSON
                                          │
                                    docs/index.html (dashboard)
                                    ├─ Today: markets + news
                                    ├─ Weekly: aggregated + chart
                                    ├─ Monthly: S&P 500 chart + stories
                                    └─ All News: date picker
```

## Data Sources

| Source | Data | Cost |
|--------|------|------|
| yfinance | All market prices | Free |
| feedparser (RSS) | Reuters, FT, ECB, NBS, Blic, N1, Novosti, Telegraf, Danas, Euronews Serbia | Free |
| NewsAPI | English macro + Serbia news | Free (100 req/day) |
| Investing.com RSS | Economic calendar events | Free |

## Adding Your Own Watchlist

Edit `TICKERS` in `pipeline/fetch_data.py` to add/remove any tickers.  
Edit `RSS_FEEDS` to add/remove news sources.
