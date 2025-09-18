#!/usr/bin/env python3
"""Test script to debug settings import issues."""

try:
    print("Testing imports...")

    print("1. Testing pydantic_settings import...")
    from pydantic_settings import BaseSettings
    print("✅ pydantic_settings imported successfully")

    print("2. Testing pydantic field_validator import...")
    from pydantic import field_validator
    print("✅ field_validator imported successfully")

    print("3. Testing settings module import...")
    from config.settings import Settings
    print("✅ Settings class imported successfully")

    print("4. Testing settings instantiation...")
    settings = Settings()
    print("✅ Settings instantiated successfully")

    print("\n🎉 All tests passed!")
    print(f"Debug mode: {settings.DEBUG}")
    print(f"Allowed origins: {settings.ALLOWED_ORIGINS}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()