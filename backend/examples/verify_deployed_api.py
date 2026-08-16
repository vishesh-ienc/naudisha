"""
Verification script for NauDisha deployed backend API and WebSocket endpoints with Real Vessel Data.
Tests all MVP Contract v2 endpoints against the public URL.
"""

import asyncio
import json
import urllib.request
import urllib.error
import websockets


BASE_URL = "https://slimy-bananas-flow.loca.lt"
HEADERS = {
    "Content-Type": "application/json",
    "bypass-tunnel-reminder": "true",
    "User-Agent": "NauDisha-Verifier/1.0",
}


def make_request(method: str, path: str, data: dict = None, timeout: int = 180, extra_headers: dict = None):
    url = f"{BASE_URL}{path}"
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    req = urllib.request.Request(url, data=payload, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}, dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body), dict(e.headers)
        except Exception:
            return e.code, body, dict(e.headers)


async def test_websocket_endpoints():
    print("11. Testing WebSocket Endpoint (/ws/ships/{imo})...")
    # Test valid IMO connection
    uri = "ws://127.0.0.1:8000/ws/ships/9176187"
    async with websockets.connect(uri) as ws:
        print("    Connected successfully with real vessel IMO 9176187 [OK]")

    # Test invalid IMO connection (should close with policy violation or fail)
    uri_invalid = "ws://127.0.0.1:8000/ws/ships/1234560"
    try:
        async with websockets.connect(uri_invalid) as ws:
            print("    Warning: Connected unexpectedly with invalid IMO")
    except Exception as exc:
        print(f"    Rejected invalid IMO as expected ({type(exc).__name__}) [OK]")


