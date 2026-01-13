import urllib.request
import json
import uuid
import sys

# Configuration - verified values from deployment
API_ENDPOINT = "https://xti52i5mqb.execute-api.eu-west-1.amazonaws.com/Prod/chat"
API_KEY = "zvkcXMflV05gQuUsAkVoJ8m8qmixO4d534kDhKp5"

# Generate a random session ID for this run
SESSION_USER_ID = f"test_user_{str(uuid.uuid4())[:8]}"

def chat_with_bot(query):
    """Sends a query to the chatbot API and returns the response."""
    payload = {
        "query": query,
        "user_id": SESSION_USER_ID
    }
    
    data = json.dumps(payload).encode('utf-8')
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "User-Agent": "ChamaTestScript/1.0"
    }
    
    req = urllib.request.Request(API_ENDPOINT, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_body = response.read().decode('utf-8')
                return json.loads(response_body)
            else:
                return {"error": f"HTTP {response.status}: {response.reason}"}
    except urllib.request.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return {"error": f"HTTP {e.code}: {e.reason}", "details": error_body}
    except Exception as e:
        return {"error": str(e)}

def main():
    print("="*60)
    print("🤖 Chama Chatbot Interactive Test")
    print(f"Endpoint: {API_ENDPOINT}")
    print(f"Session ID: {SESSION_USER_ID}")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("="*60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! 👋")
                break
                
            if not user_input:
                continue
                
            print("Bot: ", end="", flush=True) # visual indicator that we are waiting
            
            response = chat_with_bot(user_input)
            
            if "response" in response:
                # Clear the "Bot: " line if you want fancy formatting, but simple is fine
                # Just print the response
                print(f"{response['response']}")
            elif "error" in response:
                print(f"❌ Error: {response['error']}")
                if "details" in response:
                     print(f"   Details: {response['details']}")
            else:
                 print(f"⚠️ Unexpected response: {response}")

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break

if __name__ == "__main__":
    main()
