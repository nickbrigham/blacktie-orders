"""
/api/generate-orders.py - Generate and send weekly production orders

Vercel Serverless Function + Cron Job (runs Monday 10am)

POST /api/generate-orders
Body: {
    "pos_products": [...],
    "location": "lewiston",
    "send_email": true
}

Or triggered by Vercel Cron on Mondays.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from .sheets import BlackTieSheetsClient
from .matcher import ProductMatcher


# ============================================================
# ORDER THRESHOLDS
# ============================================================

THRESHOLDS = {
    'Shatter': 10,
    'Badder': 10,
    'Sugar': 10,
    'Live Resin': 10,
    'Full Spec Oil': 20,
    'Prerolls': 50,
    'Flower': 100,
}

ORDER_QUANTITIES = {
    'Shatter': 28,
    'Badder': 28,
    'Sugar': 28,
    'Live Resin': 28,
    'Full Spec Oil': 50,
    'Prerolls': 100,
    'Flower': 448,
}


# ============================================================
# ORDER GENERATION
# ============================================================

def generate_order_items(match_results: dict, location: str) -> list[dict]:
    """Generate order items from match results"""
    order_items = []
    
    # Process matched products - check for low stock
    for match in match_results['auto_matched']:
        category = match.get('production_category', 'Other')
        threshold = THRESHOLDS.get(category, 10)
        order_qty = ORDER_QUANTITIES.get(category, 28)
        
        pos_qty = match.get('pos_quantity', 0)
        prod_qty = match.get('production_quantity', 0)
        
        if pos_qty <= 0:
            order_items.append({
                'product_name': match['pos_name'],
                'category': category,
                'pos_quantity': pos_qty,
                'production_available': prod_qty,
                'requested_quantity': min(order_qty, prod_qty) if prod_qty > 0 else order_qty,
                'reason': 'out_of_stock',
                'priority': 'critical'
            })
        elif pos_qty < threshold:
            order_items.append({
                'product_name': match['pos_name'],
                'category': category,
                'pos_quantity': pos_qty,
                'production_available': prod_qty,
                'requested_quantity': min(order_qty, prod_qty) if prod_qty > 0 else order_qty,
                'reason': 'low_stock',
                'priority': 'high'
            })
    
    # Add production-only items as new products
    for prod in match_results['production_only']:
        category = prod.get('production_category', 'Other')
        order_qty = ORDER_QUANTITIES.get(category, 28)
        prod_qty = prod.get('production_quantity', 0)
        
        if prod_qty > 0:
            order_items.append({
                'product_name': prod['production_name'],
                'category': category,
                'pos_quantity': 0,
                'production_available': prod_qty,
                'requested_quantity': min(order_qty, prod_qty),
                'reason': 'new_product',
                'priority': 'normal'
            })
    
    # Sort by priority
    priority_order = {'critical': 0, 'high': 1, 'normal': 2}
    order_items.sort(key=lambda x: (priority_order.get(x['priority'], 3), x['category']))
    
    return order_items


def format_email_html(order_items: list[dict], location: str, order_date: datetime) -> str:
    """Format order items into HTML email"""
    
    due_date = order_date + timedelta(days=4)
    week_num = order_date.isocalendar()[1]
    order_number = f"BT-{order_date.year}-W{week_num:02d}-{location[:3].upper()}"
    
    critical_items = [i for i in order_items if i['priority'] == 'critical']
    high_items = [i for i in order_items if i['priority'] == 'high']
    new_items = [i for i in order_items if i['reason'] == 'new_product']
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
        <div style="background: #1a1a2e; color: white; padding: 20px; text-align: center;">
            <h1 style="margin: 0;">🌿 Black Tie Cannabis</h1>
            <p style="margin: 5px 0;">Weekly Production Order</p>
        </div>
        
        <div style="padding: 20px;">
            <table style="width: 100%; margin-bottom: 20px;">
                <tr>
                    <td><strong>Location:</strong> {location.title()}</td>
                    <td><strong>Order #:</strong> {order_number}</td>
                </tr>
                <tr>
                    <td><strong>Order Date:</strong> {order_date.strftime('%A, %B %d, %Y')}</td>
                    <td><strong>Due Date:</strong> {due_date.strftime('%A, %B %d, %Y')}</td>
                </tr>
            </table>
    """
    
    if critical_items:
        html += """
            <div style="background: #fee2e2; border-left: 4px solid #dc2626; padding: 15px; margin-bottom: 20px;">
                <h3 style="color: #dc2626; margin-top: 0;">🚨 CRITICAL - Out of Stock</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #fecaca;">
                        <th style="padding: 8px; text-align: left;">Product</th>
                        <th style="padding: 8px; text-align: left;">Category</th>
                        <th style="padding: 8px; text-align: right;">Current</th>
                        <th style="padding: 8px; text-align: right;">Request</th>
                    </tr>
        """
        for item in critical_items:
            html += f"""
                    <tr>
                        <td style="padding: 8px;">{item['product_name']}</td>
                        <td style="padding: 8px;">{item['category']}</td>
                        <td style="padding: 8px; text-align: right;">{item['pos_quantity']:.0f}</td>
                        <td style="padding: 8px; text-align: right; font-weight: bold;">{item['requested_quantity']:.0f}</td>
                    </tr>
            """
        html += "</table></div>"
    
    if high_items:
        html += """
            <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin-bottom: 20px;">
                <h3 style="color: #b45309; margin-top: 0;">⚠️ Low Stock</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #fde68a;">
                        <th style="padding: 8px; text-align: left;">Product</th>
                        <th style="padding: 8px; text-align: left;">Category</th>
                        <th style="padding: 8px; text-align: right;">Current</th>
                        <th style="padding: 8px; text-align: right;">Request</th>
                    </tr>
        """
        for item in high_items:
            html += f"""
                    <tr>
                        <td style="padding: 8px;">{item['product_name']}</td>
                        <td style="padding: 8px;">{item['category']}</td>
                        <td style="padding: 8px; text-align: right;">{item['pos_quantity']:.0f}</td>
                        <td style="padding: 8px; text-align: right;">{item['requested_quantity']:.0f}</td>
                    </tr>
            """
        html += "</table></div>"
    
    if new_items:
        html += f"""
            <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 15px; margin-bottom: 20px;">
                <h3 style="color: #1d4ed8; margin-top: 0;">📦 New Products Available</h3>
                <p style="color: #1e40af;">These items are in production but not yet stocked at {location.title()}:</p>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #bfdbfe;">
                        <th style="padding: 8px; text-align: left;">Product</th>
                        <th style="padding: 8px; text-align: left;">Category</th>
                        <th style="padding: 8px; text-align: right;">Available</th>
                        <th style="padding: 8px; text-align: right;">Send</th>
                    </tr>
        """
        for item in new_items:
            html += f"""
                    <tr>
                        <td style="padding: 8px;">{item['product_name']}</td>
                        <td style="padding: 8px;">{item['category']}</td>
                        <td style="padding: 8px; text-align: right;">{item['production_available']:.0f}</td>
                        <td style="padding: 8px; text-align: right;">{item['requested_quantity']:.0f}</td>
                    </tr>
            """
        html += "</table></div>"
    
    html += f"""
            <div style="background: #f3f4f6; padding: 15px; border-radius: 8px;">
                <h3 style="margin-top: 0;">📊 Summary</h3>
                <ul>
                    <li>Critical Items: {len(critical_items)}</li>
                    <li>Low Stock Items: {len(high_items)}</li>
                    <li>New Products: {len(new_items)}</li>
                    <li><strong>Total Line Items: {len(order_items)}</strong></li>
                </ul>
            </div>
        </div>
        
        <div style="background: #1a1a2e; color: #9ca3af; padding: 15px; text-align: center; font-size: 12px;">
            Black Tie Cannabis Inventory System
        </div>
    </body>
    </html>
    """
    
    return html


