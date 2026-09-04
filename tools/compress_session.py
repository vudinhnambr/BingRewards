import json
import base64
from pathlib import Path

def optimize_session(raw_b64: str) -> str:
    data = json.loads(base64.b64decode(raw_b64.strip()).decode('utf-8'))
    cookies = data.get('cookies', [])
    
    # Crucial cookies for Bing / Rewards authentication:
    # 1. .bing.com: _U, .MSA.Auth, MUID, MUIDB, SRCHD, SRCHUID, _EDGE_S, _EDGE_V, WLS
    # 2. rewards.bing.com: rn_S, rn_SID, _C_Auth, etc.
    # 3. .login.live.com / .live.com: MSPRequ, RPSMaybe, PPLState, MSPCID, MSPAuth, MSPProf, WLSSC, NAP, ANON
    # 4. .msn.com: lt, elt, eltc, MUID
    
    # Notice Microsoft puts huge OParams (4KB), OParams1 (4KB), OParams2 (4KB), AMC-SecAuth (10KB) which are for Azure / Microsoft Account Management portal, NOT needed for Rewards or Bing Search!
    
    bloated_cookie_names = ["OParams", "OParams1", "OParams2", "AMCSecAuth", "AMCSecAuthJWT", "AMCAccessToken", "fptctx2", "ak_bmsc", "bm_sv"]
    
    clean_cookies = []
    for c in cookies:
        name = c.get("name", "")
        domain = c.get("domain", "").lower()
        if any(b in name for b in bloated_cookie_names):
            continue
        clean_cookies.append(c)
        
    cleaned_state = {"cookies": clean_cookies, "origins": []}
    compact_json = json.dumps(cleaned_state, separators=(',', ':'))
    new_b64 = base64.b64encode(compact_json.encode('utf-8')).decode('utf-8')
    
    return new_b64

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            raw = f.read()
        out = optimize_session(raw)
        print(f"Compressed size: {len(out)} chars = {len(out)/1024:.2f} KB")
        with open("session_base64.txt", "w", encoding="utf-8") as f:
            f.write(out)
