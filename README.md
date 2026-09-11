# eBay price scraper

The scraper can run locally on a schedule and upload complete JSON output sets
to Google Cloud Storage.

## Local scheduled runner

Authenticate once with Google Application Default Credentials:

```powershell
gcloud auth application-default login
```

Install dependencies and Playwright, then start an hourly local loop:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python local_runner.py
```

Use `Ctrl+C` to stop it. To run one scrape only:

```powershell
python local_runner.py --once
```

The runner executes `main.py`, checks that all five expected non-empty JSON
outputs exist, and then uploads them under one UTC timestamp in
`gs://server-413715-iphone-scraper/data/`. A failed scrape is not uploaded.
