#!/bin/bash
# Test the new v2 endpoint with sample data

curl -X POST http://localhost:8000/convert_text_to_edi_v2 \
  -H "Content-Type: application/json" \
  -d '{"interchange_sender":"TESTNEW","edi_info_id":"430f255d-8576-4835-823e-26be72bb5312"}' \
  | python3 -m json.tool
