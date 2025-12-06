#!/usr/bin/env python3
"""Quick test to verify routes are working."""
import requests
import sys

API_URL = "http://localhost:5001/api"

def test_route(url, description):
    """Test a single route."""
    try:
        response = requests.get(url, timeout=5)
        print(f"\n{description}")
        print(f"  URL: {url}")
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  ✅ Success!")
            try:
                data = response.json()
                print(f"  Response: {str(data)[:100]}...")
            except:
                print(f"  Response: {response.text[:100]}...")
            return True
        else:
            print(f"  ❌ Failed: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"\n{description}")
        print(f"  ❌ Cannot connect to server. Is it running?")
        print(f"  Start with: python backend/app.py")
        return False
    except Exception as e:
        print(f"\n{description}")
        print(f"  ❌ Error: {e}")
        return False

def main():
    print("="*60)
    print("ROUTE VERIFICATION TEST")
    print("="*60)
    print(f"\nTesting API at: {API_URL}")
    print("\nMake sure the backend is running:")
    print("  python backend/app.py")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return
    
    results = []
    
    # Test basic routes
    results.append(("Health Check", test_route(f"{API_URL}/health", "1. Health Check")))
    results.append(("Contacts", test_route(f"{API_URL}/contacts", "2. Contacts Endpoint")))
    results.append(("Conversations", test_route(f"{API_URL}/conversations", "3. Conversations Endpoint")))
    results.append(("Next Message", test_route(f"{API_URL}/conversations/123/next_message?contact_name=Test", "4. Next Message Endpoint")))
    results.append(("Conversation State", test_route(f"{API_URL}/conversations/123/state", "5. Conversation State Endpoint")))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All routes are working!")
    else:
        print("\n⚠️  Some routes failed. Make sure:")
        print("   1. Backend server is running: python backend/app.py")
        print("   2. Server was restarted after adding new routes")
        print("   3. No import errors in server logs")

if __name__ == "__main__":
    main()

