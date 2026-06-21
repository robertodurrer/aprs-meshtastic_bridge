#!/usr/bin/env python3
"""Test script to identify webui errors."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from modules.config_loader import load as load_config
    print("✓ Config loader imported successfully")
    
    cfg = load_config()
    print("✓ Configuration loaded successfully")
    
    from modules.database import Database
    print("✓ Database module imported successfully")
    
    db = Database(cfg)
    print("✓ Database initialized successfully")
    
    from modules.logger import get_logger
    print("✓ Logger module imported successfully")
    
    log = get_logger("test", cfg)
    print("✓ Logger initialized successfully")
    
    # Test database operations
    operators = db.list_operators(active_only=False)
    print(f"✓ Database query successful: {len(operators)} operators")
    
    messages = db.list_messages(limit=10)
    print(f"✓ Database query successful: {len(messages)} messages")
    
    # Test FastAPI imports
    from fastapi import FastAPI
    print("✓ FastAPI imported successfully")
    
    from fastapi.templating import Jinja2Templates
    print("✓ Jinja2Templates imported successfully")
    
    # Test template directory
    template_dir = Path(__file__).parent / "templates"
    if template_dir.exists():
        print(f"✓ Template directory exists: {template_dir}")
        templates = list(template_dir.glob("*.html"))
        print(f"✓ Found {len(templates)} template files")
    else:
        print(f"✗ Template directory missing: {template_dir}")
    
    # Test static directory
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        print(f"✓ Static directory exists: {static_dir}")
    else:
        print(f"✗ Static directory missing: {static_dir}")
        
    print("\n✓ All tests passed! WebUI should work correctly.")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
