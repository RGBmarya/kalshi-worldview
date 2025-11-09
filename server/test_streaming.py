#!/usr/bin/env python3
"""
Simple test script to verify the streaming endpoint works.
Run the server first: poetry run uvicorn app.main:app --reload
"""
import requests
import json
import sys


def test_streaming_endpoint(worldview: str = "AI will transform healthcare by 2027"):
    """Test the /graph/stream endpoint."""
    url = "http://localhost:8000/graph/stream"
    
    payload = {
        "worldview": worldview,
        "k": 50,
        "topN": 20,
    }
    
    print("=" * 70)
    print(f"Testing streaming endpoint with worldview:")
    print(f"  '{worldview}'")
    print("=" * 70 + "\n")
    
    try:
        response = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=120,
        )
        
        if response.status_code != 200:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return
        
        print("✓ Connected to stream, receiving events...\n")
        
        event_counts = {}
        
        # Parse SSE stream
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            if line.startswith("event: "):
                event_type = line[7:]
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
                
                # Print event type with emoji
                emoji = {
                    "claim_generated": "📝",
                    "claim_verifying": "🔍",
                    "claim_verified": "✅",
                    "sources_found": "🔗",
                    "graph_complete": "🎉",
                    "error": "❌",
                }.get(event_type, "📬")
                
                print(f"{emoji} {event_type}")
                
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                
                # Show some details for interesting events
                if "node" in data:
                    print(f"   Claim: {data['node']['label'][:60]}...")
                elif "verification" in data:
                    conf = data['verification'].get('confidence', 0)
                    print(f"   Confidence: {conf:.2f}")
                elif "error" in data:
                    print(f"   Error: {data['error']}")
        
        print("\n" + "=" * 70)
        print("Stream complete! Event summary:")
        print("=" * 70)
        for event, count in sorted(event_counts.items()):
            print(f"  {event}: {count}")
        print()
        
        if "graph_complete" in event_counts:
            print("✓ Graph built successfully!")
        else:
            print("⚠ Stream ended without graph_complete event")
        
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to server.")
        print("  Make sure the server is running:")
        print("    poetry run uvicorn app.main:app --reload")
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_health():
    """Quick health check."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✓ Server is running\n")
            return True
        else:
            print(f"✗ Server returned {response.status_code}\n")
            return False
    except:
        print("✗ Server is not running")
        print("  Start it with: poetry run uvicorn app.main:app --reload\n")
        return False


if __name__ == "__main__":
    if not test_health():
        sys.exit(1)
    
    # Allow custom worldview from command line
    worldview = sys.argv[1] if len(sys.argv) > 1 else "AI will transform healthcare by 2027"
    
    test_streaming_endpoint(worldview)


