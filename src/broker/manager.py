class ConnectionManager:
    def __init__(self):
        # tenant_id -> { incidente_id -> [WebSockets] }
        self.active_connections: dict = {}
        self.loop = None

    async def connect(self, websocket, tenant_id: int, room_id: str):
        import asyncio
        try:
            self.loop = asyncio.get_running_loop()
        except Exception:
            pass
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = {}
        if room_id not in self.active_connections[tenant_id]:
            self.active_connections[tenant_id][room_id] = []
        self.active_connections[tenant_id][room_id].append(websocket)

    def run_async(self, coro):
        import asyncio
        if not self.loop:
            try:
                self.loop = asyncio.get_running_loop()
            except Exception:
                pass

        if self.loop and self.loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(coro, self.loop)
                return
            except Exception as e:
                print(f"Error in run_coroutine_threadsafe: {e}")

        # Fallback 1: current thread's running loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
            return
        except RuntimeError:
            pass

        # Fallback 2: daemon thread
        import threading
        def run_in_thread():
            try:
                asyncio.run(coro)
            except Exception as e:
                print(f"Error running coro in fallback thread: {e}")
        threading.Thread(target=run_in_thread, daemon=True).start()

    def disconnect(self, websocket, tenant_id: int, room_id: str):
        if tenant_id in self.active_connections and room_id in self.active_connections[tenant_id]:
            if websocket in self.active_connections[tenant_id][room_id]:
                self.active_connections[tenant_id][room_id].remove(websocket)
            if not self.active_connections[tenant_id][room_id]:
                del self.active_connections[tenant_id][room_id]
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]

    async def send_personal_message(self, message: str, websocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict, tenant_id: int, room_id: str):
        if tenant_id in self.active_connections and room_id in self.active_connections[tenant_id]:
            for connection in self.active_connections[tenant_id][room_id].copy():
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error sending to websocket: {e}")
                    self.disconnect(connection, tenant_id, room_id)

    async def broadcast_all_tenants(self, message: dict, room_id: str):
        for tenant_id in self.active_connections:
            if room_id in self.active_connections[tenant_id]:
                for connection in self.active_connections[tenant_id][room_id].copy():
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        print(f"Error sending to websocket: {e}")
                        self.disconnect(connection, tenant_id, room_id)

manager = ConnectionManager()
