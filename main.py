from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
from fpdf import FPDF
import os
import re
import unicodedata

app = Flask(__name__)

# Path to the local Excel file
file_path = "/Users/prashantsoni/Downloads/NO_DUPLICATES _7thmarch.xlsx"

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
        "Classification",
        "Inheritance",
        "Genetic Mutation",
        "Approved Treatments",
        "Biopharma Pipeline",
        "Publications"
    ]

    for sheet in sheets_to_load:
        try:
            print(f"Loading sheet: {sheet}")
            data = pd.read_excel(file_path, sheet_name=sheet)
            data.fillna("No details available", inplace=True)
            print(f"Columns in {sheet}: {list(data.columns)}")  # Debug column names
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
    """Render the search page for a specific disease query."""
    global fetched_data
    sheets = list(fetched_data.keys())
    return render_template("blocks.html", query=query, sheets=sheets)

@app.route("/search_suggestions")
def search_suggestions():
    """Fetch disease name suggestions as the user types."""
    global fetched_data
    query = request.args.get("query", "").strip().lower()

    if not query:
        return jsonify([])  # Return empty if no query

    all_diseases = set()
    for sheet in fetched_data.values():
        if 'Disease' in sheet.columns:
            all_diseases.update(sheet['Disease'].dropna().unique())

    # Filter diseases that match the query
    matching_diseases = sorted([d for d in all_diseases if query in str(d).lower()])

    return jsonify(matching_diseases[:10])  # Return only top 10 matches for performance

@app.route("/get_diseases")
def get_diseases():
    """Fetch disease names based on the requested type (alphabetical or prevalence order)."""
    global fetched_data
    disease_type = request.args.get("type")
    reverse_order = request.args.get("reverse", "false").lower() == "true"  # Detect reverse order request

    diseases = []

    if disease_type == "alphabetical":
        diseases = sorted(fetched_data.get("Prevalence", pd.DataFrame()).get("Disease", []).dropna().unique())
    elif disease_type == "prevalence":
        diseases = fetched_data.get("Prevalence", pd.DataFrame()).get("Disease", []).dropna().tolist()

    # Reverse the list if requested
    if reverse_order:
        diseases.reverse()

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
        elif sheet_name == "Classification":
            # Handle Classification sheet: match disease in the first column
            results = []
            first_column = data.columns[0]  # First column is the disease column
            filtered = data[data[first_column].str.lower() == query]
            for index, row in filtered.iterrows():
                # Include the queried disease name explicitly
                result_entry = {"Disease": query.capitalize()}
                # Collect column names with available data, excluding the first column
                for col in data.columns[1:]:  # Skip the first column
                    if pd.notna(row[col]) and row[col] != "No details available":
                        result_entry[col] = row[col]
                results.append(result_entry)
            if not results:
                return jsonify({"error": "No matching records found in Classification."}), 404
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
        elif sheet_name == "Classification":
            filtered = pd.DataFrame(columns=data.columns)  # Initialize empty DataFrame
            first_column = data.columns[0]  # First column is the disease column
            filtered = data[data[first_column].str.lower() == query.lower()]
        else:
            continue  # Skip sheets without "Disease" column except Classification

        if not filtered.empty:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(200, 10, f"\n{sheet_name}:", ln=True)
            pdf.set_font("Arial", "", 10)

            if sheet_name == "Classification":
                for _, row in filtered.iterrows():
                    # Exclude first column and only include column names with available data
                    categories = [key for key, value in row.items() 
                                 if key != data.columns[0] 
                                 and pd.notna(value) 
                                 and value != "No details available"]
                    pdf.multi_cell(0, 6, f"Disease: {query}")
                    pdf.multi_cell(0, 6, f"Categories: {', '.join(categories) if categories else 'N/A'}")
            else:
                for _, row in filtered.iterrows():
                    for col, val in row.items():
                        if pd.isna(val) or val == "No details available":
                            continue

                        val = clean_text(str(val))
                        val = format_text_for_pdf(val)

                        # Remove "Unnamed" column names but keep their data
                        if sheet_name == "Biopharma Pipeline" and col.startswith("Unnamed"):
                            if is_valid_url(val):
                                pdf.set_text_color(0, 0, 255)  # Set link color
                                pdf.cell(0, 6, val, ln=True, link=val)
                                pdf.set_text_color(0, 0, 0)
                            else:
                                pdf.multi_cell(0, 6, val)
                        elif sheet_name == "Publications" and is_valid_url(val):
                            pdf.set_text_color(0, 0, 255)
                            pdf.cell(0, 6, val, ln=True, link=val)
                            pdf.set_text_color(0, 0, 0)
                        elif is_valid_url(val):
                            pdf.set_text_color(0, 0, 255)
                            pdf.cell(0, 6, f"{col}: ", ln=False)
                            pdf.cell(0, 6, val, ln=True, link=val)
                            pdf.set_text_color(0, 0, 0)
                        else:
                            pdf.multi_cell(0, 6, f"{col}: {val}")

        if sheet_name == "Prevalence":
            pdf.multi_cell(0, 8, "NOTE: Without specification, published figures are worldwide || An asterisk * indicates European data || BP indicates birth prevalence.")

    pdf_file = f"{query}.pdf"
    pdf.output(pdf_file, "F")

    return send_file(pdf_file, as_attachment=True)

@app.route("/get_disease_count")
def get_disease_count():
    """Return the total number of unique diseases from the Prevalence sheet."""
    global fetched_data
    if "Prevalence" in fetched_data and "Disease" in fetched_data["Prevalence"].columns:  # Changed to "Disease"
        count = fetched_data["Prevalence"]["Disease"].dropna().nunique()  # Changed to "Disease"
        return jsonify({"count": count})
    return jsonify({"count": 0, "error": "Prevalence sheet or Disease column not found"}), 404

if __name__ == "__main__":  
    app.run(debug=True)
