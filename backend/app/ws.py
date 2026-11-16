"""Canal WebSocket: entrega en tiempo real de mensajes y avisos (requisito 17)."""
from typing import Dict, Iterable, Set

import anyio
from fastapi import WebSocket


class Gestor:
    """Mantiene las conexiones abiertas de cada usuario.

    Un usuario puede tener varias a la vez (celular y computadora).
    """

    def __init__(self) -> None:
        self._conexiones: Dict[int, Set[WebSocket]] = {}

    async def conectar(self, usuario_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._conexiones.setdefault(usuario_id, set()).add(ws)

    def desconectar(self, usuario_id: int, ws: WebSocket) -> None:
        conexiones = self._conexiones.get(usuario_id)
        if conexiones:
            conexiones.discard(ws)
            if not conexiones:
                self._conexiones.pop(usuario_id, None)

    async def enviar(self, usuarios: Iterable[int], evento: dict) -> None:
        for usuario_id in set(usuarios):
            for ws in list(self._conexiones.get(usuario_id, ())):
                try:
                    await ws.send_json(evento)
                except Exception:
                    self.desconectar(usuario_id, ws)

    def enviar_desde_hilo(self, usuarios: Iterable[int], evento: dict) -> None:
        """Para los endpoints síncronos, que corren en un hilo aparte."""
        try:
            anyio.from_thread.run(self.enviar, list(usuarios), evento)
        except Exception:
            # Un aviso que no llega nunca debe hacer fallar la operación.
            pass


gestor = Gestor()
