from flask import Flask, render_template, request
import pandas as pd

app = Flask(__name__)

# Path to the local Excel file
file_path = "NO DUPLICATES MasterFile.xlsx"

def fetch_diseases():
    try:
        sheets_to_load = [
            "CI Naveen",
            "Approved Treatments  Dandan",
            "Inheritance Dandan",
            "Publications Naveen",
            "Classification"
        ]

        combined_data = []

        for sheet in sheets_to_load:
            data = pd.read_excel(file_path, sheet_name=sheet)
            
            if sheet == "CI Naveen":
                data = data[["Disease","Estimated prevalence\n(/100,000)" ,"CI"]].dropna()
                data["Source"] = sheet
            elif sheet == "Approved Treatments  Dandan":
                data = data[["Disease", "FDA Approved Drugs with Disease Indication(Generic name)", "Links for information"]].dropna()
                data["Source"] = sheet
            elif sheet == "Inheritance Dandan":
                data = data[["Disease", "Inheritance"]].dropna()
                data["Source"] = sheet
            elif sheet == "Publications Naveen":
                data = data[["Disease", "Number of Approximate Publications in Last Five Years (Searching in Title/Abstract on Pubmed)", "Link for the Publications"]].dropna()
                data["Source"] = sheet
            elif sheet == "Classification":
                data = data[["Disease "]].dropna()
                data["Detail"] = "Classification Information"
                data["Source"] = sheet
                data.rename(columns={"Disease ": "Disease"}, inplace=True)

            # Ensure all values are strings
            data = data.astype(str)

            combined_data.extend(data.to_dict(orient="records"))

        return combined_data
    except Exception as e:
        print(f"Error fetching Excel data: {e}")
        return []

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query", "").strip()
    diseases = fetch_diseases()
    filtered_diseases = []

    if query:
        filtered_diseases = [
            d for d in diseases 
            if query.lower() in d["Disease"].lower() or any(query.lower() in str(v).lower() for v in d.values())
        ]

    return render_template("search.html", diseases=filtered_diseases, query=query)

if __name__ == "__main__":
    app.run(debug=True)
