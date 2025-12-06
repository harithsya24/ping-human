"""Test script to verify contact management and conversation intelligence features."""
import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:5001/api")
BASE_URL = os.getenv("SERIES_API_BASE_URL", "")

def test_api_health():
    """Test if API is running."""
    print("\n" + "="*60)
    print("1. Testing API Health")
    print("="*60)
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is running!")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Is the backend running?")
        print("   Start it with: python backend/app.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_contacts():
    """Test contact management."""
    print("\n" + "="*60)
    print("2. Testing Contact Management")
    print("="*60)
    try:
        # Get all contacts
        response = requests.get(f"{API_URL}/contacts", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Contacts endpoint working!")
            print(f"   Found {data.get('count', 0)} contacts")
            return True
        else:
            print(f"⚠️  Contacts endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  Contact test error: {e}")
        return False

def test_conversations():
    """Test conversation tracking."""
    print("\n" + "="*60)
    print("3. Testing Conversation Tracking")
    print("="*60)
    try:
        # Get all conversations
        response = requests.get(f"{API_URL}/conversations", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Conversations endpoint working!")
            print(f"   Found {len(data)} active conversations")
            
            # Test pending replies
            response2 = requests.get(f"{API_URL}/conversations/pending", timeout=5)
            if response2.status_code == 200:
                pending = response2.json()
                print(f"✅ Pending replies endpoint working!")
                print(f"   {pending.get('count', 0)} conversations need replies")
            return True
        else:
            print(f"⚠️  Conversations endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  Conversation test error: {e}")
        return False

def test_next_message(chat_id="test_chat_123"):
    """Test next message generation."""
    print("\n" + "="*60)
    print("4. Testing Next Message Generation")
    print("="*60)
    try:
        response = requests.get(
            f"{API_URL}/conversations/{chat_id}/next_message",
            params={"contact_name": "Test User"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Next message generation working!")
            print(f"   Suggested: {data.get('suggested_message', 'N/A')[:100]}...")
            return True
        else:
            print(f"⚠️  Next message endpoint returned {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"⚠️  Next message test error: {e}")
        return False

def test_decision_support(chat_id="test_chat_123"):
    """Test decision support."""
    print("\n" + "="*60)
    print("5. Testing Decision Support")
    print("="*60)
    try:
        # Test conversation state
        response = requests.get(
            f"{API_URL}/conversations/{chat_id}/state",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Conversation state analysis working!")
            print(f"   Recommendation: {data.get('recommendation', 'N/A')}")
            print(f"   Priority: {data.get('priority', 'N/A')}")
            return True
        else:
            print(f"⚠️  Decision support returned {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  Decision support test error: {e}")
        return False

def test_stats():
    """Test stats endpoint."""
    print("\n" + "="*60)
    print("6. Testing Stats Endpoint")
    print("="*60)
    try:
        response = requests.get(f"{API_URL}/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Stats endpoint working!")
            print(f"   Total messages: {data.get('total_messages', 0)}")
            print(f"   Total responses: {data.get('total_responses', 0)}")
            print(f"   Unique users: {data.get('unique_users', 0)}")
            print(f"   Active conversations: {data.get('active_conversations', 0)}")
            return True
        else:
            print(f"⚠️  Stats endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  Stats test error: {e}")
        return False

def check_bot_service():
    """Check if bot service is running."""
    print("\n" + "="*60)
    print("7. Checking Bot Service Status")
    print("="*60)
    print("⚠️  Bot service check requires manual verification.")
    print("   Look for these indicators:")
    print("   - Bot service process running (python backend/bot_service.py)")
    print("   - Kafka consumer connected")
    print("   - Messages being processed when you send to +16463769330")
    print("\n   To test:")
    print("   1. Send a message to +16463769330")
    print("   2. Check bot service logs for:")
    print("      - Contact name detection")
    print("      - Conversation thread tracking")
    print("      - Reply detection")
    print("      - AI response generation")

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PINGHUMANS FEATURE TEST SUITE")
    print("="*60)
    print(f"Testing API at: {API_URL}")
    print("\nMake sure the backend is running:")
    print("  python backend/app.py")
    print("\nPress Ctrl+C to skip tests...")
    time.sleep(2)
    
    results = []
    
    # Run tests
    results.append(("API Health", test_api_health()))
    results.append(("Contacts", test_contacts()))
    results.append(("Conversations", test_conversations()))
    results.append(("Next Message", test_next_message()))
    results.append(("Decision Support", test_decision_support()))
    results.append(("Stats", test_stats()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All API tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
    
    check_bot_service()
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Start bot service: python backend/bot_service.py")
    print("2. Send a test message to +16463769330")
    print("3. Check bot logs for contact tracking and reply detection")
    print("4. View dashboard at: http://localhost:5001")
    print("5. Test API endpoints using the URLs above")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()

