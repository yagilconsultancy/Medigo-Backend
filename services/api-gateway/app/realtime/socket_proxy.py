import logging

import socketio

from app.config import settings

logger = logging.getLogger(__name__)

SOCKETIO_SERVICE_MAP = {
    "/tracking": settings.TRACKING_SERVICE_URL,
    "/chat": settings.NOTIFICATION_SERVICE_URL,
}


class BackendSocketBridge:
    """Bridge frontend Socket.IO namespaces to backend Socket.IO services."""

    def __init__(self, server: socketio.AsyncServer):
        self.server = server
        self.backend_clients: dict[tuple[str, str], socketio.AsyncClient] = {}

    async def connect_backend(self, sid: str, namespace: str, auth: dict | None) -> None:
        service_url = SOCKETIO_SERVICE_MAP.get(namespace)
        if not service_url:
            raise socketio.exceptions.ConnectionRefusedError("Invalid namespace")

        backend_client = socketio.AsyncClient(
            engineio_logger=False,
            logger=False,
            reconnection=False,
        )

        @backend_client.on("*", namespace=namespace)
        async def forward_event(event: str, *args):
            payload = None
            if len(args) == 1:
                payload = args[0]
            elif len(args) > 1:
                payload = list(args)
            await self.server.emit(event, payload, to=sid, namespace=namespace)

        @backend_client.on("disconnect", namespace=namespace)
        async def on_backend_disconnect():
            logger.info("Backend disconnected for sid=%s namespace=%s", sid, namespace)
            if (sid, namespace) in self.backend_clients:
                await self.server.disconnect(sid, namespace=namespace)

        try:
            await backend_client.connect(
                service_url,
                socketio_path="socket.io",
                transports=["websocket"],
                namespaces=[namespace],
                auth=auth,
                wait_timeout=10,
            )
        except Exception as exc:
            logger.error(
                "Failed to connect backend Socket.IO service %s for namespace %s: %s",
                service_url,
                namespace,
                exc,
            )
            raise socketio.exceptions.ConnectionRefusedError("Backend service unavailable") from exc

        self.backend_clients[(sid, namespace)] = backend_client
        logger.info("Socket.IO bridge established for sid=%s namespace=%s", sid, namespace)

    async def disconnect_backend(self, sid: str, namespace: str) -> None:
        backend_client = self.backend_clients.pop((sid, namespace), None)
        if not backend_client:
            return

        try:
            if backend_client.connected:
                await backend_client.disconnect()
        except Exception as exc:
            logger.warning(
                "Error disconnecting backend Socket.IO client for sid=%s namespace=%s: %s",
                sid,
                namespace,
                exc,
            )

    async def emit_to_backend(self, sid: str, namespace: str, event: str, payload):
        backend_client = self.backend_clients.get((sid, namespace))
        if not backend_client or not backend_client.connected:
            raise RuntimeError(f"Backend Socket.IO client not connected for namespace {namespace}")
        try:
            result = await backend_client.call(event, payload, namespace=namespace, timeout=10)
            return result
        except socketio.exceptions.TimeoutError:
            logger.warning("Backend ack timeout for event=%s sid=%s", event, sid)
            return None


sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
)
bridge = BackendSocketBridge(sio)


class ProxyNamespace(socketio.AsyncNamespace):
    async def on_connect(self, sid: str, environ: dict, auth: dict | None = None) -> None:
        await bridge.connect_backend(sid, self.namespace, auth)

    async def on_disconnect(self, sid: str) -> None:
        await bridge.disconnect_backend(sid, self.namespace)

    async def trigger_event(self, event: str, sid: str, *args):
        if event in {"connect", "disconnect"}:
            return await super().trigger_event(event, sid, *args)

        payload = None
        if len(args) == 1:
            payload = args[0]
        elif len(args) > 1:
            payload = list(args)

        return await bridge.emit_to_backend(sid, self.namespace, event, payload)


for namespace in SOCKETIO_SERVICE_MAP:
    sio.register_namespace(ProxyNamespace(namespace))