def send_order_email(html_content: str, location: str, order_date: datetime) -> bool:
    """Send order email via SendGrid"""
    
    api_key = os.environ.get('SENDGRID_API_KEY')
    if not api_key:
        raise ValueError("SENDGRID_API_KEY not configured")
    
    to_email = os.environ.get('PRODUCTION_EMAIL', 'matt.barlion@gmail.com')
    cc_email = os.environ.get('CC_EMAIL', 'blacktiecannabis@gmail.com')
    from_email = os.environ.get('FROM_EMAIL', 'orders@blacktiecannabis.com')
    
    week_num = order_date.isocalendar()[1]
    subject = f"🔔 Black Tie Production Order - {location.title()} - Week {week_num}"
    
    message = Mail(
        from_email=Email(from_email, "Black Tie Orders"),
        to_emails=[To(to_email), To(cc_email)],
        subject=subject,
        html_content=html_content
    )
    
    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


# ============================================================
# VERCEL HANDLER
# ============================================================

class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler"""
    
    def do_POST(self):
        """POST /api/generate-orders - Generate and optionally send order"""
        try:
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body) if body else {}
            
            pos_products = data.get('pos_products', [])
            location = data.get('location', 'lewiston')
            send_email = data.get('send_email', False)
            
            # Get production inventory
            sheets_client = BlackTieSheetsClient()
            production_data = sheets_client.get_all_inventory()
            production_products = production_data['products']
            
            # Run matching
            matcher = ProductMatcher()
            match_results = matcher.match_inventory(pos_products, production_products)
            
            # Generate order items
            order_date = datetime.now()
            order_items = generate_order_items(match_results, location)
            
            # Format email
            email_html = format_email_html(order_items, location, order_date)
            
            # Send email if requested
            email_sent = False
            if send_email and order_items:
                email_sent = send_order_email(email_html, location, order_date)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'success': True,
                'data': {
                    'order_items': order_items,
                    'summary': {
                        'critical': len([i for i in order_items if i['priority'] == 'critical']),
                        'high': len([i for i in order_items if i['priority'] == 'high']),
                        'new_products': len([i for i in order_items if i['reason'] == 'new_product']),
                        'total': len(order_items)
                    },
                    'email_sent': email_sent,
                    'email_html': email_html if not send_email else None  # Include HTML for preview
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
    
    def do_GET(self):
        """GET /api/generate-orders - Cron job trigger (Monday 10am)"""
        # This would be called by Vercel Cron
        # In production, you'd load saved POS data or trigger a manual review
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        self.wfile.write(json.dumps({
            'success': True,
            'message': 'Cron trigger received. Manual POS upload required for order generation.'
        }).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
