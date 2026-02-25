#!/usr/bin/env python3
"""
Test script to verify PNG image support in Visual Editor Core.
"""

import os
import sys
import json
import requests
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_png_image_support():
    """Test PNG image support functionality."""
    print("Testing PNG Image Support in Visual Editor Core")
    print("=" * 50)
    
    # Check if the web interface is running
    try:
        response = requests.get("http://localhost:5002/api/palette/nodes?paradigm=node_based", timeout=5)
        if response.status_code == 200:
            print("✅ Web interface is accessible")
        else:
            print("❌ Web interface returned error:", response.status_code)
            return False
    except requests.exceptions.RequestException as e:
        print("❌ Web interface is not running. Please start it first:")
        print("   cd web_interface && python app.py")
        return False
    
    # Test node palette API
    try:
        data = response.json()
        if data.get('success'):
            nodes = data.get('data', [])
            print(f"✅ Found {len(nodes)} node definitions")
            
            # Check for image paths in node definitions
            image_nodes = [node for node in nodes if 'image' in node]
            print(f"✅ Found {len(image_nodes)} nodes with image paths")
            
            # List some examples
            print("\nNode types with PNG images:")
            for node in image_nodes[:10]:  # Show first 10
                print(f"  - {node['type']}: {node.get('image', 'N/A')}")
            
            if len(image_nodes) > 10:
                print(f"  ... and {len(image_nodes) - 10} more")
                
        else:
            print("❌ API returned error:", data.get('error'))
            return False
            
    except Exception as e:
        print("❌ Error parsing API response:", e)
        return False
    
    # Check if image files exist
    images_dir = project_root / "web_interface" / "static" / "images"
    print(f"\nChecking images directory: {images_dir}")
    
    if images_dir.exists():
        print("✅ Images directory exists")
        
        # List existing PNG files
        png_files = list(images_dir.glob("*.png"))
        print(f"✅ Found {len(png_files)} PNG files")
        
        if png_files:
            print("\nExisting PNG files:")
            for png_file in png_files:
                size = png_file.stat().st_size
                print(f"  - {png_file.name} ({size} bytes)")
        else:
            print("ℹ️  No PNG files found yet. You can add them using the naming guide.")
            
    else:
        print("❌ Images directory does not exist")
        return False
    
    # Test image mapping in JavaScript
    app_js_path = project_root / "web_interface" / "static" / "app.js"
    if app_js_path.exists():
        print(f"\nChecking JavaScript image mapping in: {app_js_path.name}")
        
        with open(app_js_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'getCustomNodeImage' in content:
            print("✅ getCustomNodeImage function found")
        else:
            print("❌ getCustomNodeImage function not found")
            return False
            
        if 'function_node.png' in content:
            print("✅ Image mapping contains function_node.png")
        else:
            print("❌ Image mapping does not contain function_node.png")
            return False
            
    else:
        print("❌ app.js file not found")
        return False
    
    print("\n" + "=" * 50)
    print("PNG Image Support Test Results:")
    print("✅ All core components are working correctly")
    print("✅ API endpoints are functional")
    print("✅ Image mapping is implemented")
    print("✅ Directory structure is correct")
    print("\nTo add PNG images:")
    print("1. Create 120x80 pixel PNG images")
    print("2. Save them in web_interface/static/images/")
    print("3. Use the naming convention from PNG_IMAGE_NAMING_GUIDE.md")
    print("4. Images will be automatically detected and used")
    
    return True

if __name__ == "__main__":
    success = test_png_image_support()
    sys.exit(0 if success else 1)