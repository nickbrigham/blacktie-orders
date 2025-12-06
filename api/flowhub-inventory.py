"""
/api/flowhub-inventory.py - Get POS inventory from Flowhub API

Vercel Serverless Function

GET /api/flowhub-inventory?location=lewiston
GET /api/flowhub-inventory?location=greene
GET /api/flowhub-inventory  (returns both locations)

Endpoint: https://api.flowhub.co/v0/locations/{locationId}/inventory

Returns real-time inventory from Flowhub - no CSV upload needed!
"""

from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

from .flowhub import FlowhubClient, filter_bt_products


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler"""
    
    def do_GET(self):
        """GET /api/flowhub-inventory - Get POS inventory from Flowhub"""
        try:
            # Parse query params
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            location = params.get('location', [None])[0]
            filter_bt = params.get('filter', ['true'])[0].lower() == 'true'
            
            client = FlowhubClient()
            
            if location:
                # Get single location
                products = client.get_inventory(location)
                
                if filter_bt:
                    products = filter_bt_products(products)
                
                result = {
                    'location': location,
                    'product_count': len(products),
                    'products': [
                        {
                            'name': p.name,
                            'parent_name': p.parent_name,
                            'type': p.category,
                            'quantity': p.quantity,
                            'unit': p.unit,
                            'sku': p.sku,
                            'strain': p.strain_name,
                            'supplier': p.supplier_name
                        }
                        for p in products
                    ]
                }
            else:
                # Get all locations
                all_inventory = client.get_all_locations_inventory()
                
                result = {
                    'locations': {}
                }
                
                for loc_name, products in all_inventory.items():
                    if isinstance(products, dict) and 'error' in products:
                        result['locations'][loc_name] = products
                    else:
                        if filter_bt:
                            products = filter_bt_products(products)
                        
                        result['locations'][loc_name] = {
                            'product_count': len(products),
                            'products': [
                                {
                                    'name': p.name,
                                    'parent_name': p.parent_name,
                                    'type': p.category,
                                    'quantity': p.quantity,
                                    'unit': p.unit
                                }
                                for p in products
                            ]
                        }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'success': True,
                'data': result
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
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
