#!/usr/bin/env python3
"""
Test individual components of the pipeline without running the full server.
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Set up logging before importing app modules
from app.logging_config import setup_logging
setup_logging(level="DEBUG")  # Use DEBUG to see everything


async def test_derivatives():
    """Test self-consistent derivative generation."""
    print("=" * 70)
    print("1. Testing Derivative Generation (Self-Consistency)")
    print("=" * 70 + "\n")
    
    from app.derivatives import DerivativesClient
    
    client = DerivativesClient()
    worldview = "Remote work will become the default by 2026"
    
    print(f"Worldview: '{worldview}'\n")
    print("Generating 4 sets of derivatives with different temperatures...")
    print("(Each set should have 6-15 derivatives after validation)\n")
    
    try:
        sets = await client.generate_multiple_sets(worldview, num_sets=4)
        
        print(f"✓ Generated {len(sets)} valid sets:")
        for i, s in enumerate(sets, 1):
            print(f"  Set {i}: {len(s)} derivatives")
            print(f"    Sample: {s[0][:70]}...")
        
        total = sum(len(s) for s in sets)
        unique = len(set(d.lower() for s in sets for d in s))
        print(f"\n✓ Total: {total} derivatives ({unique} unique)\n")
    except ValueError as e:
        print(f"✗ Failed: {e}\n")
        raise


async def test_exa():
    """Test Exa search."""
    print("=" * 70)
    print("2. Testing Exa Web Search")
    print("=" * 70 + "\n")
    
    if not os.getenv("EXA_API_KEY"):
        print("⊘ Skipping (EXA_API_KEY not set)\n")
        return
    
    from app.exa_client import ExaClient
    
    client = ExaClient()
    query = "artificial intelligence progress 2024"
    
    print(f"Searching for: '{query}'\n")
    
    results = client.search_and_contents(query, num_results=3)
    
    print(f"✓ Found {len(results)} results:\n")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.title}")
        print(f"     {result.url}")
        print(f"     Snippet: {result.snippet[:80]}...\n")


async def test_verification():
    """Test verification with Exa tool calling."""
    print("=" * 70)
    print("3. Testing Verification Agent (LLM + Exa Tool Calling)")
    print("=" * 70 + "\n")
    
    if not os.getenv("EXA_API_KEY"):
        print("⊘ Skipping (EXA_API_KEY not set)\n")
        return
    
    from app.verification import VerificationAgent
    
    agent = VerificationAgent()
    claim = "SpaceX successfully launched Starship in 2023"
    
    print(f"Verifying claim: '{claim}'")
    print("(The LLM will search the web using Exa...)\n")
    
    result = await agent.verify_claim(claim)
    
    print(f"✓ Verification complete:\n")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Rationale: {result.rationale}")
    print(f"  Sources: {len(result.exa_results)} articles found")
    
    if result.exa_results:
        print(f"\n  Top source: {result.exa_results[0].title}")
        print(f"              {result.exa_results[0].url}\n")


async def main():
    print("\n" + "=" * 70)
    print("COMPONENT TESTING")
    print("=" * 70 + "\n")
    
    # Check API keys
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_exa = bool(os.getenv("EXA_API_KEY"))
    
    print("API Keys:")
    print(f"  OPENAI_API_KEY: {'✓' if has_openai else '✗ missing'}")
    print(f"  EXA_API_KEY: {'✓' if has_exa else '⊘ optional (skips verification tests)'}")
    print()
    
    if not has_openai:
        print("✗ OPENAI_API_KEY is required. Set it in .env file.\n")
        return
    
    try:
        # Test 1: Derivatives
        await test_derivatives()
        
        # Test 2: Exa (optional)
        await test_exa()
        
        # Test 3: Verification (requires Exa)
        await test_verification()
        
        print("=" * 70)
        print("✓ All available tests passed!")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

