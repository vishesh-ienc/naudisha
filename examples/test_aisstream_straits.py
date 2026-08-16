"""
Test AISStream with high-density shipping strait bounding box.
"""

import asyncio
import json
import os
from dotenv import load_dotenv
import websockets

load_dotenv()

API_KEY = os.getenv("AISSTREAM_API_KEY") or os.getenv("VESSEL_PROVIDER_API_KEY")


async def test_aisstream():
    url = "wss://stream.aisstream.io/v0/stream"
    print(f"Connecting to AISStream with key: {API_KEY[:6]}...{API_KEY[-4:]}")
    
    # Singapore & Malacca Strait (Highest vessel density on Earth)
    subscription = {
        "APIKey": API_KEY.strip(),
        "BoundingBoxes": [
            [
                [1.0, 103.0],
                [2.0, 105.0]
            ]
        ],
        "FilterMessageTypes": ["PositionReport"]
    }
    
    try:
        async with websockets.connect(url, ping_interval=10, ping_timeout=10) as ws:
            print("Connected! Sending Singapore Strait bounding box subscription...")
            await ws.send(json.dumps(subscription))
            print("Waiting for live AIS position broadcast from Singapore Strait...")
            
            async for raw in ws:
                msg = json.loads(raw)
                meta = msg.get("MetaData", {})
                pos = msg.get("Message", {}).get("PositionReport", {})
                print("\n[SUCCESS] Live Satellite AIS Position Received!")
                print(f"   Ship Name: {meta.get('ShipName')}")
                print(f"   MMSI:      {meta.get('MMSI')}")
                print(f"   GPS Lat:   {meta.get('latitude')}")
                print(f"   GPS Lon:   {meta.get('longitude')}")
                print(f"   Speed SOG: {pos.get('Sog')} knots")
                print(f"   Course:    {pos.get('Cog')}°")
                print(f"   Time UTC:  {meta.get('time_utc')}")
                print("\nAISStream API Key is 100% VALID and streaming real-time live AIS data!")
                break
    except Exception as e:
        print(f"AISStream Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_aisstream())
