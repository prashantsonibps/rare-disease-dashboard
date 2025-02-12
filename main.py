from flask import Flask, render_template, request, jsonify
import pandas as pd

app = Flask(__name__)

# Path to the local Excel file
file_path = "NO DUPLICATES MasterFile (4).xlsx"

# Global variable to store fetched data
fetched_data = {}

def fetch_diseases():
    """
    Load data from all sheets into a dictionary.
    """
    global fetched_data
    sheets_to_load = [
        "Prevalence",
        "Pharma-Biotech Company Pipeline",
        "Approved Treatments",
        "Inheritance",
        "Publications",
        "Classification"
    ]

    for sheet in sheets_to_load:
        try:
            print(f"Loading sheet: {sheet}")
            data = pd.read_excel(file_path, sheet_name=sheet)
            data.fillna("No details available", inplace=True)  # Replace NaNs with placeholder
            fetched_data[sheet] = data
            print(f"Loaded {len(data)} rows from {sheet}.")
        except Exception as e:
            print(f"Error loading sheet '{sheet}': {e}")

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Render the search page for disease names.
    """
    global fetched_data
    if not fetched_data:  # Load data only once
        fetch_diseases()

    query = request.form.get("query", "").strip() if request.method == "POST" else ""
    if query:
        return search(query)

    return render_template("index.html")

@app.route("/search/<query>", methods=["GET"])
def search(query):
    """
    Render the blocks page for a specific disease query.
    """
    global fetched_data
    blocks = list(fetched_data.keys())  # Display blocks for all sheets
    return render_template("blocks.html", query=query, blocks=blocks)

@app.route("/fetch_data", methods=["POST"])
def fetch_data():
    """
    Fetch data for a specific sheet when a block is clicked.
    """
    global fetched_data
    sheet_name = request.json.get("sheet_name")
    query = request.json.get("query", "").strip()

    if sheet_name in fetched_data:
        data = fetched_data[sheet_name]
        
        # Case-insensitive filtering for the query in the entire row
        filtered = data[
            data.apply(
                lambda row: query.lower() in " ".join(str(value).lower() for value in row if pd.notna(value)),
                axis=1
            )
        ]
        
        # For specific sheets, drop columns with all empty or "No details available"
        if sheet_name in ["Pharma-Biotech Company Pipeline", "Classification"]:
            filtered = filtered.loc[:, ~filtered.isin(["No details available", None, ""]).all()]

        # Clean each row: remove keys with "No details available", None, or empty strings
        results = filtered.apply(
            lambda row: {key: value for key, value in row.items() if pd.notna(value) and value != "No details available"},
            axis=1
        ).tolist()

        print(f"Filtered {len(results)} results for query '{query}' in sheet '{sheet_name}'")
        return jsonify({"sheet": sheet_name, "data": results})
    else:
        print(f"Sheet '{sheet_name}' not found in fetched_data.")
        return jsonify({"error": "Sheet not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
