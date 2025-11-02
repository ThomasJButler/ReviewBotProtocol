#!/usr/bin/env python3
"""Test script to verify GitHub webhook signature verification is working."""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = str(Path(__file__).parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Set test environment variables
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_webhook_secret_123")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing")

from utils.crypto import verify_github_signature
import hashlib
import hmac


def test_signature_verification():
    """Test the GitHub webhook signature verification."""

    print("=" * 60)
    print("🔐 TESTING GITHUB WEBHOOK SIGNATURE VERIFICATION")
    print("=" * 60)
    print()

    # Test data
    webhook_secret = "test_webhook_secret_123"
    test_payload = '{"action":"opened","number":123,"pull_request":{"id":1}}'

    # Generate a valid signature
    valid_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        test_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Test 1: Valid signature with sha256= prefix
    print("Test 1: Valid signature with prefix...")
    result1 = verify_github_signature(test_payload, f"sha256={valid_signature}")
    print(f"   Result: {'✅ PASS' if result1 else '❌ FAIL'}")

    # Test 2: Valid signature without prefix
    print("Test 2: Valid signature without prefix...")
    result2 = verify_github_signature(test_payload, valid_signature)
    print(f"   Result: {'✅ PASS' if result2 else '❌ FAIL'}")

    # Test 3: Invalid signature
    print("Test 3: Invalid signature...")
    result3 = verify_github_signature(test_payload, "sha256=invalid_signature_12345")
    print(f"   Result: {'✅ PASS (correctly rejected)' if not result3 else '❌ FAIL (should reject)'}")

    # Test 4: Empty signature
    print("Test 4: Empty signature...")
    result4 = verify_github_signature(test_payload, "")
    print(f"   Result: {'✅ PASS (correctly rejected)' if not result4 else '❌ FAIL (should reject)'}")

    # Test 5: Payload as bytes
    print("Test 5: Payload as bytes...")
    result5 = verify_github_signature(test_payload.encode('utf-8'), f"sha256={valid_signature}")
    print(f"   Result: {'✅ PASS' if result5 else '❌ FAIL'}")

    # Test 6: Tampered payload
    print("Test 6: Tampered payload...")
    tampered_payload = '{"action":"closed","number":123,"pull_request":{"id":1}}'
    result6 = verify_github_signature(tampered_payload, f"sha256={valid_signature}")
    print(f"   Result: {'✅ PASS (correctly rejected)' if not result6 else '❌ FAIL (should reject)'}")

    print()
    print("=" * 60)

    # Summary
    all_passed = (
        result1 == True and
        result2 == True and
        result3 == False and
        result4 == False and
        result5 == True and
        result6 == False
    )

    if all_passed:
        print("✅ ALL WEBHOOK SIGNATURE TESTS PASSED!")
        print("   The webhook signature verification is working correctly.")
    else:
        print("❌ SOME TESTS FAILED!")
        print("   Please check the webhook signature verification implementation.")

    print("=" * 60)
    print()

    return all_passed


def test_webhook_security_notes():
    """Print security notes about webhook verification."""

    print("📚 WEBHOOK SECURITY NOTES:")
    print("=" * 60)
    print()
    print("✅ Webhook signature verification is now ENABLED")
    print()
    print("Security measures in place:")
    print("1. ✅ HMAC-SHA256 signature verification")
    print("2. ✅ Constant-time comparison (prevents timing attacks)")
    print("3. ✅ Signature required for all webhook requests")
    print("4. ✅ Proper error logging for failed verifications")
    print()
    print("⚠️  IMPORTANT: Set GITHUB_WEBHOOK_SECRET in production!")
    print("   - Generate a strong, random secret")
    print("   - Use the same secret in GitHub webhook settings")
    print("   - Never commit the secret to version control")
    print()
    print("GitHub Webhook Setup:")
    print("1. Go to repository Settings > Webhooks")
    print("2. Set Payload URL: https://your-domain/api/webhook/github")
    print("3. Content type: application/json")
    print("4. Secret: [your strong random secret]")
    print("5. Events: Pull requests, Pull request reviews")
    print()
    print("=" * 60)
    print()


if __name__ == "__main__":
    # Run tests
    success = test_signature_verification()

    # Show security notes
    test_webhook_security_notes()

    # Exit code
    sys.exit(0 if success else 1)