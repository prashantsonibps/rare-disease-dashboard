from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
from fpdf import FPDF
import os
import re
import unicodedata

app = Flask(__name__)

# Path to the local Excel file
file_path = "/Users/prashantsoni/Downloads/NO_DUPLICATES_16thFeb.xlsx"

# Global variable to store fetched data
fetched_data = {}

def clean_text(text):
    """Remove hidden Unicode characters and normalize text."""
    if isinstance(text, str):
        text = text.replace("\u200b", "")  # Remove zero-width spaces
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Replace non-ASCII characters with space
        text = unicodedata.normalize('NFKD', text)  # Normalize text
    return text

def format_text_for_pdf(text):
    """Format text by inserting new lines if there are more than 10 consecutive spaces."""
    return re.sub(r' {10,}', '\n', text)

def is_valid_url(text):
    """Check if a given text is a valid URL."""
    return re.match(r'^https?:\/\/\S+', text) is not None

def fetch_diseases():
    """Load data from all sheets into a dictionary."""
    global fetched_data
    sheets_to_load = [
        "Prevalence",
        "Biopharma Pipeline Drug",
        "Approved Treatments",
        "Inheritance",
        "Publications",
        "Classification"
    ]

    for sheet in sheets_to_load:
        try:
            print(f"Loading sheet: {sheet}")
            data = pd.read_excel(file_path, sheet_name=sheet)
            data.fillna("No details available", inplace=True)
            fetched_data[sheet] = data
            print(f"Loaded {len(data)} rows from {sheet}.")
        except Exception as e:
            print(f"Error loading sheet '{sheet}': {e}")

@app.route("/", methods=["GET", "POST"])
def index():
    """Render the search page for disease names."""
    global fetched_data
    if not fetched_data:
        fetch_diseases()

    all_diseases = set()
    for sheet in fetched_data.values():
        if 'Disease' in sheet.columns:
            all_diseases.update(sheet['Disease'].dropna().unique())
    all_diseases = sorted(all_diseases)

    query = request.form.get("query", "").strip() if request.method == "POST" else ""
    if query:
        return search(query)

    return render_template("index.html", diseases=all_diseases)

@app.route("/search/<query>", methods=["GET"])
def search(query):
    """Render the blocks page for a specific disease query."""
    global fetched_data
    sheets = list(fetched_data.keys())
    return render_template("blocks.html", query=query, sheets=sheets)

@app.route("/get_diseases")
def get_diseases():
    """Fetch disease names based on the requested type (alphabetical or prevalence order)."""
    global fetched_data
    disease_type = request.args.get("type")
    diseases = []

    if disease_type == "alphabetical":
        diseases = sorted(fetched_data.get("Prevalence", pd.DataFrame()).get("Disease", []).dropna().unique())
    elif disease_type == "prevalence":
        diseases = fetched_data.get("Prevalence", pd.DataFrame()).get("Disease", []).dropna().tolist()
    
    return jsonify({"diseases": diseases})

@app.route("/fetch_data", methods=["POST"])
def fetch_data():
    """Fetch data for a specific sheet when clicked."""
    global fetched_data
    sheet_name = request.json.get("sheet_name")
    query = request.json.get("query", "").strip().lower()

    if sheet_name in fetched_data:
        data = fetched_data[sheet_name]

        if "Disease" in data.columns:
            filtered = data[data["Disease"].str.lower() == query]
            results = filtered.to_dict(orient="records")

            if not results:
                return jsonify({"error": "No matching records found."}), 404
            
            # Append the note for Prevalence block
            if sheet_name == "Prevalence":
                results.append({"NOTE": "Without specification, published figures are worldwide | An asterisk * indicates European data | BP indicates birth prevalence."})

            return jsonify({"sheet": sheet_name, "data": results})
        else:
            return jsonify({"error": "No 'Disease' column found in sheet"}), 404
    else:
        return jsonify({"error": "Sheet not found"}), 404

@app.route("/download/<query>", methods=["GET"])
def download_pdf(query):
    """Generate and download a PDF report for the searched disease."""
    global fetched_data
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"Disease Report: {query}", ln=True, align="C")

    for sheet_name, data in fetched_data.items():
        if "Disease" in data.columns:
            filtered = data[data["Disease"].str.lower() == query.lower()]
            if not filtered.empty:
                pdf.set_font("Arial", "B", 12)
                pdf.cell(200, 10, f"\n{sheet_name}:", ln=True)
                pdf.set_font("Arial", "", 10)

                if sheet_name == "Classification":
                    for _, row in filtered.iterrows():
                        categories = [key for key, value in row.items() if key != "Disease" and value and value != "No details available"]
                        pdf.multi_cell(0, 6, f"Disease: {row['Disease']}")
                        pdf.multi_cell(0, 6, f"Categories: {', '.join(categories)}")
                else:
                    for _, row in filtered.iterrows():
                        for col, val in row.items():
                            if pd.isna(val) or val == "No details available":
                                continue

                            val = clean_text(str(val))
                            val = format_text_for_pdf(val)

                            # Remove "Unnamed" column names but keep their data
                            if sheet_name == "Biopharma Pipeline Drug" and col.startswith("Unnamed"):
                                if is_valid_url(val):
                                    pdf.set_text_color(0, 0, 255)  # Set link color
                                    pdf.cell(0, 6, val, ln=True, link=val)  # Clickable hyperlink
                                    pdf.set_text_color(0, 0, 0)  # Reset color
                                else:
                                    pdf.multi_cell(0, 6, val)  # Normal text
                            elif sheet_name == "Prevalence":
                                pdf.cell(0, 6, f"{col}: {val}", ln=True)  # Use cell() for Prevalence
                            elif sheet_name == "Publications" and is_valid_url(val):
                                pdf.set_text_color(0, 0, 255)  # Set link color
                                pdf.cell(0, 6, val, ln=True, link=val)  # Clickable hyperlink in Publications
                                pdf.set_text_color(0, 0, 0)  # Reset color
                            elif is_valid_url(val):
                                pdf.set_text_color(0, 0, 255)  # Set link color
                                pdf.cell(0, 6, f"{col}: ", ln=False)  # Add column name
                                pdf.cell(0, 6, val, ln=True, link=val)  # Clickable hyperlink
                                pdf.set_text_color(0, 0, 0)  # Reset color
                            else:
                                pdf.multi_cell(0, 6, f"{col}: {val}")  # Keep multi-cell for other sections
                
                if sheet_name == "Prevalence":
                    pdf.multi_cell(0, 8, "NOTE: Without specification, published figures are worldwide || An asterisk * indicates European data || BP indicates Birth Prevalence.")
    
    pdf_file = f"{query}.pdf"
    pdf.output(pdf_file, "F")

    return send_file(pdf_file, as_attachment=True)

if __name__ == "__main__":  
    app.run(debug=True)
