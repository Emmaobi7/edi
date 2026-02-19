#!/usr/bin/env python3
"""Quick test to verify LLM connection is working."""

import httpx
import json
import time

LLM_API_URL = "https://ai.kontratar.com:40726/v1/chat/completions"
LLM_API_KEY = "c96ef1a0bd506defa4b2c0c0318a654952ad6b8ef598c6f104d99ffa36264ca7"
LLM_MODEL = "gaunernst/gemma-3-27b-it-qat-compressed-tensors"

print("🔍 Testing LLM connection...")
print(f"URL: {LLM_API_URL}")
print(f"Model: {LLM_MODEL}")
print()

# Simple test request
payload = {
    "model": LLM_MODEL,
    "messages": [
        {"role": "user", "content": "Say 'Hello, I am working!' and nothing else."}
    ],
    "max_tokens": 50,
    "temperature": 0.1
}

try:
    print("⏱️  Sending request...")
    start_time = time.time()
    
    with httpx.Client(verify=False, timeout=60.0) as client:
        response = client.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload
        )
    
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        result = response.json()
        message = result['choices'][0]['message']['content']
        tokens = result['usage']
        
        print(f"✅ SUCCESS! ({elapsed:.2f} seconds)")
        print(f"Response: {message}")
        print(f"Tokens: {tokens}")
    else:
        print(f"❌ FAILED! Status: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ ERROR: {e}")

