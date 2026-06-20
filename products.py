# products.py
# Product catalog for Shortcaike Beauty Stores (no emojis)
from typing import List, Dict, Optional

CATALOG = [
    {
        "name": "Hydrating Serum",
        "price": 7000,
        "category": "dry skin",
        "description": "Rich in hyaluronic acid that locks in moisture"
    },
    {
        "name": "Brightening Face Cream",
        "price": 5500,
        "category": "brightening",
        "description": "Even skin tone and reduce dark spots"
    },
    {
        "name": "Acne Treatment Gel",
        "price": 4500,
        "category": "acne",
        "description": "Tea tree oil based to clear breakouts"
    },
    {
        "name": "Sunscreen SPF 50",
        "price": 6000,
        "category": "sun protection",
        "description": "Broad spectrum UVA/UVB protection, soothes redness"
    },
    {
        "name": "Exfoliating Scrub",
        "price": 4000,
        "category": "face",
        "description": "Gentle exfoliation for smooth skin"
    },
    {
        "name": "Night Repair Cream",
        "price": 8000,
        "category": "dry skin",
        "description": "Deep hydration while you sleep"
    },
    {
        "name": "Aloe Vera Gel",
        "price": 3500,
        "category": "soothing",
        "description": "Calms irritated skin and sunburns"
    }
]

def get_catalog() -> List[Dict]:
    """Return full product catalog."""
    return CATALOG

def find_product_by_name(name: str) -> Optional[Dict]:
    """Search for a product by name (case‑insensitive, partial match)."""
    if not name:
        return None
    name_lower = name.lower()
    for product in CATALOG:
        if name_lower in product["name"].lower():
            return product
    return None

def get_product_price(name: str) -> float:
    """Return price of a product, or 0 if not found."""
    product = find_product_by_name(name)
    return product["price"] if product else 0

def search_products(query: str) -> List[Dict]:
    """Search products by name or category (case‑insensitive)."""
    query_lower = query.lower()
    return [
        p for p in CATALOG
        if query_lower in p["name"].lower() or query_lower in p["category"].lower()
    ]

def format_product_for_bot(product: Dict) -> str:
    """Format a product for display in WhatsApp messages."""
    return f"{product['name']} - ₦{product['price']:,} - {product['description']}"
