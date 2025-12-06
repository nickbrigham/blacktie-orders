"""
Black Tie Cannabis - Flowhub API Integration

Pulls real-time inventory data from Flowhub POS via their API.
No more manual CSV exports needed!

API Documentation: https://flowhub.stoplight.io/docs/public-developer-portal/

Endpoint: GET https://api.flowhub.co/v0/locations/{locationId}/inventory

Authentication Headers:
- clientId: Your client ID (UUID)
- key: Your API key (UUID)

Response fields include:
- productName: Full product name with variant
- parentProductName: Base product name
- category: Product category (Flower, Concentrate, etc.)
- quantity: Current inventory count
- inventoryUnitOfMeasure: Unit (grams, units, etc.)
- sku, strainName, supplierName, cannabinoidInformation, etc.
"""

import os
import httpx
from dataclasses import dataclass
from typing import Optional


# ============================================================
# CONFIGURATION
# ============================================================

FLOWHUB_CONFIG = {
    'client_id': os.environ.get('FLOWHUB_CLIENT_ID', '2a114178-f811-4b69-89db-d6ef6ac6e4b4'),
    'api_key': os.environ.get('FLOWHUB_API_KEY', '6365ac53-3186-4df4-bba9-6b41d52e671f'),
    'locations': {
        'lewiston': {
            'id': 'b9d2a82b-9c98-4f18-95f3-df8843c0cf1e',
            'name': 'Black Tie Cannabis Lewiston'
        },
        'greene': {
            'id': '1333c834-871e-4a6b-b2c9-30bfac938233',
            'name': 'Black Tie Cannabis'  # Greene location
        }
    },
    'base_url': 'https://api.flowhub.co',
}


@dataclass
class FlowhubProduct:
    """A product from Flowhub inventory"""
    id: str
    name: str
    parent_name: str
    category: str
    quantity: float
    unit: str = 'units'
    sku: Optional[str] = None
    strain_name: Optional[str] = None
    supplier_name: Optional[str] = None
    thc_percentage: Optional[float] = None
    cbd_percentage: Optional[float] = None
    price_cents: Optional[int] = None
    product_weight: Optional[float] = None
    

