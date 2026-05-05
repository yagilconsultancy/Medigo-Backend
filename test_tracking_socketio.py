#!/usr/bin/env python3
"""
Test direct connection to tracking service and through gateway.
"""

import asyncio
import json
import subprocess
import sys

# Install dependencies
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "python-socketio", "aiohttp", "httpx"])

import socketio


async def test_direct_tracking_service():
    """Test connecting directly to tracking service."""
    print("\n" + "="*70)
    print("TEST 1: Direct Connection to Tracking Service")
    print("="*70)
    
    # Try different possible URLs
    urls_to_try = [
        "http://localhost:8006",
        "http://tracking-service:8006",
        "http://127.0.0.1:8006",
    ]
    
    for url in urls_to_try:
        print(f"\nTrying: {url}")
        
        sio = socketio.AsyncClient(reconnection=False)
        
        connect_attempted = False
        connect_error = None
        
        @sio.on("connect", namespace="/tracking")
        async def on_connect():
            print(f"  ✓ Connected!")
            
        @sio.on("connect_error", namespace="/tracking")
        async def on_connect_error(data):
            nonlocal connect_error
            connect_error = data
            print(f"  ✗ Connection error: {data}")
        
        try:
            connect_attempted = True
            print(f"  Connecting to {url}/socket.io/ ...")
            await sio.connect(
                url,
                transports=["websocket"],
                namespaces=["/tracking"],
                wait_timeout=5,
            )
            print(f"  ✓ SUCCESS! Connected to {url}")
            await asyncio.sleep(2)
            await sio.disconnect()
            return True
        except asyncio.TimeoutError:
            if connect_error:
                print(f"  ✗ Failed: {connect_error}")
            else:
                print(f"  ✗ Timeout - service not responding")
        except ConnectionRefusedError:
            print(f"  ✗ Connection refused - service not running")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {e}")
        finally:
            try:
                if sio.connected:
                    await sio.disconnect()
            except:
                pass
    
    return False


async def test_gateway():
    """Test connecting through gateway."""
    print("\n" + "="*70)
    print("TEST 2: Connection Through API Gateway")
    print("="*70)
    
    gateway_url = "http://localhost:8080"
    
    print(f"\nGateway URL: {gateway_url}")
    print("Socket.IO path: /api/v1/ws/socket.io")
    print(f"Namespace: /tracking")
    
    sio = socketio.AsyncClient(reconnection=False, engineio_logger=False, logger=False)
    
    connect_error = None
    
    @sio.on("connect", namespace="/tracking")
    async def on_connect():
        print(f"  ✓ Connected through gateway!")
        
    @sio.on("connect_error", namespace="/tracking")
    async def on_connect_error(data):
        nonlocal connect_error
        connect_error = data
        print(f"  ✗ Connection error: {data}")
    
    try:
        print(f"Connecting...")
        await sio.connect(
            gateway_url,
            socketio_path="api/v1/ws/socket.io",
            transports=["websocket"],
            namespaces=["/tracking"],
            wait_timeout=5,
        )
        print(f"  ✓ SUCCESS! Connected through gateway")
        await asyncio.sleep(2)
        await sio.disconnect()
        return True
    except asyncio.TimeoutError:
        if connect_error:
            print(f"  ✗ Failed: {connect_error}")
        else:
            print(f"  ✗ Timeout")
        return False
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")
        return False
    finally:
        try:
            if sio.connected:
                await sio.disconnect()
        except:
            pass


async def check_services_health():
    """Check if services are running."""
    print("\n" + "="*70)
    print("SERVICE HEALTH CHECK")
    print("="*70)
    
    import httpx
    
    services = {
        "Gateway": "http://localhost:8080/docs",
        "Tracking": "http://localhost:8006/tracking/docs",
        "Auth": "http://localhost:8001/docs",
    }
    
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in services.items():
            try:
                response = await client.get(url)
                status = "✓ UP" if response.status_code < 500 else "✗ ERROR"
                print(f"  {name:15} {status:10} ({response.status_code})")
            except Exception as e:
                print(f"  {name:15} ✗ DOWN       ({type(e).__name__})")


async def main():
    await check_services_health()
    
    # Test direct connection first
    direct_ok = await test_direct_tracking_service()
    
    if not direct_ok:
        print("\n⚠️  Cannot connect directly to tracking service!")
        print("   Check if the service is running and accessible.")
        print("   Gateway cannot proxy to a service it can't reach.")
        return
    
    # If direct works, test through gateway
    await test_gateway()
    
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
