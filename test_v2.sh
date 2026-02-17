#!/bin/bash
# Test the new v2 endpoint with sample data

curl -X POST http://localhost:8000/convert_text_to_edi_v2 \
  -H "Content-Type: application/json" \
  -d '{"interchange_sender":"TESTNEW","edi_info_id":"dcdbeeb6-93e4-4640-9a13-850e88c0dc87"}' \
  | python3 -m json.tool
