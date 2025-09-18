#!/usr/bin/env python3
"""
Test runner for Git Review Assistant Backend

This script runs the comprehensive test suite and provides detailed reporting.
"""

import subprocess
import sys
import time
import os
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return the result."""
    print(f"\n🔄 {description}...")
    print(f"Running: {' '.join(cmd)}")

    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()

    duration = end_time - start_time

    if result.returncode == 0:
        print(f"✅ {description} completed successfully ({duration:.2f}s)")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ {description} failed ({duration:.2f}s)")
        if result.stderr:
            print("STDERR:", result.stderr)
        if result.stdout:
            print("STDOUT:", result.stdout)

    return result


def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking test dependencies...")

    required_packages = [
        "pytest",
        "pytest-asyncio",
        "httpx",
        "fastapi"
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} is missing")

    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Install them with: pip install " + " ".join(missing_packages))
        return False

    return True


def run_tests():
    """Run the test suite with different configurations."""
    print("\n🧪 Starting Git Review Assistant Backend Test Suite")
    print("=" * 60)

    # Check if we're in the right directory
    if not Path("tests").exists():
        print("❌ Tests directory not found. Make sure you're in the backend directory.")
        return False

    # Check dependencies
    if not check_dependencies():
        return False

    # Test configurations to run
    test_configs = [
        {
            "name": "Quick Health Check Tests",
            "cmd": ["python", "-m", "pytest", "tests/test_health.py", "-v"],
            "description": "Running basic health and API tests"
        },
        {
            "name": "Authentication Tests",
            "cmd": ["python", "-m", "pytest", "tests/test_auth.py", "-v"],
            "description": "Running authentication and security tests"
        },
        {
            "name": "Webhook Tests",
            "cmd": ["python", "-m", "pytest", "tests/test_webhook.py", "-v"],
            "description": "Running GitHub webhook processing tests"
        },
        {
            "name": "Review Engine Tests",
            "cmd": ["python", "-m", "pytest", "tests/test_review.py", "-v"],
            "description": "Running code review functionality tests"
        },
        {
            "name": "Full Test Suite",
            "cmd": ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
            "description": "Running complete test suite"
        }
    ]

    results = []

    for config in test_configs:
        print(f"\n{'='*60}")
        print(f"📋 {config['name']}")
        print('='*60)

        result = run_command(config["cmd"], config["description"])
        results.append({
            "name": config["name"],
            "success": result.returncode == 0,
            "returncode": result.returncode
        })

        if result.returncode != 0:
            print(f"⚠️  {config['name']} had failures - continuing with other tests...")

    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print('='*60)

    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["success"])
    failed_tests = total_tests - passed_tests

    for result in results:
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        print(f"{status} - {result['name']}")

    print(f"\n📈 Results: {passed_tests}/{total_tests} test suites passed")

    if failed_tests > 0:
        print(f"⚠️  {failed_tests} test suite(s) had failures")
        print("\n💡 Common issues and solutions:")
        print("   • Missing environment variables: Check .env file")
        print("   • Database connection: Ensure SQLite is working")
        print("   • Authentication mocks: Some tests mock external services")
        print("   • Async tests: Ensure pytest-asyncio is installed")
        return False
    else:
        print("🎉 All test suites passed!")
        return True


def run_with_coverage():
    """Run tests with coverage reporting."""
    print("\n📊 Running tests with coverage...")

    coverage_cmd = [
        "python", "-m", "pytest",
        "tests/",
        "--cov=.",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-fail-under=70",
        "-v"
    ]

    result = run_command(coverage_cmd, "Running tests with coverage")

    if result.returncode == 0:
        print("\n📋 Coverage report generated in htmlcov/index.html")

    return result.returncode == 0


def main():
    """Main test runner."""
    print("🚀 Git Review Assistant Backend Test Runner")

    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Virtual environment not detected. Recommended to run in .venv")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return 1

    # Run basic tests
    success = run_tests()

    if success:
        # Ask if user wants coverage report
        response = input("\n🔍 Run tests with coverage report? (y/N): ")
        if response.lower() == 'y':
            run_with_coverage()

    print(f"\n{'='*60}")
    print("🏁 Test run completed!")
    print('='*60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())