import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 1. SETUP FLASK ---
# We set static_url_path='' so it doesn't force /static/ prefix
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# --- 2. CONFIGURATION ---
# ⚠️ REPLACE THIS WITH YOUR REAL KEY
API_KEY = "pRAoUVvdllyd6skGURjLGBTuUf7jlKeBiN7Az3rQ" 
BASE_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# --- 3. SESSION SETUP (Speed Optimization) ---
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# --- 4. CATEGORY MAPPER ---
def map_usda_category(usda_cat, name):
    cat = str(usda_cat).lower()
    name_lower = str(name).lower()
    
    # Junk Food / Snacks
    if "candy" in cat or "chocolate" in name_lower or "reeses" in name_lower or "snack" in cat: return "sweet"
    if "cookie" in name_lower or "pastry" in cat or "croissant" in name_lower or "cake" in name_lower: return "sweet"
    if "soda" in name_lower or "beverage" in cat or "drink" in name_lower: return "sweet"
    if "chips" in name_lower or "fries" in name_lower or "doritos" in name_lower: return "veg" 

    # Standard Groups
    if "fruit" in cat: return "fruit"
    if "vegetable" in cat or "pod" in cat: return "veg"
    if "beef" in cat or "pork" in cat or "poultry" in cat or "sausage" in cat or "fish" in cat or "egg" in cat: return "protein"
    if "cereal" in cat or "grain" in cat or "bread" in cat or "pasta" in cat: return "grain"
    if "dairy" in cat or "milk" in cat or "cheese" in cat or "yogurt" in cat: return "dairy"
    if "fats" in cat or "oil" in cat or "butter" in cat or "margarine" in cat: return "fat"
    
    return "grain" # Default

# --- 5. SEARCH ROUTE ---
@app.route('/api/search', methods=['GET'])
def search_food():
    query = request.args.get('q')
    if not query: return jsonify({"error": "No query"}), 400

    print(f"🔎 Searching USDA for: {query}...") 

    payload = {
        "api_key": API_KEY,
        "query": query,
        "dataType": ["Foundation", "SR Legacy", "Branded", "Survey (FNDDS)"], 
        "pageSize": 6
    }

    try:
        r = session.get(BASE_URL, params=payload, timeout=10)
        
        if r.status_code != 200:
            print(f"❌ API ERROR: {r.status_code}")
            # If rate limited (429), tell the frontend
            if r.status_code == 429:
                return jsonify({"error": "Rate Limit Exceeded. Please wait."}), 429
            return jsonify([]), 200

        data = r.json()
        results = []
        
        for item in data.get('foods', []):
            nutrients = {n['nutrientId']: n['value'] for n in item.get('foodNutrients', [])}
            
            # IDs: 203=Protein, 204=Fat, 269=Sugar, 2000=Total Sugar, 208=Kcal
            protein = nutrients.get(203, 0)
            fat = nutrients.get(204, 0)
            sugar = nutrients.get(269, nutrients.get(2000, 0))
            calories = nutrients.get(208, 0)

            name = item.get('description')
            category = map_usda_category(item.get('foodCategory', ''), name)
            
            cooked_in = None
            special = None
            lower_name = name.lower()
            ingredients = item.get('ingredients', '').lower()
            
            if "soybean" in ingredients or "canola" in ingredients or "sunflower" in ingredients or "corn oil" in ingredients:
                cooked_in = "seed_oil"
            if "tallow" in lower_name or "raw milk" in lower_name or "grass-fed" in lower_name:
                special = "rfk_bonus"

            results.append({
                "name": name,
                "category": category,
                "protein_g": protein,
                "fat_g": fat,
                "sugar_g": sugar,
                "calories": calories,
                "cooked_in": cooked_in,
                "special": special
            })

        print(f"✅ Found {len(results)} results.")
        return jsonify(results)

    except Exception as e:
        print(f"❌ SYSTEM ERROR: {e}")
        return jsonify({"error": str(e)}), 500

# --- 6. SERVE HTML ---
@app.route('/')
def serve_index():
    if os.path.exists('index.html'):
        return send_from_directory('.', 'index.html')
    else:
        return "<h1>Error: index.html not found!</h1><p>Make sure app.py and index.html are in the same folder.</p>"

# --- 7. STARTUP & SELF-TEST ---
if __name__ == '__main__':
    print("\n" + "="*40)
    print("🚀 STARTING SERVER...")
    print("🔑 Testing API Key connection...")
    
    try:
        # Simple test request to USDA to check if key works
        test_payload = {"api_key": API_KEY, "query": "apple", "pageSize": 1}
        test_r = requests.get(BASE_URL, params=test_payload, timeout=5)
        
        if test_r.status_code == 200:
            print("✅ API Key is VALID! Connection successful.")
        elif test_r.status_code == 403:
            print("❌ ERROR: API Key is INVALID. Check your spelling.")
        elif test_r.status_code == 429:
            print("⚠️ WARNING: Rate Limit Exceeded. You must wait an hour or use a new key.")
        else:
            print(f"⚠️ WARNING: USDA returned status {test_r.status_code}")
    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")
        print("   (Check your internet connection)")

    print("="*40 + "\n")
    print("🌍 Open this link in your browser: http://127.0.0.1:5000/")
    
    app.run(debug=True, port=5000)