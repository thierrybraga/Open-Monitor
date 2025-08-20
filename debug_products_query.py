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
from sqlalchemy import text, func, desc

def debug_products_query():
    """Debug the products query to understand why it's not working."""
    app = create_app()
    
    results = []
    
    with app.app_context():
        results.append("=== DEBUGGING PRODUCTS QUERY ===")
        
        # Test 1: Check if there are any matching IDs between tables
        results.append("\n1. Checking ID overlap between product and cve_product tables:")
        
        # Get some product IDs
        product_ids = db.session.execute(text("SELECT id FROM product LIMIT 10")).fetchall()
        results.append(f"Sample product IDs: {[p[0] for p in product_ids]}")
        
        # Get some cve_product product_ids
        cve_product_ids = db.session.execute(text("SELECT DISTINCT product_id FROM cve_product LIMIT 10")).fetchall()
        results.append(f"Sample cve_product product_ids: {[p[0] for p in cve_product_ids]}")
        
        # Check if there's any overlap
        overlap_count = db.session.execute(text("""
            SELECT COUNT(*) FROM product p 
            INNER JOIN cve_product cp ON p.id = cp.product_id
        """)).scalar()
        results.append(f"Records with matching IDs: {overlap_count}")
        
        # Test 2: Try raw SQL query
        results.append("\n2. Testing raw SQL query:")
        try:
            raw_results = db.session.execute(text("""
                SELECT p.name, COUNT(cp.cve_id) as count
                FROM product p
                INNER JOIN cve_product cp ON p.id = cp.product_id
                GROUP BY p.name
                ORDER BY count DESC
                LIMIT 10
            """)).fetchall()
            
            results.append(f"Raw SQL query returned {len(raw_results)} results")
            if raw_results:
                results.append("Top products from raw SQL:")
                for result in raw_results:
                    results.append(f"  Product: {result[0]}, Count: {result[1]}")
            else:
                results.append("No results from raw SQL query")
        except Exception as e:
            results.append(f"Error in raw SQL query: {str(e)}")
        
        # Test 3: Try using affected_products table instead
        results.append("\n3. Checking affected_products table structure:")
        try:
            # Check if affected_products has data
            affected_count = db.session.execute(text("SELECT COUNT(*) FROM affected_products")).scalar()
            results.append(f"Total records in affected_products: {affected_count}")
            
            if affected_count > 0:
                # Try to get product names from affected_products
                affected_sample = db.session.execute(text("""
                    SELECT product_id, affected_versions FROM affected_products LIMIT 5
                """)).fetchall()
                results.append("Sample affected_products data:")
                for sample in affected_sample:
                    results.append(f"  Product ID: {sample[0]}, Versions: {sample[1]}")
        except Exception as e:
            results.append(f"Error checking affected_products: {str(e)}")
        
        # Test 4: Check if we should use a different approach
        results.append("\n4. Alternative approach - using vulnerabilities table:")
        try:
            # Check if vulnerabilities table has product information
            vuln_sample = db.session.execute(text("""
                SELECT id, cve_id FROM vulnerabilities LIMIT 5
            """)).fetchall()
            results.append("Sample vulnerabilities data:")
            for vuln in vuln_sample:
                results.append(f"  ID: {vuln[0]}, CVE: {vuln[1]}")
                
            # Check if we can get products through affected_products -> vulnerabilities
            alt_query = db.session.execute(text("""
                SELECT v.cve_id, ap.product_id
                FROM vulnerabilities v
                INNER JOIN affected_products ap ON v.id = ap.vulnerability_id
                LIMIT 5
            """)).fetchall()
            results.append(f"Alternative query returned {len(alt_query)} results")
            if alt_query:
                results.append("Sample alternative query results:")
                for result in alt_query:
                    results.append(f"  CVE: {result[0]}, Product ID: {result[1]}")
        except Exception as e:
            results.append(f"Error in alternative approach: {str(e)}")
    
    # Save results to file
    with open('debug_products_results.txt', 'w', encoding='utf-8') as f:
        for line in results:
            f.write(line + '\n')
    
    # Print results
    for line in results:
        print(line)

if __name__ == '__main__':
    debug_products_query()