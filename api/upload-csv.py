"""
/api/upload-csv.py - Parse Flowhub CSV and return structured data

Vercel Serverless Function

POST /api/upload-csv
Body: CSV file content

Returns parsed products ready for reconciliation.
"""

from http.server import BaseHTTPRequestHandler
import json
import csv
import io


def parse_flowhub_csv(csv_content: str) -> list[dict]:
    """
    Parse Flowhub inventory CSV export.
    
    Expected columns:
    - Product Name
    - Product Type
    - Quantity
    
    Returns list of dicts with 'name', 'type', 'quantity'
    """
    products = []
    
    reader = csv.DictReader(io.StringIO(csv_content))
    
    for row in reader:
        # Skip totals row
        name = row.get('Product Name', '').strip()
        if not name or name == '---TOTALS---':
            continue
        
        product_type = row.get('Product Type', '').strip()
        
        try:
            quantity = float(row.get('Quantity', 0))
        except (ValueError, TypeError):
            quantity = 0
        
        products.append({
            'name': name,
            'type': product_type,
            'quantity': quantity
        })
    
    return products


def filter_bt_products(products: list[dict]) -> list[dict]:
    """
    Filter to only Black Tie production items.
    
    Excludes third-party brands and accessories.
    """
    # Product types that are BT production
    bt_types = {
        'badder', 'badder house', 'badder house (baller)', 'badder (baller)',
        'shatter', 'sugar', 'live resin', 'resin',
        'flower', 'cart',
        'pre roll', 'pre roll 2', 'pre roll pack', 'pre roll infused',
        'rosin', 'hash rosin', 'diamonds',
        'baller jar', 'concentrate'
    }
    
    # Skip these product types (accessories, third-party)
    skip_types = {
        'misc.', 'glass', 'apparel', 'vape', 'battery', 'nicotine',
        'gift card', 'e rig', 'edible'  # Edibles are manufacturing, not production
    }
    
    # Name patterns that indicate third-party
    third_party_patterns = [
        'bs trees', 'bstrees', 'budard', 'casco', 'crooked jaw',
        'dabilitated', 'dialed in', 'ekko', 'fish meadow', 'fraktal',
        'harbor', 'hilltop', 'iron lung', 'laughing lobster', 'leaf labs',
        'lookah', 'lost mary', 'maine concentrates', 'medible', 'mojo',
        'new horizons', 'northern terps', 'peace of maine', 'pot & pan',
        'puffco', 'recovery', 'refine', 'secret stash', 'sireel',
        'terra horta', 'fresh canna', 'brick house', 'cadillac pre'
    ]
    
    filtered = []
    
    for product in products:
        product_type = product.get('type', '').lower().strip()
        product_name = product.get('name', '').lower()
        
        # Skip non-production types
        if product_type in skip_types:
            continue
        
        # Skip if type not in our production categories
        type_match = any(bt in product_type for bt in bt_types)
        if not type_match:
            continue
        
        # Skip third-party products
        is_third_party = any(tp in product_name for tp in third_party_patterns)
        if is_third_party:
            continue
        
        filtered.append(product)
    
    return filtered


def aggregate_by_product(products: list[dict]) -> list[dict]:
    """
    Aggregate quantities for same product (combines locations).
    """
    aggregated = {}
    
    for product in products:
        key = (product['name'], product['type'])
        
        if key in aggregated:
            aggregated[key]['quantity'] += product['quantity']
        else:
            aggregated[key] = {
                'name': product['name'],
                'type': product['type'],
                'quantity': product['quantity']
            }
    
    return list(aggregated.values())


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler"""
    
    def do_POST(self):
        """POST /api/upload-csv - Parse uploaded CSV"""
        try:
            # Get content type
            content_type = self.headers.get('Content-Type', '')
            
            # Read body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Handle different content types
            if 'multipart/form-data' in content_type:
                # Handle file upload
                # This is simplified - in production use proper multipart parsing
                csv_content = body.decode('utf-8', errors='ignore')
                # Extract CSV content from multipart (basic extraction)
                if 'Product Name' in csv_content:
                    start = csv_content.find('Product Name')
                    csv_content = csv_content[start:]
                    # Find end of CSV (before boundary)
                    if '------' in csv_content:
                        csv_content = csv_content[:csv_content.find('------')]
            else:
                csv_content = body.decode('utf-8')
            
            # Parse CSV
            all_products = parse_flowhub_csv(csv_content)
            
            # Filter to BT products
            bt_products = filter_bt_products(all_products)
            
            # Aggregate (in case same product appears twice for different locations)
            aggregated = aggregate_by_product(bt_products)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'success': True,
                'data': {
                    'total_rows': len(all_products),
                    'bt_products': len(bt_products),
                    'aggregated_products': len(aggregated),
                    'products': aggregated
                }
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
