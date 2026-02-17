#!/usr/bin/env python3
"""Test custom LLM connection"""

from dotenv import load_dotenv
load_dotenv()

from engine.chains import llm

def test_llm():
    """Test basic LLM functionality"""
    print("Testing LLM connection...")
    
    try:
        response = llm.invoke("Say 'Hello, EDI!' in exactly 3 words.")
        print(f"✅ LLM Response: {response.content}")
        print(f"✅ LLM is working!")
        return True
    except Exception as e:
        print(f"❌ LLM Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_llm()

