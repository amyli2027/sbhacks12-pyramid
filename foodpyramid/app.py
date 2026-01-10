import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

app = Flask(__name__, static_folder='.')
CORS(app)

# ---------------- CONFIGURATION ----------------
API_KEY = "DEMO_KEY"  # Replace with your actual key if you hit limits
BASE_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# ---------------- HELPER: CATEGORY MAPPER ----------------
def map_usda_category(usda_cat, name):
    cat = usda_cat.lower()
    name_lower = name.lower()
    
    # Priority Keywords for Junk Food
    if "candy" in cat or "chocolate" in name_lower or "reeses" in name_lower or "snack" in cat: return "sweet"
    if "cookie" in name_lower or "pastry" in cat or "croissant" in name_lower or "cake" in name_lower: return "sweet"
    if "soda" in name_lower or "beverage" in cat: return "sweet"
    if "chips" in name_lower or "fries" in name_lower: return "veg" # We'll catch the oil in the special flags

    # Standard Categories
    if "fruit" in cat: return "fruit"
    if "vegetable" in cat or "pod" in cat: return "veg"
    if "beef" in cat or "pork" in cat or "poultry" in cat or "sausage" in cat or "fish" in cat or "egg" in cat: return "protein"
    if "cereal" in cat or "grain" in cat or "bread" in cat or "pasta" in cat: return "grain"
    if "dairy" in cat or "milk" in cat or "cheese" in cat or "yogurt" in cat: return "dairy"
    if "fats" in cat or "oil" in cat or "butter" in cat: return "fat"
    
    return "grain" # Default fallback

# ---------------- ROUTE: SEARCH ----------------
@app.route('/api/search', methods=['GET'])
def search_food():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "No query provided"}), 400

    # UPDATE: We now include 'Branded' and 'Survey' to find Croissants & Candy
    payload = {
        "api_key": API_KEY,
        "query": query,
        "dataType": ["Foundation", "SR Legacy", "Branded", "Survey (FNDDS)"], 
        "pageSize": 6
    }

    try:
        r = requests.get(BASE_URL, params=payload)
        data = r.json()
        
        results = []
        for item in data.get('foods', []):
            # USDA Nutrient IDs: 
            # 203=Protein, 204=Total Fat, 205=Carbs, 269=Sugars, 208=Energy(Kcal)
            nutrients = {n['nutrientId']: n['value'] for n in item.get('foodNutrients', [])}
            
            protein = nutrients.get(203, 0)
            fat = nutrients.get(204, 0)
            sugar = nutrients.get(269, 0)
            calories = nutrients.get(208, 0)

            name = item.get('description')
            category = map_usda_category(item.get('foodCategory', ''), name)
            
            # Special Flags
            cooked_in = None
            special = None
            
            lower_name = name.lower()
            
            # Identify Seed Oils (often in Branded chips/snacks)
            ingredients = item.get('ingredients', '').lower()
            if "soybean" in ingredients or "canola" in ingredients or "sunflower" in ingredients or "corn oil" in ingredients:
                cooked_in = "seed_oil"
            
            # RFK Bonus
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

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)