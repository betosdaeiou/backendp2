import asyncio
import websockets
import json

async def test_ws():
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8000/auth/login", data={"username": "taller1@lin.com", "password": "password"})
        if r.status_code != 200:
            r = await client.post("http://localhost:8000/auth/login", data={"username": "taller1@lin.com", "password": "password123"})
        if r.status_code != 200:
            print("Login failed:", r.text)
            return
        token = r.json().get("access_token")
        
        uri = f"ws://localhost:8000/ws/1/talleres?token={token}"
        try:
            async with websockets.connect(uri) as ws:
                print("Connected to WebSocket successfully!")
                
                # We don't really need to report an incident to test.
                # Just making sure we can connect and receive anything.
                # Actually, let's trigger something via HTTP
                r_cond = await client.post("http://localhost:8000/auth/login", data={"username": "conductor1@lin.com", "password": "password"})
                if r_cond.status_code != 200:
                    r_cond = await client.post("http://localhost:8000/auth/login", data={"username": "conductor1@lin.com", "password": "password123"})
                cond_token = r_cond.json().get("access_token")
                
                if cond_token:
                    headers = {"Authorization": f"Bearer {cond_token}"}
                    payload = {
                        "coordenadagps": "0,0",
                        "estado": "Reportado",
                        "vehiculo_id": 1,
                        "evidencia": {"descripcion": "test WS 2"}
                    }
                    print("Reporting incident...")
                    res = await client.post("http://localhost:8000/incidentes/reportar", json=payload, headers=headers)
                    print("Report response:", res.status_code, res.text)
                
                print("Waiting for WS message...")
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print("Received WS message:", msg)
                
        except Exception as e:
            print("WS Error:", e)

if __name__ == "__main__":
    asyncio.run(test_ws())
