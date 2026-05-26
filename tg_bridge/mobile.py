from __future__ import annotations

import asyncio
import logging
import socket
import threading
import traceback
from typing import Callable

from tg_bridge.config import DEFAULT_RELAY_IP, BridgeConfig
from tg_bridge.netutil import install_quiet_asyncio_handler
from tg_bridge.relay_pool import (
    apply_relay_to_config,
    get_working_relay,
    run_exit_probe,
)
from tg_bridge.socks5_server import handle_client

log = logging.getLogger("tg_bridge")

CANDIDATE_PORTS = (1080, 10808, 9050, 7890)


class MobileBridge:
    """SOCKS5 127.0.0.1 — sync accept (стабильно на Android)."""

    def __init__(
        self,
        relay_ip: str = DEFAULT_RELAY_IP,
        port: int = 1080,
        on_ready: Callable[[], None] | None = None,
    ) -> None:
        self.relay_ip = relay_ip
        self.port = port
        self.on_ready = on_ready
        self._thread: threading.Thread | None = None
        self._server_sock: socket.socket | None = None
        self._stop = threading.Event()
        self._running = False
        self.ready = False
        self.error: str = ""

    @property
    def running(self) -> bool:
        return self._running

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_alive:
            return
        self.error = ""
        self.ready = False
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._thread_main,
            name="tg-mobile-socks",
            daemon=False,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._running = False
        self.ready = False
        sock = self._server_sock
        self._server_sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=8)
        self._thread = None
        log.info("Мобильный мост остановлен")

    def _thread_main(self) -> None:
        install_quiet_asyncio_handler()
        srv: socket.socket | None = None
        try:
            bound_port = None
            last_err: OSError | None = None
            for port in CANDIDATE_PORTS:
                srv = None
                try:
                    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    srv.bind(("127.0.0.1", port))
                    srv.listen(128)
                    bound_port = port
                    break
                except OSError as exc:
                    last_err = exc
                    if srv is not None:
                        try:
                            srv.close()
                        except OSError:
                            pass
                    srv = None

            if bound_port is None or srv is None:
                self.error = "Не удалось занять порт SOCKS5: %s" % (last_err or "?")
                return

            self.port = bound_port
            self._server_sock = srv
            self._running = True
            self.relay_ip = get_working_relay() or DEFAULT_RELAY_IP
            self.ready = True
            log.info("SOCKS5 слушает 127.0.0.1:%s", bound_port)

            def _on_found(endpoint: str) -> None:
                self.relay_ip = endpoint
                log.info("выход обновлён: %s", endpoint)

            run_exit_probe(on_found=_on_found)

            if self.on_ready:
                try:
                    self.on_ready()
                except Exception:
                    pass

            cfg = BridgeConfig(
                host="127.0.0.1",
                port=bound_port,
                connect_timeout=35.0,
                dc_relay_ips={i: self.relay_ip for i in range(1, 6)},
            )

            srv.settimeout(1.0)
            while not self._stop.is_set():
                try:
                    client, _addr = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                relay = get_working_relay() or self.relay_ip
                if relay:
                    apply_relay_to_config(cfg, relay)
                threading.Thread(
                    target=self._client_thread,
                    args=(client, cfg),
                    name="tg-socks-client",
                    daemon=True,
                ).start()
        except Exception:
            self.error = traceback.format_exc(limit=4)
            log.exception("mobile bridge")
        finally:
            self._running = False
            self.ready = False
            if srv is not None:
                try:
                    srv.close()
                except OSError:
                    pass
            self._server_sock = None

    def _client_thread(self, client_sock: socket.socket, cfg: BridgeConfig) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._serve_client(client_sock, cfg))
        except Exception as exc:
            log.debug("client: %s", exc)
        finally:
            try:
                client_sock.close()
            except OSError:
                pass
            loop.close()

    async def _serve_client(self, client_sock: socket.socket, cfg: BridgeConfig) -> None:
        client_sock.setblocking(False)
        reader, writer = await asyncio.open_connection(sock=client_sock)
        await handle_client(reader, writer, cfg)
