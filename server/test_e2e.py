#!/usr/bin/env python3
"""
E2E test - hits the actual streaming endpoint like the frontend would.
"""
import requests
import json
import sys
import time

from app.logging_config import setup_logging
setup_logging(level="INFO")


def test_streaming_endpoint():
    """Test the /graph/stream endpoint E2E."""
    url = "http://localhost:8000/graph/stream"
    
    worldview = "AI will transform healthcare by 2027"
    
    payload = {
        "worldview": worldview,
        "k": 50,
        "topN": 5,  # Only verify top 5
        "maxHops": 2,
        "threshold": 0.75,
    }
    
    print("=" * 80)
    print("E2E STREAMING TEST")
    print("=" * 80)
    print(f"\nWorldview: '{worldview}'")
    print(f"Endpoint: {url}")
    print("\nStarting stream...\n")
    
    try:
        response = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=180,  # 3 minutes
        )
        
        if response.status_code != 200:
            print(f"✗ Error: {response.status_code}")
            print(response.text)
            return False
        
        print("✓ Connected, receiving events:\n")
        
        event_counts = {}
        last_event = None
        claims_generated = 0
        claims_verified = 0
        
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            if line.startswith("event: "):
                event_type = line[7:]
                last_event = event_type
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
                
                emoji = {
                    "claim_generated": "📝",
                    "claim_verifying": "🔍",
                    "claim_verified": "✅",
                    "sources_found": "🔗",
                    "graph_complete": "🎉",
                    "error": "❌",
                }.get(event_type, "📬")
                
                if event_type == "claim_generated":
                    claims_generated += 1
                elif event_type == "claim_verified":
                    claims_verified += 1
                
                print(f"{emoji} {event_type} ({event_counts[event_type]})")
                
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                
                # Show details for key events
                if last_event == "claim_generated" and "node" in data:
                    print(f"   Claim: {data['node']['label'][:70]}...")
                    
                elif last_event == "claim_verified" and "verification" in data:
                    conf = data['verification'].get('confidence', 0)
                    print(f"   Confidence: {conf:.2f}")
                    sources = len(data['verification'].get('exa_results', []))
                    if sources > 0:
                        print(f"   Sources: {sources} articles")
                    
                elif last_event == "sources_found" and "market" in data:
                    print(f"   Market: {data['market']['title'][:60]}...")
                    
                elif last_event == "graph_complete":
                    graph = data
                    print(f"\n   Final graph:")
                    print(f"   - Nodes: {len(graph.get('nodes', []))}")
                    print(f"   - Edges: {len(graph.get('edges', []))}")
                    print(f"   - Core ID: {graph.get('coreId', 'N/A')}")
                    
                elif last_event == "error":
                    print(f"   Error: {data.get('error', 'Unknown')}")
        
        print("\n" + "=" * 80)
        print("EVENT SUMMARY")
        print("=" * 80)
        for event, count in sorted(event_counts.items()):
            print(f"  {event}: {count}")
        
        print(f"\nClaims: {claims_generated} generated, {claims_verified} verified")
        
        if "graph_complete" in event_counts:
            print("\n✓ E2E test passed!")
            return True
        else:
            print("\n⚠ Stream ended without graph_complete")
            return False
        
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to server.")
        print("  Start the server first:")
        print("    poetry run uvicorn app.main:app --reload")
        return False
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code == 200:
            print("✓ Server is running\n")
        else:
            print(f"⚠ Server returned {response.status_code}\n")
    except:
        print("=" * 80)
        print("SERVER NOT RUNNING")
        print("=" * 80)
        print("\nStart the server first:")
        print("  poetry run uvicorn app.main:app --reload")
        print("\nThen run this test again:")
        print("  poetry run python test_e2e.py\n")
        sys.exit(1)
    
    success = test_streaming_endpoint()
    sys.exit(0 if success else 1)

