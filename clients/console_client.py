"""Simple chat client for Multi-Agent Post Generator API"""

import requests
from datetime import datetime

API_URL = "http://localhost:8000"

def chat(query: str):
    """Send a chat query to the API"""
    user_id = f"demo-user-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"\n🤖 Generating post about: {query}")
    print(f"   User: {user_id}\n")
    
    try:
        response = requests.post(
            f"{API_URL}/chat",
            json={"user_id": user_id, "query": query},
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print("=" * 80)
            print(result.get("post", ""))
            print("=" * 80)
            return result
        else:
            print(f"❌ Error {response.status_code}: {response.json().get('message')}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    """Run interactive chat loop"""
    print("\n" + "=" * 80)
    print("Multi-Agent Post Generator - Chat Client")
    print("=" * 80)
    
    # Check API health
    try:
        health = requests.get(f"{API_URL}/health", timeout=5).json()
        print(f"✅ API is {health['status']} (v{health['version']})\n")
    except:
        print(f"❌ Cannot connect to API at {API_URL}")
        print("   Start the API with: python -m api.main\n")
        return
    
    # Chat loop
    while True:
        query = input("\nYour topic (or 'quit' to exit): ").strip()
        
        if not query or query.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!\n")
            break
        
        chat(query)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
