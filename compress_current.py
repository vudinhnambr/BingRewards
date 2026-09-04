import json
import base64
from export_session import clean_session_data, copy_to_clipboard

# Read raw session if exists, or optimize
session_file = "session.json"
try:
    with open(session_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    cleaned = clean_session_data(data)
    compact_json = json.dumps(cleaned, separators=(',', ':'))
    b64 = base64.b64encode(compact_json.encode('utf-8')).decode('utf-8')
    
    with open("session_base64.txt", "w", encoding="utf-8") as f:
        f.write(b64)
        
    copied = copy_to_clipboard(b64)
    print(f"DONE: size = {len(b64)} chars = {len(b64)/1024:.2f} KB | Copied: {copied}")
except Exception as e:
    print(f"Error: {e}")