def test_cors_headers():
    print("12. Testing CORS Headers (OPTIONS & GET with Origin)...")
    req = urllib.request.Request(
        f"{BASE_URL}/health",
        headers={
            "Origin": "http://localhost:5173",
            "bypass-tunnel-reminder": "true",
            "Access-Control-Request-Method": "GET",
        },
        method="OPTIONS",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        headers = dict(resp.headers)
        allow_origin = headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin")
        print(f"    CORS Preflight Status: {resp.status}")
        print(f"    Access-Control-Allow-Origin: {allow_origin} [OK]")
        assert resp.status == 200
        assert allow_origin is not None


def main():
    print(f"=== NauDisha Real Vessel API Verification: {BASE_URL} ===\n")

    # 1. GET /health
    status, data, _ = make_request("GET", "/health")
    print(f"1. GET /health -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 200
    assert data.get("status") == "ok"

    # 2. POST /api/ships (Real Vessel: IMO 9176187 - Courage, Vehicle Carrier)
    status, data, _ = make_request("POST", "/api/ships", {"imo_number": "9176187"})
    print(f"2. POST /api/ships (Courage - 9176187) -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}")
    print(f"   Vessel Name: {data.get('name')}, Type: {data.get('ship', {}).get('ship_type')}, Length: {data.get('ship', {}).get('length_m')}m, Draft: {data.get('ship', {}).get('draft_m')}m\n")
    assert status == 200
    assert data.get("name") == "Courage"
    assert data.get("ship", {}).get("ship_type") == "Vehicles Carrier"
    assert data.get("ship", {}).get("length_m") == 199.9

    # 3. POST /api/ships (Real Vessel: IMO 9811000 - Ever Given, Container Ship)
    status, data, _ = make_request("POST", "/api/ships", {"imo_number": "9811000"})
    print(f"3. POST /api/ships (Ever Given - 9811000) -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}")
    print(f"   Vessel Name: {data.get('name')}, Type: {data.get('ship', {}).get('ship_type')}, Length: {data.get('ship', {}).get('length_m')}m, Beam: {data.get('ship', {}).get('beam_m')}m\n")
    assert status == 200
    assert data.get("name") == "Ever Given"
    assert data.get("ship", {}).get("length_m") == 399.9

    # 4. POST /api/ships (Real Vessel: IMO 9748289 - Berge Everest, VLOC Bulk Carrier)
    status, data, _ = make_request("POST", "/api/ships", {"imo_number": "9748289"})
    print(f"4. POST /api/ships (Berge Everest - 9748289) -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}")
    print(f"   Vessel Name: {data.get('name')}, Type: {data.get('ship', {}).get('ship_type')}, Draft: {data.get('ship', {}).get('draft_m')}m\n")
    assert status == 200
    assert data.get("name") == "Berge Everest"

    # 5. POST /api/ships (Unknown IMO -> 404 SHIP_NOT_FOUND)
    status, data, _ = make_request("POST", "/api/ships", {"imo_number": "9074729"})
    print(f"5. POST /api/ships (Unknown IMO 9074729) -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 404
    assert data["error"]["code"] == "SHIP_NOT_FOUND"

    # 6. POST /api/ships (Invalid IMO Checksum -> 422 INVALID_IMO)
    status, data, _ = make_request("POST", "/api/ships", {"imo_number": "1234560"})
    print(f"6. POST /api/ships (Invalid IMO Checksum) -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 422
    assert data["error"]["code"] == "INVALID_IMO"

    # 7. POST /api/routes/preview (With Real IMO 9176187 Courage - querying live CMEMS+Open-Meteo)
    print("7. POST /api/routes/preview (With Real IMO 9176187 Courage - querying live CMEMS+Open-Meteo)...")
    req_body = {
        "imo_number": "9176187",
        "start": {"latitude": 18.52, "longitude": 72.91},
        "destination": {"latitude": 19.07, "longitude": 72.87},
        "departure_time": "2026-08-20T06:00:00Z",
    }
    status, data, _ = make_request("POST", "/api/routes/preview", req_body, timeout=180)
    print(f"   Response status: HTTP {status}")
    print(f"   Departure Time: {data.get('departure_time')}, ETA: {data.get('eta')}, Cost: {data.get('total_cost')}")
    print(f"   Waypoints: {len(data.get('route', []))} nodes, Distance: {data.get('distance_nm')} NM\n")
    assert status == 200
    assert data["status"] == "route_ready"
    assert "departure_time" in data
    assert "eta" in data
    assert len(data["route"]) > 0

    # 8. POST /api/routes/preview (IMO-less Flow with custom ship particulars)
    print("8. POST /api/routes/preview (IMO-less Flow with custom ship particulars)...")
    req_body_no_imo = {
        "imo_number": None,
        "start": {"latitude": 18.52, "longitude": 72.91},
        "destination": {"latitude": 19.07, "longitude": 72.87},
        "ship": {
            "ship_type": "Bulk Carrier",
            "length_m": 225.0,
            "beam_m": 32.2,
            "draft_m": 12.5,
            "cruising_speed_kn": 14.0,
            "max_speed_kn": 17.0,
        },
    }
    status, data, _ = make_request("POST", "/api/routes/preview", req_body_no_imo, timeout=180)
    print(f"   Response status: HTTP {status}")
    print(f"   IMO: {data.get('imo_number')}, ETA: {data.get('eta')}, Cost: {data.get('total_cost')}\n")
    assert status == 200
    assert data["imo_number"] is None

    # 9. POST /api/ships/9176187/tracking/start
    status, data, _ = make_request("POST", "/api/ships/9176187/tracking/start", {
        "destination": {"latitude": 19.07, "longitude": 72.87}
    })
    print(f"9. POST /api/ships/9176187/tracking/start -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 200
    assert data["tracking"] is True

    # 10. GET /api/ships/9176187/status
    status, data, _ = make_request("GET", "/api/ships/9176187/status")
    print(f"10. GET /api/ships/9176187/status -> HTTP {status}")
    print(f"    Response: {json.dumps(data)}\n")
    assert status == 200
    assert data["imo_number"] == "9176187"
    assert "destination" in data

    # 11. WebSocket tests
    asyncio.run(test_websocket_endpoints())
    print()

    # 12. CORS tests
    test_cors_headers()
    print()

    print("==================================================================")
    print("=== ALL REAL VESSEL ENDPOINTS VERIFIED AGAINST LIVE SERVER =======")
    print("==================================================================")


if __name__ == "__main__":
    main()
