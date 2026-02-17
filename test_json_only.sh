#!/bin/bash
# Test v2 endpoint - extract JSON only (no EDI building)

curl -X POST http://localhost:8000/convert_text_to_edi_v2 \
  -H "Content-Type: application/json" \
  -d '{"interchange_sender":"TESTXXX","edi_info_id":"bd340a2d-5c2e-45ac-991b-a8656b7f3be8","build_edi":false}' \
  | python3 -m json.tool
