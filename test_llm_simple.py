#!/usr/bin/env python3
"""
Simple test to check if the LLM is responding at all
"""
import os
import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import time

load_dotenv()

LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

print(f"Testing LLM: {LLM_MODEL}")
print(f"URL: {LLM_API_URL}")
print("-" * 70)

# Create HTTP client with timeout
http_client = httpx.Client(verify=False, timeout=60.0)

llm = ChatOpenAI(
    model=LLM_MODEL,
    temperature=0.1,
    openai_api_key=LLM_API_KEY,
    openai_api_base=LLM_API_URL,
    http_client=http_client,
    request_timeout=60
)

# Test 1: Very simple prompt
print("\n[Test 1] Simple prompt...")
start = time.time()
try:
    response = llm.invoke("Say hello in 5 words or less")
    print(f"✓ Response in {time.time()-start:.2f}s: {response.content}")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test 2: Slightly longer prompt
print("\n[Test 2] Medium prompt...")
start = time.time()
try:
    response = llm.invoke("Extract the invoice number from this text: Invoice #12345 dated March 1, 2024")
    print(f"✓ Response in {time.time()-start:.2f}s: {response.content}")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test 3: Structured output (like the real extraction)
print("\n[Test 3] Structured JSON output...")
from pydantic import BaseModel, Field

class SimpleExtraction(BaseModel):
    invoice_number: str = Field(description="The invoice number")
    invoice_date: str = Field(description="The invoice date")

start = time.time()
try:
    structured_llm = llm.with_structured_output(SimpleExtraction)
    response = structured_llm.invoke("Invoice #12345 dated March 1, 2024")
    print(f"✓ Response in {time.time()-start:.2f}s:")
    print(f"  Invoice: {response.invoice_number}")
    print(f"  Date: {response.invoice_date}")
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n" + "=" * 70)
print("LLM test complete!")

