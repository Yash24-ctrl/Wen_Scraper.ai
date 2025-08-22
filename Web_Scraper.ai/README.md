# Web_Scraper.ai — By Yash Kansara

A simple, login-protected web scraper built with Flask. Paste any URL and extract contact info, links, text, and HTML tables. Download results as JSON or CSV (ZIP).

## Features
- Login + Register (SQLite)
- URL paste to scrape any public webpage
- Extracts: emails, phone numbers, page metadata, links, social links, text, and tables
- Downloads: JSON and CSV bundle (contacts, links, and tables per file)

## Quickstart (Local)
1. Prerequisites: Python 3.10+ and pip
2. Clone or copy this folder, then:
```bash
cd Web_Scraper.ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="change-me"
python app.py
```
3. Open http://127.0.0.1:5000

## Docker
```bash
# Build image
docker build -t web_scraper_ai .
# Run container
docker run -p 5000:5000 -e SECRET_KEY="change-me" web_scraper_ai
```

## Production (Gunicorn)
```bash
pip install -r requirements.txt
export SECRET_KEY="your-strong-secret"
gunicorn wsgi:app --bind 0.0.0.0:5000 --workers 2
```

## Environment
- SECRET_KEY: Flask session secret (required for auth sessions)

## Notes
- Only crawl public pages you have the right to access; respect robots.txt and site terms.
- Heavy or dynamic sites may require specialized renderers; this app uses requests + BeautifulSoup.