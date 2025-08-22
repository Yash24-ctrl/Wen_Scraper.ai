import re
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Dict, Any, List

USER_AGENT = (
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"\+?\d[\d\s().-]{7,}\d")

SOCIAL_DOMAINS = {
	"facebook": ["facebook.com", "fb.me"],
	"twitter": ["twitter.com", "x.com"],
	"instagram": ["instagram.com"],
	"linkedin": ["linkedin.com"],
	"youtube": ["youtube.com", "youtu.be"],
	"github": ["github.com"],
}


def normalize_url(url: str) -> str:
	if not url:
		raise ValueError("Empty URL")
	parsed = urlparse(url)
	if not parsed.scheme:
		url = "https://" + url
	return url


def _http_get_with_retries(url: str, headers: dict, timeout: int = 20, retries: int = 3) -> requests.Response:
	last_exc = None
	for attempt in range(retries):
		try:
			resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
			resp.raise_for_status()
			return resp
		except Exception as exc:
			last_exc = exc
			time.sleep(0.8 * (attempt + 1))
	if last_exc:
		raise last_exc


def scrape_url(url: str) -> Dict[str, Any]:
	resp = _http_get_with_retries(url, headers=DEFAULT_HEADERS, timeout=25, retries=3)

	content_type = resp.headers.get('Content-Type', '')
	if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
		return {
			"url": url,
			"title": url,
			"meta": {},
			"emails": EMAIL_REGEX.findall(resp.text),
			"phones": PHONE_REGEX.findall(resp.text),
			"links": [],
			"text": resp.text[:50000],
			"tables": [],
		}

	soup = BeautifulSoup(resp.text, 'html.parser')

	title_tag = soup.find('title')
	title = title_tag.get_text(strip=True) if title_tag else url
	meta = {
		"description": _get_meta(soup, 'description'),
		"keywords": _get_meta(soup, 'keywords'),
	}

	for tag in soup(['script', 'style', 'noscript']):
		tag.decompose()
	text = soup.get_text(separator=' ', strip=True)
	text = re.sub(r"\s+", " ", text)
	if len(text) > 200000:
		text = text[:200000]

	emails = sorted(set(EMAIL_REGEX.findall(text)))
	phones = sorted(set(PHONE_REGEX.findall(text)))

	links = []
	for a in soup.find_all('a', href=True):
		href = a['href'].strip()
		absolute = urljoin(url, href)
		text_content = a.get_text(strip=True) or absolute
		links.append({"text": text_content, "href": absolute})

	social_links = {}
	for platform, domains in SOCIAL_DOMAINS.items():
		platform_links = [l["href"] for l in links if any(d in l["href"] for d in domains)]
		if platform_links:
			social_links[platform] = sorted(set(platform_links))

	tables = _extract_tables(soup, base_url=url)

	return {
		"url": url,
		"title": title,
		"meta": meta,
		"emails": emails,
		"phones": phones,
		"social_links": social_links,
		"links": links,
		"text": text,
		"tables": tables,
	}


def _get_meta(soup: BeautifulSoup, name: str) -> str:
	meta_tag = soup.find('meta', attrs={'name': name}) or soup.find('meta', attrs={'property': name})
	if not meta_tag:
		return ''
	return meta_tag.get('content', '').strip()


def _extract_tables(soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
	tables_data: List[Dict[str, Any]] = []
	for table in soup.find_all('table'):
		headers = []
		thead = table.find('thead')
		if thead:
			th_tags = thead.find_all('th')
			headers = [th.get_text(strip=True) or f"col_{i+1}" for i, th in enumerate(th_tags)]
		else:
			first_row = table.find('tr')
			if first_row:
				cells = first_row.find_all(['th', 'td'])
				headers = [c.get_text(strip=True) or f"col_{i+1}" for i, c in enumerate(cells)]

		rows_data = []
		for tr in table.find_all('tr'):
			cells = tr.find_all(['td'])
			if not cells:
				continue
			values = [c.get_text(strip=True) for c in cells]
			while len(values) < len(headers):
				values.append('')
			while len(values) > len(headers):
				headers.append(f"col_{len(headers)+1}")
			row = {headers[i]: values[i] for i in range(len(values))}
			rows_data.append(row)

		if rows_data:
			tables_data.append(rows_data)

	return tables_data