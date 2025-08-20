#!/usr/bin/env python3

import os
import sys
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Disable all logging
logging.disable(logging.CRITICAL)

from app import create_app
from extensions.db import db
from sqlalchemy import text, inspect

def check_products_structure():
    """Check the structure and data of Product and CVEProduct tables."""
    app = create_app()
    
    results = []
    
    with app.app_context():
        inspector = inspect(db.engine)
        
        results.append("=== CHECKING PRODUCTS STRUCTURE ===")
        
        # Check if Product table exists
        if 'product' in inspector.get_table_names():
            results.append("✓ Product table exists")
            
            # Get Product table columns
            product_columns = inspector.get_columns('product')
            results.append(f"Product table columns: {[col['name'] for col in product_columns]}")
            
            # Count products
            product_count = db.session.execute(text("SELECT COUNT(*) FROM product")).scalar()
            results.append(f"Total products: {product_count}")
            
            # Sample products
            if product_count > 0:
                sample_products = db.session.execute(text("SELECT id, name FROM product LIMIT 5")).fetchall()
                results.append("Sample products:")
                for product in sample_products:
                    results.append(f"  ID: {product[0]}, Name: {product[1]}")
        else:
            results.append("✗ Product table does not exist")
        
        # Check if CVEProduct table exists
        if 'cve_product' in inspector.get_table_names():
            results.append("\n✓ CVEProduct table exists")
            
            # Get CVEProduct table columns
            cve_product_columns = inspector.get_columns('cve_product')
            results.append(f"CVEProduct table columns: {[col['name'] for col in cve_product_columns]}")
            
            # Count CVE-Product relationships
            cve_product_count = db.session.execute(text("SELECT COUNT(*) FROM cve_product")).scalar()
            results.append(f"Total CVE-Product relationships: {cve_product_count}")
            
            # Sample CVE-Product relationships
            if cve_product_count > 0:
                sample_cve_products = db.session.execute(text("SELECT cve_id, product_id FROM cve_product LIMIT 5")).fetchall()
                results.append("Sample CVE-Product relationships:")
                for rel in sample_cve_products:
                    results.append(f"  CVE: {rel[0]}, Product ID: {rel[1]}")
        else:
            results.append("\n✗ CVEProduct table does not exist")
        
        # Check if affected_products table exists (alternative)
        if 'affected_products' in inspector.get_table_names():
            results.append("\n✓ AffectedProducts table exists")
            
            # Get AffectedProducts table columns
            affected_products_columns = inspector.get_columns('affected_products')
            results.append(f"AffectedProducts table columns: {[col['name'] for col in affected_products_columns]}")
            
            # Count affected products
            affected_products_count = db.session.execute(text("SELECT COUNT(*) FROM affected_products")).scalar()
            results.append(f"Total affected products: {affected_products_count}")
            
            # Sample affected products
            if affected_products_count > 0:
                sample_affected = db.session.execute(text("SELECT cve_id, product_name FROM affected_products LIMIT 5")).fetchall()
                results.append("Sample affected products:")
                for affected in sample_affected:
                    results.append(f"  CVE: {affected[0]}, Product: {affected[1]}")
                    
                # Count unique products in affected_products
                unique_products = db.session.execute(text("SELECT COUNT(DISTINCT product_name) FROM affected_products")).scalar()
                results.append(f"Unique product names in affected_products: {unique_products}")
        else:
            results.append("\n✗ AffectedProducts table does not exist")
        
        # Test the actual query used in analytics
        results.append("\n=== TESTING ANALYTICS QUERY ===")
        try:
            from models.product import Product
            from models.cve_product import CVEProduct
            from sqlalchemy import func, desc
            
            query_results = db.session.query(
                Product.name,
                func.count(CVEProduct.cve_id).label('count')
            ).join(
                CVEProduct, Product.id == CVEProduct.product_id
            ).group_by(
                Product.name
            ).order_by(
                desc('count')
            ).limit(10).all()
            
            results.append(f"Analytics query returned {len(query_results)} results")
            if query_results:
                results.append("Top products from analytics query:")
                for result in query_results:
                    results.append(f"  Product: {result.name}, Count: {result.count}")
            else:
                results.append("No results from analytics query")
                
        except Exception as e:
            results.append(f"Error in analytics query: {str(e)}")
    
    # Save results to file
    with open('products_results.txt', 'w', encoding='utf-8') as f:
        for line in results:
            f.write(line + '\n')
    
    # Print results
    for line in results:
        print(line)

if __name__ == '__main__':
    check_products_structure()