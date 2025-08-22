from flask import Flask, render_template, request, send_file, redirect, url_for, flash
import os
import pandas as pd
from fpdf import FPDF
from scraper import scrape_website

app = Flask(__name__)
app.secret_key = "supersecretkey"

SAVE_FOLDER = "scraped_files"
os.makedirs(SAVE_FOLDER, exist_ok=True)

def dataframe_to_pdf(df, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    col_width = pdf.w / max(len(df.columns), 1) - 1

    # Header
    for col in df.columns:
        pdf.cell(col_width, 10, str(col), 1, 0, 'C')
    pdf.ln()

    # Rows
    for _, row in df.iterrows():
        for col in df.columns:
            text = str(row[col]).encode('latin-1', errors='replace').decode('latin-1')
            pdf.cell(col_width, 10, text, 1, 0, 'C')
        pdf.ln()
    pdf.output(filename)

def save_dataframe(df, filename_base):
    df_csv = os.path.join(SAVE_FOLDER, f"{filename_base}.csv")
    df_excel = os.path.join(SAVE_FOLDER, f"{filename_base}.xlsx")
    df_json = os.path.join(SAVE_FOLDER, f"{filename_base}.json")
    df_pdf = os.path.join(SAVE_FOLDER, f"{filename_base}.pdf")

    df.to_csv(df_csv, index=False, encoding='utf-8-sig')
    df.to_excel(df_excel, index=False)
    df.to_json(df_json, orient="records", indent=4)
    dataframe_to_pdf(df, df_pdf)

    return {"csv": df_csv, "excel": df_excel, "json": df_json, "pdf": df_pdf}

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        if not url:
            flash("Please enter a URL!", "error")
            return redirect(url_for("index"))

        scraped_data = scrape_website(url)
        dataframes = {}

        # Company Info
        company_info = {
            "Company Name": [url],
            "Email": [", ".join(scraped_data.get("emails", [])) or "N/A"],
            "Phone": [", ".join(scraped_data.get("phones", [])) or "N/A"]
        }
        df_company = pd.DataFrame(company_info)
        files_company = save_dataframe(df_company, "company_info")
        dataframes["Company Info"] = {"columns": df_company.columns.tolist(), "rows": df_company.values.tolist(), "files": files_company}

        # Text Data
        if scraped_data.get("text"):
            df_text = pd.DataFrame(scraped_data["text"], columns=["Text"])
            files_text = save_dataframe(df_text, "text_data")
            dataframes["Text Data"] = {"columns": df_text.columns.tolist(), "rows": df_text.values.tolist(), "files": files_text}

        # Links
        if scraped_data.get("links"):
            df_links = pd.DataFrame(scraped_data["links"], columns=["Link Text", "URL"])
            files_links = save_dataframe(df_links, "links")
            dataframes["Links"] = {"columns": df_links.columns.tolist(), "rows": df_links.values.tolist(), "files": files_links}

        # Forms
        if scraped_data.get("forms"):
            df_forms = pd.DataFrame(scraped_data["forms"], columns=["Form Action", "Input Name", "Input Type"])
            files_forms = save_dataframe(df_forms, "forms")
            dataframes["Forms"] = {"columns": df_forms.columns.tolist(), "rows": df_forms.values.tolist(), "files": files_forms}

        # Tables
        for i, table in enumerate(scraped_data.get("tables", []), start=1):
            df_table = pd.DataFrame(table)
            files_table = save_dataframe(df_table, f"table_{i}")
            dataframes[f"Table {i}"] = {"columns": df_table.columns.tolist(), "rows": df_table.values.tolist(), "files": files_table}

        return render_template("results.html", dataframes=dataframes)

    return render_template("index.html")

@app.route("/download/<filetype>/<path:filepath>")
def download(filetype, filepath):
    return send_file(filepath, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
