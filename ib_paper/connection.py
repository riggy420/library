"""Connection lifecycle manager for TWS / IB Gateway."""

import threading
from typing import Optional

from ib_insync import IB, util

from .config import Config
from .exceptions import ConnectionError, LiveAccountWarning
from .types import ConnectionState


class ConnectionManager:
    """Manages a single ``ib_insync.IB`` connection.

    Typical usage::

        cm = ConnectionManager()
        cm.connect()
        ib = cm.ib
        # ... use ib ...
        cm.disconnect()

    Also supports the context-manager protocol::

        with ConnectionManager() as cm:
            ib = cm.ib
            ...
    """

    # TWS / IB Gateway default ports
    PORT_PAPER = 7497
    PORT_LIVE = 7496
    PORT_GATEWAY_PAPER = 4002
    PORT_GATEWAY_LIVE = 4001

    _LIVE_PORTS = {PORT_LIVE, PORT_GATEWAY_LIVE}

    def __init__(self) -> None:
        self._ib: Optional[IB] = None
        self._state = ConnectionState.DISCONNECTED
        self._readonly = False

    # -- properties -------------------------------------------------------

    @property
    def ib(self) -> IB:
        """Return the underlying ``IB`` instance.

        Raises ``ConnectionError`` if not connected.
        """
        if self._ib is None or not self._ib.isConnected():
            raise ConnectionError(
                "Not connected to TWS / IB Gateway. Call connect() first."
            )
        return self._ib

    @property
    def is_connected(self) -> bool:
        """``True`` when the connection is established and alive."""
        return self._ib is not None and self._ib.isConnected()

    @property
    def readonly(self) -> bool:
        """``True`` when connected in read-only mode (orders blocked)."""
        return self._readonly

    # -- connect / disconnect ---------------------------------------------

    def connect(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        client_id: Optional[int] = None,
        readonly: bool = False,
        max_retries: int = 20,
    ) -> None:
        """Connect to TWS or IB Gateway.

        Parameters are read from config when not supplied explicitly.

        Args:
            host: TWS / Gateway host (default ``127.0.0.1``).
            port: TWS / Gateway port (default ``7497`` -- paper).
            client_id: Unique client id (default from config).
            readonly: If ``True``, order placement is blocked.
            max_retries: If the client ID is already in use, auto-increment
                up to this many times before giving up.

        Raises:
            LiveAccountWarning: If *port* appears to be a live-trading port.
            ConnectionError: If the connection cannot be established.
        """
        config = Config.load()
        host = host or config["connection"]["host"]
        port = port or config["connection"]["port"]
        if client_id is None:
            client_id = config["connection"]["client_id"]
        timeout = config["connection"]["timeout"]

        # Detect live-trading port
        if port in self._LIVE_PORTS:
            if config["safety"]["confirm_live"]:
                raise LiveAccountWarning(
                    f"Port {port} is a LIVE trading port. "
                    f"Paper trading uses port {self.PORT_PAPER}. "
                    "Set safety.confirm_live to false in config to suppress."
                )

        self._state = ConnectionState.CONNECTING
        self._readonly = readonly
        util.startLoop()

        # Track whether we got a client-ID-collision error (326).
        # ib_insync doesn't surface this as an exception from connect();
        # it comes through ib.errorEvent.  We listen for it to abort
        # early instead of waiting for the full timeout.
        collision_event = threading.Event()

        def _on_error(reqId, errorCode, errorString, _contract):
            if errorCode == 326:
                collision_event.set()

        last_error: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            cid = client_id + attempt
            collision_event.clear()

            # Use a short timeout for retries — the client-ID collision
            # is detected within milliseconds, so 2s is plenty.
            attempt_timeout = timeout if attempt == 0 else min(timeout, 2)

            ib = IB()
            ib.errorEvent += _on_error
            try:
                ib.connect(host, port, clientId=cid, timeout=attempt_timeout)
                # Success — disconnect the error handler & persist the ID
                ib.errorEvent -= _on_error
                self._ib = ib
                self._state = ConnectionState.CONNECTED
                if cid != config["connection"]["client_id"]:
                    Config.update({"connection": {"client_id": cid}})
                return
            except Exception as exc:
                last_error = exc
                ib.errorEvent -= _on_error
                try:
                    ib.disconnect()
                except Exception:
                    pass

                # If we got error 326 (client ID collision), increment & retry
                if collision_event.is_set():
                    continue

                # Any other error — don't retry
                break

        self._state = ConnectionState.DISCONNECTED
        self._ib = None
        raise ConnectionError(
            f"Could not connect to TWS / IB Gateway at {host}:{port}.\n"
            "Make sure TWS or IB Gateway is running and API connections "
            "are enabled:\n"
            "  File → Global Configuration → API → Settings → "
            "Enable ActiveX and Socket Clients.\n"
            f"Details: {last_error}"
        ) from last_error

    def disconnect(self) -> None:
        """Disconnect and tear down the IB session."""
        if self._ib is not None and self._ib.isConnected():
            self._ib.disconnect()
        self._state = ConnectionState.DISCONNECTED
        self._ib = None

    # -- context manager --------------------------------------------------

    def __enter__(self) -> "ConnectionManager":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()

    # -- repr -------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<ConnectionManager state={self._state.value!r} readonly={self._readonly!r}>"
