from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import json
from src.broker.manager import manager
from src.modules.iam.models import Usuario
from src.modules.iam.dependencies import verify_token_ws

router = APIRouter(prefix="/ws", tags=["Tiempo Real"])

@router.websocket("/{tenant_id}/{room_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: int, room_id: str, token: str):
    user = verify_token_ws(token)
    
    # Permitir tenant_id=0 si el usuario no tiene tenant (conductor global)
    is_global = (tenant_id == 0 and user is not None and user.tenant_id is None)
    
    if not user or (user.tenant_id != tenant_id and not is_global):
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, tenant_id, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("action") == "telemetria":
                    await manager.broadcast(payload, tenant_id, room_id)
                else:
                    await manager.broadcast({"message": f"User {user.Correo}: {data}"}, tenant_id, room_id)
            except Exception:
                await manager.broadcast({"message": f"User {user.Correo}: {data}"}, tenant_id, room_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, tenant_id, room_id)
        await manager.broadcast({"message": f"User {user.Correo} left the room"}, tenant_id, room_id)
