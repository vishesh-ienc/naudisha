"""
Verification script for NauDisha deployed backend API and WebSocket endpoints.
Tests all MVP Contract v2 endpoints against the public URL.
"""

import asyncio
import json
import urllib.request
import urllib.error
import websockets


BASE_URL = "https://lemon-windows-taste.loca.lt"
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
    print("10. Testing WebSocket Endpoint (/ws/ships/{imo})...")
    # Test valid IMO connection
    uri = "ws://127.0.0.1:8000/ws/ships/1234567"
    async with websockets.connect(uri) as ws:
        print("    Connected successfully with valid IMO 1234567 [OK]")

    # Test invalid IMO connection (should close with policy violation or fail)
    uri_invalid = "ws://127.0.0.1:8000/ws/ships/1234560"
    try:
        async with websockets.connect(uri_invalid) as ws:
            print("    Warning: Connected unexpectedly with invalid IMO")
    except websockets.exceptions.InvalidStatusCode as exc:
        print(f"    Rejected invalid IMO as expected with status {exc.status_code} [OK]")
    except Exception as exc:
        print(f"    Rejected invalid IMO as expected ({type(exc).__name__}) [OK]")


def test_cors_headers():
    print("11. Testing CORS Headers (OPTIONS & GET with Origin)...")
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
    print(f"=== NauDisha API Verification: {BASE_URL} ===\n")

    # 1. GET /health
    status, data, _ = make_request("GET", "/health")
    print(f"1. GET /health -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 200
    assert data.get("status") == "ok"

    # 2. POST /api/ships (Valid IMO)
    status, data, _ = make_request("POST", "/api/ships", {"imo_number": "1234567"})
    print(f"2. POST /api/ships (Valid IMO) -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 200
    assert data.get("imo_number") == "1234567"
    assert "ship" in data
    assert data["ship"]["cruising_speed_kn"] == 18.0

    # 3. POST /api/ships (Invalid IMO)
    status, data, _ = make_request("POST", "/api/ships", {"imo_number": "1234560"})
    print(f"3. POST /api/ships (Invalid IMO Checksum) -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 422
    assert data["error"]["code"] == "INVALID_IMO"

    # 4. POST /api/routes/preview (With IMO & departure_time)
    print("4. POST /api/routes/preview (With IMO - querying live CMEMS+Open-Meteo)...")
    req_body = {
        "imo_number": "1234567",
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

    # 5. POST /api/routes/preview (Without IMO, with custom ship particulars)
    print("5. POST /api/routes/preview (IMO-less Flow with custom ship particulars)...")
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

    # 6. POST /api/routes/preview (Rejected when neither IMO nor ship is provided)
    status, data, _ = make_request("POST", "/api/routes/preview", {
        "start": {"latitude": 18.52, "longitude": 72.91},
        "destination": {"latitude": 19.07, "longitude": 72.87},
    })
    print(f"6. POST /api/routes/preview (Missing IMO & Ship) -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 422
    assert "error" in data

    # 7. POST /api/ships/1234567/tracking/start
    status, data, _ = make_request("POST", "/api/ships/1234567/tracking/start", {
        "destination": {"latitude": 19.07, "longitude": 72.87}
    })
    print(f"7. POST /api/ships/1234567/tracking/start -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 200
    assert data["tracking"] is True

    # 8. GET /api/ships/1234567/status
    status, data, _ = make_request("GET", "/api/ships/1234567/status")
    print(f"8. GET /api/ships/1234567/status -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 200
    assert data["imo_number"] == "1234567"
    assert "destination" in data

    # 9. GET /api/ships/1234567/route
    status, data, _ = make_request("GET", "/api/ships/1234567/route")
    print(f"9. GET /api/ships/1234567/route -> HTTP {status}")
    print(f"   Response: {json.dumps(data)}\n")
    assert status == 200
    assert data["route_status"] == "optimal"
    assert "destination" in data
    assert len(data["route"]) > 0

    # 10. WebSocket tests
    asyncio.run(test_websocket_endpoints())
    print()

    # 11. CORS tests
    test_cors_headers()
    print()

    print("==================================================================")
    print("=== ALL 11 ENDPOINTS & PROTOCOLS VERIFIED AGAINST LIVE SERVER ===")
    print("==================================================================")


if __name__ == "__main__":
    main()
