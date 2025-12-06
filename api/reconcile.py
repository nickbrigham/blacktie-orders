"""
/api/reconcile.py - Reconcile POS inventory against Production

Vercel Serverless Function

POST /api/reconcile
Body: {
    "pos_products": [
        {"name": "Product Name", "type": "Badder House", "quantity": 26},
        ...
    ],
    "location": "lewiston"
}

Returns matched products, items needing review, and production-only items.
"""

from http.server import BaseHTTPRequestHandler
import json
import os

from .sheets import BlackTieSheetsClient
from .matcher import ProductMatcher


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler"""
    
    def do_POST(self):
        """POST /api/reconcile - Reconcile POS against production inventory"""
        try:
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            pos_products = data.get('pos_products', [])
            location = data.get('location', 'unknown')
            
            if not pos_products:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'pos_products is required'
                }).encode())
                return
            
            # Get production inventory
            sheets_client = BlackTieSheetsClient()
            production_data = sheets_client.get_all_inventory()
            production_products = production_data['products']
            
            # Run matching
            matcher = ProductMatcher()
            results = matcher.match_inventory(pos_products, production_products)
            
            # Add summary
            results['summary'] = {
                'location': location,
                'pos_product_count': len(pos_products),
                'production_product_count': len(production_products),
                'auto_matched': len(results['auto_matched']),
                'needs_review': len(results['needs_review']),
                'unmatched': len(results['unmatched']),
                'production_only': len(results['production_only'])
            }
            
            # Include production inventory summary
            results['production_summary'] = production_data['summary']
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'success': True,
                'data': results
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
