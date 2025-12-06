"""
Black Tie Cannabis - Google Sheets Integration
Auto-detects sheet tabs and parses production inventory

This module automatically discovers all tabs in the spreadsheet
and attempts to parse them as inventory sheets.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ProductionProduct:
    """A product in production inventory"""
    name: str
    quantity: float
    sheet_tab: str
    unit: str = "grams"
    row_number: int = 0


@dataclass
class SheetTabConfig:
    """Configuration for a detected sheet tab"""
    name: str
    gid: int
    format: str  # 'ledger', 'flower', 'simple', 'unknown'
    summary_row: str  # 'total remaining', 'quantity on hand', etc.
    unit: str
    is_inventory: bool  # Whether this looks like an inventory sheet


# ============================================================
# KNOWN CONFIGURATIONS (can be extended automatically)
# ============================================================

# Keywords that indicate a sheet is an inventory sheet
INVENTORY_KEYWORDS = [
    'shatter', 'badder', 'sugar', 'live resin', 'resin',
    'full spec', 'oil', 'cart', 'preroll', 'pre roll', 'pre-roll',
    'flower', 'rosin', 'diamond', 'concentrate', 'wax'
]

# Keywords to skip when looking for product names
SKIP_PATTERNS = [
    r'^lewiston$',
    r'^greene$',
    r'^ws$',
    r'^wholesale$',
    r'^total remaining$',
    r'^total$',
    r'^quantity on hand$',
    r'^average cost.*$',
    r'^updated$',
    r'^product name$',
    r'^strain$',
    r'^type$',
    r'^audit$',
    r'^amount available$',
    r'^quantity available.*$',
    r'^\d+/\d+/\d+$',  # Dates
    r'^$',
]

# Map sheet names to categories for POS matching
CATEGORY_MAP = {
    'shatter': 'Shatter',
    'badder': 'Badder',
    'sugar': 'Sugar',
    'live resin': 'Live Resin',
    'full spec oil': 'Full Spec Oil',
    'full spec': 'Full Spec Oil',
    'prerolls': 'Prerolls',
    'pre rolls': 'Prerolls',
    'flower': 'Flower',
    'rosin': 'Rosin',
    'diamonds': 'Diamonds',
}


# ============================================================
# SHEETS CLIENT WITH AUTO-DETECT
# ============================================================

class BlackTieSheetsClient:
    """
    Google Sheets client that auto-detects inventory tabs.
    
    Features:
    - Automatically discovers all sheet tabs
    - Identifies which tabs contain inventory data
    - Detects the format of each tab (ledger, flower, simple)
    - Parses products from all inventory tabs
    """
    
    SPREADSHEET_ID = os.environ.get(
        'GOOGLE_SHEETS_SPREADSHEET_ID',
        '1H6pOc_URqzoQwb-F12fd2DAfSxhFb6nNLyt50D7W_vM'
    )
    
    def __init__(self):
        """Initialize with Google credentials from environment"""
        self._service = None
        self._detected_tabs: list[SheetTabConfig] = []
    
    @property
    def service(self):
        """Lazy-load the Google Sheets service"""
        if self._service is None:
            # Build credentials from environment variables
            creds_info = {
                "type": "service_account",
                "project_id": os.environ.get("GCP_PROJECT_ID"),
                "private_key": os.environ.get("GCP_PRIVATE_KEY", "").replace("\\n", "\n"),
                "client_email": os.environ.get("GCP_CLIENT_EMAIL"),
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            
            self._service = build('sheets', 'v4', credentials=creds)
        
        return self._service
    
    def discover_tabs(self) -> list[SheetTabConfig]:
        """
        Discover all tabs in the spreadsheet and identify inventory tabs.
        
        Returns:
            List of SheetTabConfig objects for each detected tab
        """
        # Get spreadsheet metadata
        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=self.SPREADSHEET_ID
        ).execute()
        
        tabs = []
        
        for sheet in spreadsheet.get('sheets', []):
            props = sheet.get('properties', {})
            title = props.get('title', '')
            gid = props.get('sheetId', 0)
            
            # Check if this looks like an inventory sheet
            title_lower = title.lower()
            is_inventory = any(kw in title_lower for kw in INVENTORY_KEYWORDS)
            
            # Detect format by sampling the sheet
            format_info = self._detect_format(title)
            
            # Determine unit
            if 'flower' in title_lower:
                unit = 'grams'  # Will convert to lbs in display
            elif 'preroll' in title_lower or 'pre roll' in title_lower:
                unit = 'units'
            else:
                unit = 'grams'
            
            tabs.append(SheetTabConfig(
                name=title,
                gid=gid,
                format=format_info['format'],
                summary_row=format_info['summary_row'],
                unit=unit,
                is_inventory=is_inventory
            ))
        
        self._detected_tabs = tabs
        return tabs
    
    def _detect_format(self, sheet_name: str) -> dict:
        """
        Sample a sheet to detect its format.
        
        Returns:
            Dict with 'format' and 'summary_row' keys
        """
        try:
            # Get first 50 rows to analyze
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.SPREADSHEET_ID,
                range=f"'{sheet_name}'!A1:C50"
            ).execute()
            
            rows = result.get('values', [])
            
            # Look for indicator patterns
            has_total_remaining = False
            has_quantity_on_hand = False
            has_amount_available = False
            
            for row in rows:
                if not row:
                    continue
                cell = str(row[0]).lower().strip()
                
                if cell == 'total remaining':
                    has_total_remaining = True
                elif cell == 'quantity on hand':
                    has_quantity_on_hand = True
                elif cell == 'amount available':
                    has_amount_available = True
            
            # Determine format
            if has_quantity_on_hand:
                return {'format': 'flower', 'summary_row': 'quantity on hand'}
            elif has_total_remaining:
                return {'format': 'ledger', 'summary_row': 'total remaining'}
            elif has_amount_available:
                return {'format': 'simple', 'summary_row': None}
            else:
                return {'format': 'simple', 'summary_row': None}
                
        except Exception as e:
            print(f"Error detecting format for {sheet_name}: {e}")
            return {'format': 'unknown', 'summary_row': None}
    
    def _is_product_name(self, value: str) -> bool:
        """Check if a cell value is a product name"""
        if not value or not isinstance(value, str):
            return False
        
        value_lower = value.strip().lower()
        
        for pattern in SKIP_PATTERNS:
            if re.match(pattern, value_lower):
                return False
        
        if len(value_lower) < 2:
            return False
        
        # Shouldn't be just a number
        try:
            float(value_lower.replace(',', ''))
            return False
        except ValueError:
            pass
        
        return True
    
    def _parse_number(self, value: str) -> Optional[float]:
        """Parse a number from a cell value"""
        if not value:
            return None
        try:
            cleaned = str(value).replace(',', '').strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    def parse_tab(self, tab_config: SheetTabConfig) -> list[ProductionProduct]:
        """
        Parse a single tab and extract products.
        
        Args:
            tab_config: Configuration for the tab to parse
            
        Returns:
            List of ProductionProduct objects
        """
        if not tab_config.is_inventory:
            return []
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.SPREADSHEET_ID,
                range=f"'{tab_config.name}'!A:C"
            ).execute()
            
            rows = result.get('values', [])
        except Exception as e:
            print(f"Error reading {tab_config.name}: {e}")
            return []
        
        products = []
        current_product_name = None
        
        for i, row in enumerate(rows):
            if not row:
                continue
            
            cell_a = str(row[0]).strip() if row else ""
            cell_b = str(row[1]).strip() if len(row) > 1 else ""
            
            cell_a_lower = cell_a.lower()
            
            # Check for summary row
            if tab_config.summary_row and cell_a_lower == tab_config.summary_row:
                if current_product_name:
                    qty = self._parse_number(cell_b)
                    if qty is not None and qty > 0:
                        products.append(ProductionProduct(
                            name=current_product_name,
                            quantity=qty,
                            sheet_tab=tab_config.name,
                            unit=tab_config.unit,
                            row_number=i + 1
                        ))
                current_product_name = None
                continue
            
            # Simple format: name and qty on same row
            if tab_config.format == 'simple':
                if self._is_product_name(cell_a):
                    qty = self._parse_number(cell_b)
                    if qty is not None and qty > 0:
                        products.append(ProductionProduct(
                            name=cell_a,
                            quantity=qty,
                            sheet_tab=tab_config.name,
                            unit=tab_config.unit,
                            row_number=i + 1
                        ))
                continue
            
            # Ledger/Flower format: look for product names
            if self._is_product_name(cell_a):
                current_product_name = cell_a
        
        return products
    
    def get_all_inventory(self) -> dict:
        """
        Get all inventory from all detected tabs.
        
        Returns:
            Dict with:
            - 'tabs': List of detected tab configurations
            - 'products': List of all products
            - 'by_category': Products grouped by sheet tab
            - 'summary': Total counts per category
        """
        # Discover tabs if not already done
        if not self._detected_tabs:
            self.discover_tabs()
        
        all_products = []
        by_category = {}
        summary = {}
        
        for tab in self._detected_tabs:
            if not tab.is_inventory:
                continue
            
            products = self.parse_tab(tab)
            all_products.extend(products)
            
            by_category[tab.name] = products
            summary[tab.name] = {
                'count': len(products),
                'total': sum(p.quantity for p in products),
                'unit': tab.unit
            }
        
        return {
            'tabs': [
                {
                    'name': t.name,
                    'gid': t.gid,
                    'format': t.format,
                    'is_inventory': t.is_inventory
                }
                for t in self._detected_tabs
            ],
            'products': [
                {
                    'name': p.name,
                    'quantity': p.quantity,
                    'category': p.sheet_tab,
                    'unit': p.unit
                }
                for p in all_products
            ],
            'by_category': {
                cat: [
                    {'name': p.name, 'quantity': p.quantity}
                    for p in prods
                ]
                for cat, prods in by_category.items()
            },
            'summary': summary
        }


# ============================================================
# API HANDLER FOR VERCEL
# ============================================================

def get_production_inventory():
    """
    Get current production inventory.
    Called by Vercel API route.
    """
    client = BlackTieSheetsClient()
    return client.get_all_inventory()


# For local testing
if __name__ == "__main__":
    # This won't work without credentials, but shows the interface
    print("BlackTieSheetsClient - Auto-detect tabs demo")
    print("=" * 50)
    print("""
To use this client:

1. Set environment variables:
   - GOOGLE_SHEETS_SPREADSHEET_ID
   - GCP_PROJECT_ID
   - GCP_CLIENT_EMAIL
   - GCP_PRIVATE_KEY

2. Call get_production_inventory() to get all inventory data

The client will automatically:
- Discover all tabs in the spreadsheet
- Identify which are inventory tabs
- Detect the format of each tab
- Parse products from all inventory tabs
""")