class FlowhubClient:
    """
    Client for Flowhub's REST API.
    
    Endpoint: GET /v0/locations/{locationId}/inventory
    
    Returns all inventory items for the specified location.
    Inventory is summed across all rooms.
    
    Usage:
        client = FlowhubClient()
        inventory = client.get_inventory('lewiston')
        
        for product in inventory:
            print(f"{product.name}: {product.quantity} {product.unit}")
    """
    
    def __init__(
        self,
        client_id: str = None,
        api_key: str = None,
        base_url: str = None
    ):
        self.client_id = client_id or FLOWHUB_CONFIG['client_id']
        self.api_key = api_key or FLOWHUB_CONFIG['api_key']
        self.base_url = base_url or FLOWHUB_CONFIG['base_url']
        self.locations = FLOWHUB_CONFIG['locations']
    
    def _get_headers(self) -> dict:
        """
        Build request headers for Flowhub API.
        
        Required headers per API docs:
        - clientId: Your unique integrator client ID
        - key: Your integration authentication token
        """
        return {
            'clientId': self.client_id,
            'key': self.api_key,
            'Accept': 'application/json',
        }
    
    def _get_location_id(self, location: str) -> str:
        """Convert location name to Flowhub location ID"""
        location_lower = location.lower().strip()
        if location_lower in self.locations:
            return self.locations[location_lower]['id']
        return location
    
    def get_inventory(self, location: str) -> list[FlowhubProduct]:
        """
        Get inventory for a location.
        
        Endpoint: GET /v0/locations/{locationId}/inventory
        
        Args:
            location: 'lewiston', 'greene', or a location ID
            
        Returns:
            List of FlowhubProduct objects
        """
        location_id = self._get_location_id(location)
        
        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                f"{self.base_url}/v0/locations/{location_id}/inventory",
                headers=self._get_headers()
            )
            
            if response.status_code == 401:
                raise Exception("Unauthorized - check your clientId and key")
            elif response.status_code != 200:
                raise Exception(f"Flowhub API error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            # Response format: {"status": 200, "data": [...]}
            if data.get('status') != 200:
                raise Exception(f"API returned error status: {data.get('status')}")
            
            return self._parse_inventory_response(data.get('data', []))
    
    def _parse_inventory_response(self, items: list) -> list[FlowhubProduct]:
        """Parse Flowhub inventory API response"""
        products = []
        
        for item in items:
            product = self._parse_item(item)
            if product:
                products.append(product)
        
        return products
    
    def _parse_item(self, item: dict) -> Optional[FlowhubProduct]:
        """
        Parse a single inventory item from Flowhub API.
        
        Key fields from API response:
        - productName: Full name with variant (e.g., "Afghani Shake - One Gram")
        - parentProductName: Base product name (e.g., "Afghani Shake")
        - category: Product category (Flower, Concentrate, etc.)
        - quantity: Current inventory count
        - inventoryUnitOfMeasure: Unit (grams, units, etc.)
        - sku: SKU code
        - strainName: Strain name
        - supplierName: Supplier
        - cannabinoidInformation: Array with THC/CBD data
        - productWeight: Weight in base units
        - preTaxPriceInPennies: Price in cents
        """
        if not item:
            return None
        
        name = item.get('productName', '')
        if not name:
            return None
        
        # Extract THC/CBD from cannabinoidInformation array
        thc = None
        cbd = None
        cannabinoids = item.get('cannabinoidInformation', []) or []
        for c in cannabinoids:
            c_name = (c.get('name') or '').lower()
            # Use upperRange as the value (or lowerRange if same)
            value = c.get('upperRange') or c.get('lowerRange')
            unit = c.get('unitOfMeasure', '%')
            
            if c_name == 'thc' and unit == '%':
                thc = value
            elif c_name == 'cbd' and unit == '%':
                cbd = value
        
        return FlowhubProduct(
            id=item.get('productId', ''),
            name=name,
            parent_name=item.get('parentProductName', name),
            category=item.get('category', ''),
            quantity=item.get('quantity', 0),
            unit=item.get('inventoryUnitOfMeasure', 'units'),
            sku=item.get('sku'),
            strain_name=item.get('strainName'),
            supplier_name=item.get('supplierName'),
            thc_percentage=thc,
            cbd_percentage=cbd,
            price_cents=item.get('preTaxPriceInPennies'),
            product_weight=item.get('productWeight')
        )
    
    def test_connection(self) -> dict:
        """
        Test the API connection by fetching Lewiston inventory.
        
        Returns:
            Dict with 'success', 'message', and optionally 'count'
        """
        try:
            location_id = self.locations['lewiston']['id']
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.base_url}/v0/locations/{location_id}/inventory",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    count = len(data.get('data', []))
                    return {
                        'success': True,
                        'message': f'Connected! Found {count} inventory items',
                        'count': count
                    }
                elif response.status_code == 401:
                    return {'success': False, 'message': 'Unauthorized - invalid clientId or key'}
                else:
                    return {
                        'success': False,
                        'message': f'API error {response.status_code}: {response.text[:200]}'
                    }
                    
        except httpx.ConnectError:
            return {'success': False, 'message': 'Could not connect to api.flowhub.co'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def get_all_locations_inventory(self) -> dict:
        """
        Get inventory for all configured locations.
        
        Returns:
            Dict mapping location name to list of products or error
        """
        all_inventory = {}
        
        for location_name in self.locations:
            try:
                products = self.get_inventory(location_name)
                all_inventory[location_name] = products
            except Exception as e:
                all_inventory[location_name] = {'error': str(e)}
        
        return all_inventory


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_pos_inventory(location: str = 'lewiston') -> list[dict]:
    """
    Get POS inventory as simple dicts for order generation.
    
    Args:
        location: 'lewiston' or 'greene'
        
    Returns:
        List of dicts with 'name', 'type', 'quantity', 'unit'
    """
    client = FlowhubClient()
    products = client.get_inventory(location)
    
    return [
        {
            'name': p.name,
            'parent_name': p.parent_name,
            'type': p.category,
            'quantity': p.quantity,
            'unit': p.unit,
            'sku': p.sku,
            'strain': p.strain_name
        }
        for p in products
    ]


def filter_bt_products(products: list[FlowhubProduct]) -> list[FlowhubProduct]:
    """
    Filter to only Black Tie production items.
    
    Excludes third-party brands and accessories.
    """
    # Categories that are BT production
    bt_categories = {
        'flower', 'concentrate', 'pre-roll', 'preroll', 'pre roll',
        'cartridge', 'cart', 'vape', 'edible', 'tincture', 'topical'
    }
    
    # Skip these categories entirely
    skip_categories = {
        'accessory', 'accessories', 'glass', 'apparel', 'battery',
        'merchandise', 'merch', 'gear', 'misc', 'other'
    }
    
    # Third-party brand/supplier patterns to exclude
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
        category = product.category.lower().strip()
        product_name = product.name.lower()
        supplier = (product.supplier_name or '').lower()
        
        # Skip non-cannabis categories
        if category in skip_categories:
            continue
        
        # Check if category matches BT production
        category_match = any(bt in category for bt in bt_categories)
        if not category_match:
            continue
        
        # Skip third-party brands (check name and supplier)
        is_third_party = any(
            tp in product_name or tp in supplier 
            for tp in third_party_patterns
        )
        if is_third_party:
            continue
        
        filtered.append(product)
    
    return filtered


def aggregate_by_parent(products: list[FlowhubProduct]) -> dict:
    """
    Aggregate inventory by parent product name.
    
    Flowhub returns variants separately (e.g., "Strain - 1g", "Strain - 3.5g").
    This combines them back to the base product level.
    
    Returns:
        Dict mapping parent_name to total quantity
    """
    aggregated = {}
    
    for p in products:
        key = p.parent_name or p.name
        if key not in aggregated:
            aggregated[key] = {
                'name': key,
                'category': p.category,
                'total_quantity': 0,
                'unit': p.unit,
                'variants': []
            }
        
        aggregated[key]['total_quantity'] += p.quantity
        aggregated[key]['variants'].append({
            'name': p.name,
            'quantity': p.quantity,
            'weight': p.product_weight
        })
    
    return aggregated


# ============================================================
# CLI TESTING
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("FLOWHUB API CLIENT TEST")
    print("=" * 60)
    
    client = FlowhubClient()
    
    print("\nConfiguration:")
    print(f"  Client ID: {client.client_id}")
    print(f"  API Key: {client.api_key[:8]}...{client.api_key[-4:]}")
    print(f"  Base URL: {client.base_url}")
    
    print("\nLocations:")
    for name, info in client.locations.items():
        print(f"  {name}: {info['id']}")
    
    print("\nTesting connection...")
    result = client.test_connection()
    
    if result['success']:
        print(f"  ✅ {result['message']}")
        
        print("\nFetching Lewiston inventory...")
        try:
            products = client.get_inventory('lewiston')
            print(f"  Total items: {len(products)}")
            
            # Filter to BT only
            bt_products = filter_bt_products(products)
            print(f"  BT production items: {len(bt_products)}")
            
            # Group by category
            categories = {}
            for p in bt_products:
                cat = p.category
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(p)
            
            print("\n  By Category:")
            for cat, items in sorted(categories.items()):
                total_qty = sum(p.quantity for p in items)
                print(f"    {cat}: {len(items)} items, {total_qty} total qty")
            
            # Show first 5
            print("\n  Sample products:")
            for p in bt_products[:5]:
                print(f"    - {p.name}: {p.quantity} {p.unit} ({p.category})")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    else:
        print(f"  ❌ {result['message']}")
