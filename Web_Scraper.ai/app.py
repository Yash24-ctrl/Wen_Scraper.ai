import os
import io
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, Response
from werkzeug.security import generate_password_hash, check_password_hash

from scraper import scrape_url


DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'users.db')
SESSION_SECRET = os.environ.get('SECRET_KEY', 'dev-secret-change-me')


def create_app() -> Flask:
	app = Flask(__name__, template_folder='templates', static_folder='static')
	app.secret_key = SESSION_SECRET

	ensure_db()

	@app.route('/')
	def index():
		if 'user_id' in session:
			return redirect(url_for('scrape'))
		return redirect(url_for('login'))

	@app.route('/login', methods=['GET', 'POST'])
	def login():
		if request.method == 'POST':
			form_type = request.form.get('form_type', 'login')
			username = request.form.get('username', '').strip()
			password = request.form.get('password', '')

			if form_type == 'register':
				if not username or not password:
					flash('Username and password are required.', 'error')
					return redirect(url_for('login'))
				try:
					create_user(username=username, password=password)
					flash('Registration successful. Please log in.', 'success')
				except sqlite3.IntegrityError:
					flash('Username already exists. Choose another.', 'error')
				return redirect(url_for('login'))

			# login flow
			user = get_user_by_username(username)
			if user and check_password_hash(user['password_hash'], password):
				session['user_id'] = user['id']
				session['username'] = user['username']
				return redirect(url_for('scrape'))
			flash('Invalid username or password.', 'error')
			return redirect(url_for('login'))

		# GET
		return render_template('login.html', app_name='Web_Scraper.ai', author_name='Yash Kansara')

	@app.route('/logout')
	def logout():
		session.clear()
		flash('Logged out.', 'info')
		return redirect(url_for('login'))

	@app.route('/scrape', methods=['GET', 'POST'])
	def scrape():
		if 'user_id' not in session:
			flash('Please log in first.', 'error')
			return redirect(url_for('login'))

		if request.method == 'POST':
			url = request.form.get('url', '').strip()
			if not url:
				flash('Please paste a valid URL.', 'error')
				return redirect(url_for('scrape'))
			try:
				results = scrape_url(url)
				results['scraped_at'] = datetime.utcnow().isoformat() + 'Z'
				session['last_results'] = results
				return redirect(url_for('results'))
			except Exception as exc:
				flash(f'Error while scraping: {exc}', 'error')
				return redirect(url_for('scrape'))

		return render_template('url_input.html', app_name='Web_Scraper.ai', author_name='Yash Kansara')

	@app.route('/results', methods=['GET'])
	def results():
		if 'user_id' not in session:
			return redirect(url_for('login'))
		results = session.get('last_results')
		if not results:
			flash('No results yet. Paste a URL to scrape.', 'info')
			return redirect(url_for('scrape'))
		# Limit text preview for UI
		text_preview = (results.get('text') or '')
		if len(text_preview) > 3000:
			text_preview = text_preview[:3000] + '…'
		return render_template(
			'results.html',
			app_name='Web_Scraper.ai',
			author_name='Yash Kansara',
			results=results,
			text_preview=text_preview
		)

	@app.route('/download/json')
	def download_json():
		if 'user_id' not in session:
			return redirect(url_for('login'))
		results = session.get('last_results')
		if not results:
			flash('No results to download.', 'error')
			return redirect(url_for('scrape'))
		payload = json.dumps(results, ensure_ascii=False, indent=2)
		return Response(
			payload,
			mimetype='application/json',
			headers={
				'Content-Disposition': 'attachment; filename="scrape_results.json"'
			}
		)

	@app.route('/download/csv')
	def download_csv():
		if 'user_id' not in session:
			return redirect(url_for('login'))
		results = session.get('last_results')
		if not results:
			flash('No results to download.', 'error')
			return redirect(url_for('scrape'))

		buffer = io.BytesIO()
		with ZipFile(buffer, 'w', ZIP_DEFLATED) as zipf:
			# Contacts
			contacts_csv = build_contacts_csv(results)
			zipf.writestr('contacts.csv', contacts_csv)

			# Links
			links_csv = build_links_csv(results)
			zipf.writestr('links.csv', links_csv)

			# Tables: each as its own CSV
			tables = results.get('tables') or []
			for index, table in enumerate(tables, start=1):
				csv_content = build_table_csv(table)
				zipf.writestr(f'table_{index}.csv', csv_content)

			# Full text as a text file for reference
			text_content = (results.get('text') or '').strip()
			zipf.writestr('full_text.txt', text_content)

		buffer.seek(0)
		return send_file(
			buffer,
			as_attachment=True,
			download_name='scrape_results_csv_bundle.zip',
			mimetype='application/zip'
		)

	return app


def ensure_db() -> None:
	with closing(sqlite3.connect(DATABASE_PATH)) as conn:
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS users (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				username TEXT UNIQUE NOT NULL,
				password_hash TEXT NOT NULL,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			);
			"""
		)
		conn.commit()


def create_user(username: str, password: str) -> None:
	password_hash = generate_password_hash(password)
	with closing(sqlite3.connect(DATABASE_PATH)) as conn:
		conn.execute(
			"INSERT INTO users (username, password_hash) VALUES (?, ?)",
			(username, password_hash),
		)
		conn.commit()


def get_user_by_username(username: str):
	with closing(sqlite3.connect(DATABASE_PATH)) as conn:
		conn.row_factory = sqlite3.Row
		row = conn.execute(
			"SELECT id, username, password_hash FROM users WHERE username = ?",
			(username,),
		).fetchone()
		return dict(row) if row else None


def build_contacts_csv(results: dict) -> str:
	lines = ["type,value"]
	emails = results.get('emails') or []
	phones = results.get('phones') or []
	for email in emails:
		lines.append(f"email,{email}")
	for phone in phones:
		lines.append(f"phone,{phone}")
	return "\n".join(lines) + "\n"


def build_links_csv(results: dict) -> str:
	lines = ["text,url"]
	for link in results.get('links') or []:
		text = (link.get('text') or '').replace('\n', ' ').replace(',', ' ').strip()
		url = link.get('href') or ''
		lines.append(f"{text},{url}")
	return "\n".join(lines) + "\n"


def build_table_csv(table_rows: list) -> str:
	# table_rows is expected to be list[dict]
	if not table_rows:
		return "\n"
	# Collect headers
	headers = []
	for row in table_rows:
		for key in row.keys():
			if key not in headers:
				headers.append(key)
	lines = [",".join(headers)]
	for row in table_rows:
		values = []
		for header in headers:
			value = row.get(header)
			if value is None:
				values.append("")
			else:
				cell = str(value).replace('\n', ' ').replace(',', ' ')
				values.append(cell)
		lines.append(",".join(values))
	return "\n".join(lines) + "\n"


if __name__ == '__main__':
	app = create_app()
	app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)