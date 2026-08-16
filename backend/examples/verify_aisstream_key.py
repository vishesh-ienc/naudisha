"""
Verification script to test AISStream WebSocket API key and stream real live vessel positions.
"""

import asyncio
import json
import os
import sys
from dotenv import load_dotenv
import websockets

# 1. Load environment variables from .env
load_dotenv()

AISSTREAM_API_KEY = os.getenv("AISSTREAM_API_KEY") or os.getenv("VESSEL_PROVIDER_API_KEY")


async def connect_and_stream(api_key: str, max_messages: int = 5):
    url = "wss://stream.aisstream.io/v0/stream"
    print(f"Connecting to AISStream WebSocket: {url}...")
    
    # Standard AISStream subscription format
    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": [
            [
                [-90.0, -180.0],
                [90.0, 180.0]
            ]
        ],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData", "StandardClassBPositionReport"]
    }
    
    try:
        async with websockets.connect(url, ping_interval=10, ping_timeout=10) as ws:
            print("WebSocket connected! Sending subscription payload...")
            await ws.send(json.dumps(subscription))
            print(f"Subscription active. Listening for live global satellite/terrestrial AIS broadcasts...\n")
            
            count = 0
            while count < max_messages:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=20)
                msg = json.loads(msg_raw)
                
                # Check for server error message
                if "error" in msg:
                    print(f"AISStream Server Error: {msg['error']}")
                    return False

                msg_type = msg.get("MessageType")
                meta = msg.get("MetaData", {})
                
                ship_name = meta.get("ShipName", "").strip()
                mmsi = meta.get("MMSI")
                lat = meta.get("latitude")
                lon = meta.get("longitude")
                time_utc = meta.get("time_utc")

                count += 1
                print(f"[{count}/{max_messages}] Live Vessel Broadcast:")
                print(f"   Name:         {ship_name or 'N/A'}")
                print(f"   MMSI:         {mmsi}")
                print(f"   GPS Position: Latitude {lat}, Longitude {lon}")
                print(f"   Timestamp:    {time_utc}")
                print(f"   Message Type: {msg_type}")
                
                # Check specific message details
                if msg_type == "PositionReport":
                    pos = msg.get("Message", {}).get("PositionReport", {})
                    sog = pos.get("Sog")
                    cog = pos.get("Cog")
                    print(f"   Speed/Course: SOG {sog} kn, COG {cog}°")
                elif msg_type == "ShipStaticData":
                    stat = msg.get("Message", {}).get("ShipStaticData", {})
                    imo = stat.get("ImoNumber")
                    dim = stat.get("Dimension", {})
                    print(f"   IMO:          {imo}")
                    print(f"   Dimensions:   {dim}")
                print("-" * 55)
                
            print("\nAISStream API Key verification SUCCESSFUL! Real-time live satellite GPS data received.")
            return True
            
    except asyncio.TimeoutError:
        print("Timeout waiting for message from stream. Checking connection...")
        return False
    except websockets.exceptions.InvalidStatusCode as exc:
        print(f"Authentication failed: HTTP {exc.status_code}. Please verify your AISSTREAM_API_KEY.")
        return False
    except Exception as exc:
        print(f"Connection error: {type(exc).__name__}: {exc}")
        return False


def main():
    if not AISSTREAM_API_KEY or AISSTREAM_API_KEY.strip() == "":
        print("ERROR: AISSTREAM_API_KEY is empty or not set in .env file.")
        print("Please check c:\\Users\\VISHESH\\Desktop\\naudisha\\.env and add your key.")
        sys.exit(1)
        
    print(f"Found AISStream API Key in .env (length: {len(AISSTREAM_API_KEY.strip())} chars)")
    success = asyncio.run(connect_and_stream(AISSTREAM_API_KEY.strip(), max_messages=5))
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
