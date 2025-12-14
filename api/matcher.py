"""
Product Matching Service
Fuzzy matches POS products to Production inventory
"""

import re
from dataclasses import dataclass
from typing import Optional
from rapidfuzz import fuzz


@dataclass
class MatchResult:
    """Result of matching a POS product to Production"""
    pos_name: str
    pos_type: str
    pos_quantity: float
    production_name: Optional[str]
    production_quantity: Optional[float]
    production_category: Optional[str]
    similarity_score: float
    confidence: str  # 'auto', 'review', 'none'


class ProductMatcher:
    """Fuzzy matches POS products to Production inventory"""
    
    AUTO_THRESHOLD = 90
    REVIEW_THRESHOLD = 70
    
    # Map POS types to production categories
    POS_TYPE_MAP = {
        'badder house': 'Badder',
        'badder house (baller)': 'Badder',
        'badder (baller)': 'Badder',
        'badder': 'Badder',
        'shatter': 'Shatter',
        'sugar': 'Sugar',
        'live resin': 'Live Resin',
        'resin': 'Live Resin',
        'cart': 'Full Spec Oil',
        'pre roll': 'Prerolls',
        'pre roll 2': 'Prerolls',
        'pre roll pack': 'Prerolls',
        'pre roll infused': 'Prerolls',
        'flower': 'Flower',
        'rosin': 'Rosin',
        'hash rosin': 'Rosin',
        'diamonds': 'Diamonds',
    }
    
    def __init__(self, confirmed_matches: dict = None, rejected_matches: set = None):
        """
        Initialize matcher with optional learning data.
        
        Args:
            confirmed_matches: Dict of {pos_normalized: production_normalized}
            rejected_matches: Set of (pos_norm, prod_norm) tuples
        """
        self.confirmed_matches = confirmed_matches or {}
        self.rejected_matches = rejected_matches or set()
    
    def normalize(self, name: str) -> str:
        """Normalize product name for matching"""
        if not name:
            return ""
        
        n = name.lower().strip()
        
        # Remove parenthetical content
        n = re.sub(r'\([^)]*\)', '', n)
        
        # Remove common prefixes/suffixes
        n = re.sub(r'\b(bt|black tie|7g|1g|2g)\b', '', n)
        
        # Remove special chars
        n = re.sub(r'[^a-z0-9\s]', '', n)
        
        # Collapse whitespace
        n = re.sub(r'\s+', ' ', n).strip()
        
        return n
    
    def get_production_category(self, pos_type: str, pos_name: str = "") -> Optional[str]:
        """Map POS product to category. Name takes precedence over type."""
        name_lower = pos_name.lower()
        
        # Check name first
        if "badder" in name_lower or "baller" in name_lower:
            return "Badder"
        if "shatter" in name_lower:
            return "Shatter"
        if "sugar" in name_lower:
            return "Sugar"
        if "live resin" in name_lower:
            return "Live Resin"
        if "rosin" in name_lower:
            return "Rosin"
        if "diamond" in name_lower:
            return "Diamonds"
        if "preroll" in name_lower or "pre roll" in name_lower or "pre-roll" in name_lower:
            return "Prerolls"
        if "cart" in name_lower or "full spec" in name_lower:
            return "Full Spec Oil"
        
        # Check type second
        if pos_type:
            mapped = self.POS_TYPE_MAP.get(pos_type.lower().strip())
            if mapped:
                return mapped
        
        # Default to Flower
        return "Flower"
    
    def match_product(
        self,
        pos_name: str,
        pos_type: str,
        pos_quantity: float,
        production_products: list[dict]
    ) -> MatchResult:
        """
        Find best production match for a POS product.
        
        Args:
            pos_name: Product name from POS
            pos_type: Product type from POS
            pos_quantity: Quantity in POS
            production_products: List of dicts with 'name', 'quantity', 'category'
        
        Returns:
            MatchResult with best match details
        """
        pos_norm = self.normalize(pos_name)
        pos_category = self.get_production_category(pos_type, pos_name)
        
        # Check confirmed matches first
        if pos_norm in self.confirmed_matches:
            confirmed_prod_norm = self.confirmed_matches[pos_norm]
            for prod in production_products:
                if self.normalize(prod['name']) == confirmed_prod_norm:
                    return MatchResult(
                        pos_name=pos_name,
                        pos_type=pos_type,
                        pos_quantity=pos_quantity,
                        production_name=prod['name'],
                        production_quantity=prod['quantity'],
                        production_category=prod['category'],
                        similarity_score=100,
                        confidence='auto'
                    )
        
        # Filter to same category - no fallback to other categories
        if pos_category:
            candidates = [p for p in production_products if p.get('category') == pos_category]
        else:
            candidates = production_products
        
        # Find best match
        best_match = None
        best_score = 0
        
        for prod in candidates:
            prod_norm = self.normalize(prod['name'])
            
            # Skip rejected matches
            if (pos_norm, prod_norm) in self.rejected_matches:
                continue
            
            # Calculate similarity
            score = fuzz.token_set_ratio(pos_norm, prod_norm)
            
            # Boost for category match
            if prod.get('category') == pos_category:
                score = min(100, score + 5)
            
            if score > best_score:
                best_score = score
                best_match = prod
        
        # Determine confidence
        if best_score >= self.AUTO_THRESHOLD:
            confidence = 'auto'
        elif best_score >= self.REVIEW_THRESHOLD:
            confidence = 'review'
        else:
            confidence = 'none'
        
        return MatchResult(
            pos_name=pos_name,
            pos_type=pos_type,
            pos_quantity=pos_quantity,
            production_name=best_match['name'] if best_match and best_score >= self.REVIEW_THRESHOLD else None,
            production_quantity=best_match['quantity'] if best_match and best_score >= self.REVIEW_THRESHOLD else None,
            production_category=best_match.get('category') if best_match and best_score >= self.REVIEW_THRESHOLD else None,
            similarity_score=best_score,
            confidence=confidence
        )
    
    def match_inventory(
        self,
        pos_products: list[dict],
        production_products: list[dict]
    ) -> dict:
        """
        Match all POS products against production inventory.
        
        Args:
            pos_products: List of dicts with 'name', 'type', 'quantity'
            production_products: List of dicts with 'name', 'quantity', 'category'
        
        Returns:
            Dict with 'auto_matched', 'needs_review', 'unmatched', 'production_only'
        """
        results = {
            'auto_matched': [],
            'needs_review': [],
            'unmatched': [],
            'production_only': []
        }
        
        matched_production = set()
        
        for pos in pos_products:
            result = self.match_product(
                pos['name'],
                pos.get('type', ''),
                pos.get('quantity', 0),
                production_products
            )
            
            result_dict = {
                'pos_name': result.pos_name,
                'pos_type': result.pos_type,
                'pos_quantity': result.pos_quantity,
                'production_name': result.production_name,
                'production_quantity': result.production_quantity,
                'production_category': result.production_category,
                'similarity_score': result.similarity_score,
                'confidence': result.confidence
            }
            
            if result.confidence == 'auto':
                results['auto_matched'].append(result_dict)
                if result.production_name:
                    matched_production.add((result.production_name, result.production_category))
            elif result.confidence == 'review':
                results['needs_review'].append(result_dict)
            else:
                results['unmatched'].append(result_dict)
        
        # Find production-only products
        for prod in production_products:
            if (prod['name'], prod.get('category')) not in matched_production:
                # Check if it's in needs_review
                in_review = any(
                    r['production_name'] == prod['name'] 
                    for r in results['needs_review']
                )
                if not in_review and prod.get('quantity', 0) > 0:
                    results['production_only'].append({
                        'production_name': prod['name'],
                        'production_quantity': prod['quantity'],
                        'production_category': prod.get('category'),
                        'reason': 'Not in POS inventory'
                    })
        
        return results
