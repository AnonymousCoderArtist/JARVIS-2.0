#!/usr/bin/env python3
"""Simple WebSocket test client to verify the fix"""

import asyncio
import json
import websockets
import requests

async def test_websocket():
    """Test WebSocket connection and message sending"""
    
    # Get bootstrap token
    try:
        response = requests.get("http://127.0.0.1:8765/jarvis/bootstrap")
        bootstrap_data = response.json()
        token = bootstrap_data["token"]
        print(f"✓ Got token: {token[:20]}...")
    except Exception as e:
        print(f"✗ Failed to get bootstrap token: {e}")
        return
    
    # Connect to WebSocket
    uri = f"ws://127.0.0.1:8765/jarvis/ws?token={token}"
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket connected")
            
            # Wait for ready event
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"✓ Received: {response_data}")
            
            if response_data.get("event") == "ready":
                print("✓ Server ready, creating new chat")
                
                # Send new_chat request
                new_chat_msg = {
                    "type": "new_chat"
                }
                await websocket.send(json.dumps(new_chat_msg))
                print("✓ Sent new_chat request")
                
                # Wait for attached response
                response = await websocket.recv()
                response_data = json.loads(response)
                print(f"✓ Received: {response_data}")
                
                if response_data.get("event") == "attached":
                    chat_id = response_data.get("chat_id")
                    print(f"✓ Attached to chat: {chat_id}")
                    
                    # Send a test message
                    test_message = {
                        "type": "message",
                        "chat_id": chat_id,
                        "content": "Hello, this is a test message!"
                    }
                    await websocket.send(json.dumps(test_message))
                    print("✓ Sent test message")
                
                # Collect responses
                responses = []
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        response_data = json.loads(response)
                        responses.append(response_data)
                        print(f"✓ Received event: {response_data.get('event')}")
                        
                        if response_data.get("event") == "turn_end":
                            print("✓ Turn completed successfully")
                            break
                        elif response_data.get("event") == "error":
                            print(f"✗ Received error: {response_data}")
                            break
                            
                except asyncio.TimeoutError:
                    print("✗ Timeout waiting for response")
                    return
                
                print(f"✓ Received {len(responses)} events total")
                print("✓ WebSocket test completed successfully!")
                
            else:
                print(f"✗ Unexpected response: {response_data}")
                
    except Exception as e:
        print(f"✗ WebSocket test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
