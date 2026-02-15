"""Reaper OSC feedback server.

Listens for OSC messages from Reaper and updates ReaperState.
Runs in a background thread.

NOTE: python-osc's Dispatcher.map() passes extra args as a list in the
second callback parameter: callback(address, [extra_args], *osc_values).
All handlers must account for this.
"""

import logging
import re
import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from reaper.state import ReaperState

log = logging.getLogger("push2reaper.reaper.osc_server")

# Regex to extract track number from OSC paths like /track/3/volume
_TRACK_RE = re.compile(r"^/track/(\d+)/(.+)$")
# Regex for send paths like /track/3/send/2/volume
_SEND_RE = re.compile(r"^/track/(\d+)/send/(\d+)/(.+)$")
# Regex for FX paths like /track/3/fx/1/fxparam/2/value
_FX_RE = re.compile(r"^/track/(\d+)/fx/(\d+)/(.+)$")
_FX_PARAM_RE = re.compile(r"^/track/(\d+)/fx/(\d+)/fxparam/(\d+)/(.+)$")


class ReaperOSCServer:
    """Listens for OSC feedback messages from Reaper."""

    def __init__(self, port: int = 9000, state: ReaperState = None):
        self.port = port
        self.state = state
        self._server: ThreadingOSCUDPServer | None = None
        self._thread: threading.Thread | None = None
        self._msg_count = 0

    def start(self) -> None:
        """Start listening for OSC feedback in a background thread."""
        dispatcher = Dispatcher()
        self._setup_handlers(dispatcher)

        self._server = ThreadingOSCUDPServer(
            ("0.0.0.0", self.port), dispatcher
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="osc-server",
            daemon=True,
        )
        self._thread.start()
        log.info("OSC feedback server listening on :%d", self.port)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            log.info("OSC feedback server stopped")

    def _setup_handlers(self, d: Dispatcher) -> None:
        """Register OSC message handlers."""

        # --- Transport feedback ---
        d.map("/play", self._on_transport, "playing")
        d.map("/record", self._on_transport, "recording")
        d.map("/pause", self._on_transport, "paused")
        d.map("/repeat", self._on_transport, "repeat")
        d.map("/stop", self._on_stop)

        # --- Tempo ---
        d.map("/tempo/raw", self._on_tempo_raw)
        d.map("/tempo/str", self._on_tempo_str)
        d.map("/beat/str", self._on_beat_str)
        d.map("/time/str", self._on_time_str)

        # --- Master ---
        d.map("/master/volume", self._on_master_float, "volume")
        d.map("/master/pan", self._on_master_float, "pan")
        d.map("/master/vu", self._on_master_float, "vu")
        d.map("/master/volume/str", self._on_master_str, "volume_str")

        # --- Track feedback (wildcard) ---
        d.map("/track/*/volume", self._on_track_float, "volume")
        d.map("/track/*/pan", self._on_track_float, "pan")
        d.map("/track/*/vu", self._on_track_float, "vu")
        d.map("/track/*/vu/L", self._on_track_float, "vu_l")
        d.map("/track/*/vu/R", self._on_track_float, "vu_r")
        d.map("/track/*/mute", self._on_track_bool, "mute")
        d.map("/track/*/solo", self._on_track_bool, "solo")
        d.map("/track/*/recarm", self._on_track_bool, "rec_arm")
        d.map("/track/*/select", self._on_track_select)
        d.map("/track/*/name", self._on_track_str, "name")
        d.map("/track/*/volume/str", self._on_track_str, "volume_str")
        d.map("/track/*/pan/str", self._on_track_str, "pan_str")
        d.map("/track/*/color", self._on_track_color)
        d.map("/track/*/automode", self._on_track_automode)

        # --- Send feedback ---
        d.map("/track/*/send/*/volume", self._on_send_float, "volume")
        d.map("/track/*/send/*/pan", self._on_send_float, "pan")
        d.map("/track/*/send/*/name", self._on_send_str, "name")
        d.map("/track/*/send/*/volume/str", self._on_send_str, "volume_str")

        # --- FX feedback ---
        d.map("/track/*/fx/*/name", self._on_fx_name)
        d.map("/track/*/fx/*/fxparam/*/value", self._on_fx_param_value)
        d.map("/track/*/fx/*/fxparam/*/name", self._on_fx_param_name)

        # Catch-all for debugging unknown messages
        d.set_default_handler(self._on_unknown)

    def _extract_track_num(self, address: str) -> int | None:
        """Extract track number from an OSC address."""
        m = _TRACK_RE.match(address)
        return int(m.group(1)) if m else None

    # --- Transport handlers ---
    # python-osc callback signature: callback(address, extra_args_list, *osc_values)

    def _on_transport(self, address: str, extra_args: list, *args):
        if not args or self.state is None:
            return
        field = extra_args[0]  # e.g. "playing"
        value = bool(int(args[0]))
        self.state.update_transport(**{field: value})
        log.info("Transport %s = %s", field, value)

    def _on_stop(self, address: str, *args):
        if self.state is None:
            return
        # args[0] might be the extra_args list if no extra args were passed
        # For map() with no extra args: callback(address, *osc_values)
        osc_args = args
        if osc_args and isinstance(osc_args[0], list):
            osc_args = osc_args[1:]  # skip empty extra_args list
        if osc_args and int(osc_args[0]):
            self.state.update_transport(playing=False, paused=False)

    # --- Tempo handlers ---

    def _on_tempo_raw(self, address: str, *args):
        osc_val = self._get_osc_value(args)
        if osc_val is not None and self.state:
            self.state.update_transport(tempo=float(osc_val))

    def _on_tempo_str(self, address: str, *args):
        osc_val = self._get_osc_value(args)
        if osc_val is not None and self.state:
            self.state.update_transport(tempo_str=str(osc_val))

    def _on_beat_str(self, address: str, *args):
        osc_val = self._get_osc_value(args)
        if osc_val is not None and self.state:
            self.state.update_transport(beat_str=str(osc_val))

    def _on_time_str(self, address: str, *args):
        osc_val = self._get_osc_value(args)
        if osc_val is not None and self.state:
            self.state.update_transport(time_str=str(osc_val))

    # --- Master handlers ---

    def _on_master_float(self, address: str, extra_args: list, *args):
        if args and self.state:
            field = extra_args[0]
            try:
                val = float(args[0])
            except (ValueError, TypeError):
                return
            if not (0.0 <= val <= 1.0):
                return
            self.state.update_master(**{field: val})

    def _on_master_str(self, address: str, extra_args: list, *args):
        if args and self.state:
            field = extra_args[0]
            self.state.update_master(**{field: str(args[0])})

    # --- Track handlers ---

    def _on_track_float(self, address: str, extra_args: list, *args):
        track_num = self._extract_track_num(address)
        if track_num is not None and args and self.state:
            field = extra_args[0]
            try:
                val = float(args[0])
            except (ValueError, TypeError):
                return  # skip string values like "-52.7dB"
            # Only accept normalized values (0.0-1.0) — reject dB values
            # that leak through wildcard matching
            if field in ("volume", "pan") and not (0.0 <= val <= 1.0):
                return
            if field.startswith("vu") and not (0.0 <= val <= 1.0):
                return
            self.state.update_track(track_num, **{field: val})

    def _on_track_bool(self, address: str, extra_args: list, *args):
        track_num = self._extract_track_num(address)
        if track_num is not None and args and self.state:
            field = extra_args[0]
            try:
                val = bool(int(float(args[0])))
            except (ValueError, TypeError):
                return
            self.state.update_track(track_num, **{field: val})

    def _on_track_select(self, address: str, *args):
        osc_val = self._get_osc_value(args)
        track_num = self._extract_track_num(address)
        if track_num is not None and osc_val is not None and self.state:
            selected = bool(int(osc_val))
            self.state.update_track(track_num, selected=selected)
            if selected:
                self.state.selected_track = track_num
                log.debug("Track %d selected", track_num)

    def _on_track_str(self, address: str, extra_args: list, *args):
        track_num = self._extract_track_num(address)
        if track_num is not None and args and self.state:
            field = extra_args[0]
            value = str(args[0])
            self.state.update_track(track_num, **{field: value})
            if field == "name":
                log.info("Track %d name: '%s'", track_num, value)

    def _on_track_automode(self, address: str, *args):
        """Handle track automation mode (0=trim, 1=read, 2=touch, 3=write, 4=latch)."""
        osc_val = self._get_osc_value(args)
        track_num = self._extract_track_num(address)
        if track_num is not None and osc_val is not None and self.state:
            try:
                mode = int(float(osc_val))
                self.state.update_track(track_num, automode=mode)
            except (ValueError, TypeError):
                pass

    # --- Send handlers ---

    def _on_send_float(self, address: str, extra_args: list, *args):
        m = _SEND_RE.match(address)
        if m and args and self.state:
            track_num = int(m.group(1))
            send_idx = int(m.group(2)) - 1  # 1-indexed → 0-indexed
            field = extra_args[0]
            try:
                val = float(args[0])
                if not (0.0 <= val <= 1.0):
                    return
                self.state.update_send(track_num, send_idx, **{field: val})
            except (ValueError, TypeError):
                pass

    def _on_send_str(self, address: str, extra_args: list, *args):
        m = _SEND_RE.match(address)
        if m and args and self.state:
            track_num = int(m.group(1))
            send_idx = int(m.group(2)) - 1
            field = extra_args[0]
            self.state.update_send(track_num, send_idx, **{field: str(args[0])})

    # --- FX handlers ---

    def _on_fx_name(self, address: str, *args):
        osc_val = self._get_osc_value(args)
        m = _FX_RE.match(address)
        if m and osc_val is not None and self.state:
            track_num = int(m.group(1))
            fx_idx = int(m.group(2)) - 1
            self.state.update_fx(track_num, fx_idx, name=str(osc_val))

    def _on_fx_param_value(self, address: str, *args):
        osc_val = self._get_osc_value(args)
        m = _FX_PARAM_RE.match(address)
        if m and osc_val is not None and self.state:
            track_num = int(m.group(1))
            fx_idx = int(m.group(2)) - 1
            param_idx = int(m.group(3)) - 1
            try:
                val = float(osc_val)
                self.state.update_fx_param(track_num, fx_idx, param_idx, value=val)
            except (ValueError, TypeError):
                pass

    def _on_fx_param_name(self, address: str, *args):
        osc_val = self._get_osc_value(args)
        m = _FX_PARAM_RE.match(address)
        if m and osc_val is not None and self.state:
            track_num = int(m.group(1))
            fx_idx = int(m.group(2)) - 1
            param_idx = int(m.group(3)) - 1
            self.state.update_fx_param(track_num, fx_idx, param_idx, name=str(osc_val))

    def _on_track_color(self, address: str, *args):
        """Handle track color from Reaper (sent as integer R|G|B packed)."""
        osc_val = self._get_osc_value(args)
        track_num = self._extract_track_num(address)
        if track_num is not None and osc_val is not None and self.state:
            try:
                color_int = int(osc_val)
                # Reaper sends color as 0xRRGGBB integer
                r = (color_int >> 16) & 0xFF
                g = (color_int >> 8) & 0xFF
                b = color_int & 0xFF
                self.state.update_track(track_num, color=(r, g, b))
                log.debug("Track %d color: (%d, %d, %d)", track_num, r, g, b)
            except (ValueError, TypeError):
                pass

    def _on_unknown(self, address: str, *args):
        log.debug("Unknown OSC: %s %s", address, args)
        self._msg_count += 1
        if self._msg_count <= 5:
            log.info("OSC received (unmatched): %s %s", address, args)
        elif self._msg_count == 6:
            log.info("(suppressing further unmatched OSC logs)")

    @staticmethod
    def _get_osc_value(args):
        """Extract the first OSC value from args, skipping extra_args list if present.

        For map() with no extra args, python-osc may still pass them differently.
        """
        if not args:
            return None
        # If first arg is a list, it's the extra_args from map() — skip it
        if isinstance(args[0], list):
            return args[1] if len(args) > 1 else None
        return args[0]
