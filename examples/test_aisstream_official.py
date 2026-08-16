"""
Official AISStream Python Client Example with verbose debugging.
"""

import asyncio
import json
import os
import sys
from dotenv import load_dotenv
import websockets

load_dotenv()

API_KEY = os.getenv("AISSTREAM_API_KEY") or os.getenv("VESSEL_PROVIDER_API_KEY")


async def connect_ais_stream():
    if not API_KEY:
        print("ERROR: No API Key found in .env")
        return

    print(f"Connecting with API Key: {API_KEY[:6]}...{API_KEY[-4:]} (length {len(API_KEY)})")
    
    url = "wss://stream.aisstream.io/v0/stream"
    try:
        async with websockets.connect(url, ssl=True) as websocket:
            subscribe_message = {
                "APIKey": API_KEY.strip(),
                "BoundingBoxes": [[[-90, -180], [90, 180]]],
            }
            
            await websocket.send(json.dumps(subscribe_message))
            print("Subscription payload sent! Waiting for stream data...")

            count = 0
            async for message_json in websocket:
                count += 1
                message = json.loads(message_json)
                msg_type = message.get("MessageType")
                meta = message.get("MetaData", {})
                print(f"[{count}] Broadcast Received:")
                print(f"    Ship:     {meta.get('ShipName')}")
                print(f"    MMSI:     {meta.get('MMSI')}")
                print(f"    Lat/Lon:  {meta.get('latitude')}, {meta.get('longitude')}")
                print(f"    Type:     {msg_type}")
                print(f"    Time UTC: {meta.get('time_utc')}")
                print("-" * 50)
                if count >= 3:
                    print("SUCCESS: 3 live vessel AIS broadcasts successfully captured!")
                    break
    except Exception as exc:
        print(f"Error connecting or receiving: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(connect_ais_stream())
