class ConnectionManager:
    def __init__(self):
        # tenant_id -> { incidente_id -> [WebSockets] }
        self.active_connections: dict = {}

    async def connect(self, websocket, tenant_id: int, room_id: str):
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = {}
        if room_id not in self.active_connections[tenant_id]:
            self.active_connections[tenant_id][room_id] = []
        self.active_connections[tenant_id][room_id].append(websocket)

    def disconnect(self, websocket, tenant_id: int, room_id: str):
        if tenant_id in self.active_connections and room_id in self.active_connections[tenant_id]:
            self.active_connections[tenant_id][room_id].remove(websocket)
            if not self.active_connections[tenant_id][room_id]:
                del self.active_connections[tenant_id][room_id]
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]

    async def send_personal_message(self, message: str, websocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict, tenant_id: int, room_id: str):
        if tenant_id in self.active_connections and room_id in self.active_connections[tenant_id]:
            for connection in self.active_connections[tenant_id][room_id]:
                await connection.send_json(message)

    async def broadcast_all_tenants(self, message: dict, room_id: str):
        for tenant_id in self.active_connections:
            if room_id in self.active_connections[tenant_id]:
                for connection in self.active_connections[tenant_id][room_id]:
                    await connection.send_json(message)

manager = ConnectionManager()
