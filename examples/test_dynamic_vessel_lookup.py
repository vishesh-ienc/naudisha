"""
Test dynamic online vessel lookup for any IMO number.
"""

import json
import re
import urllib.request
import urllib.error


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def test_balticshipping(imo: str):
    url = f"https://www.balticshipping.com/vessel/imo/{imo}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            print(f"[BalticShipping] Status: {resp.status}, HTML length: {len(html)}")
            
            # Extract name
            name_m = re.search(r"<title>([^-<]+)", html)
            name = name_m.group(1).strip() if name_m else None
            
            # Extract type
            type_m = re.search(r"Vessel type:\s*</[^>]+>\s*<[^>]+>([^<]+)", html, re.I)
            if not type_m:
                type_m = re.search(r"Type:\s*</[^>]+>\s*<[^>]+>([^<]+)", html, re.I)
            ship_type = type_m.group(1).strip() if type_m else None

            # Extract Length / LOA
            loa_m = re.search(r"Length Overall \(LOA\):\s*</[^>]+>\s*<[^>]+>([\d.]+)", html, re.I)
            if not loa_m:
                loa_m = re.search(r"Length:\s*</[^>]+>\s*<[^>]+>([\d.]+)", html, re.I)
            loa = float(loa_m.group(1)) if loa_m else None

            # Extract Beam
            beam_m = re.search(r"Beam:\s*</[^>]+>\s*<[^>]+>([\d.]+)", html, re.I)
            beam = float(beam_m.group(1)) if beam_m else None

            # Extract Draught
            draft_m = re.search(r"Draught:\s*</[^>]+>\s*<[^>]+>([\d.]+)", html, re.I)
            if not draft_m:
                draft_m = re.search(r"Draft:\s*</[^>]+>\s*<[^>]+>([\d.]+)", html, re.I)
            draft = float(draft_m.group(1)) if draft_m else None

            print(f"Extracted -> Name: {name}, Type: {ship_type}, LOA: {loa}m, Beam: {beam}m, Draft: {draft}m")
            return {"name": name, "type": ship_type, "length": loa, "beam": beam, "draft": draft}
    except Exception as e:
        print(f"[BalticShipping] Error for {imo}: {e}")
        return None


def test_myshiptracking(imo: str):
    url = f"https://www.myshiptracking.com/vessels?imo={imo}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            print(f"[MyShipTracking] Status: {resp.status}, HTML length: {len(html)}")
            return True
    except Exception as e:
        print(f"[MyShipTracking] Error for {imo}: {e}")
        return None


def main():
    print("Testing live online lookup for IMO 9400980 (EVALI)...")
    test_balticshipping("9400980")

    print("\nTesting live online lookup for IMO 9811000 (Ever Given)...")
    test_balticshipping("9811000")

    print("\nTesting live online lookup for random IMO 9321483 (Emma Maersk)...")
    test_balticshipping("9321483")

    print("\nTesting live online lookup for IMO 9241061 (CMA CGM Christophe Colomb)...")
    test_balticshipping("9241061")


if __name__ == "__main__":
    main()
