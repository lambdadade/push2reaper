"""Playtime gRPC client.

Connects directly to Playtime's gRPC server (same API as the Helgoland app)
for bidirectional clip control and real-time state streaming.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING

import grpc

from playtime import helgobox_pb2 as pb
from playtime import helgobox_pb2_grpc as pb_grpc

if TYPE_CHECKING:
    from core.event_bus import EventBus

log = logging.getLogger("push2reaper.playtime.client")

# Clip slot states for the session mode grid
SLOT_EMPTY = 0
SLOT_STOPPED = 1      # has content, not playing
SLOT_PLAYING = 2
SLOT_RECORDING = 3
SLOT_QUEUED = 4        # scheduled for play/record start


def _play_state_to_slot_state(ps: int) -> int:
    """Map Playtime's SlotPlayState enum to our simplified slot state."""
    if ps == pb.SLOT_PLAY_STATE_UNKNOWN:
        return SLOT_EMPTY
    if ps == pb.SLOT_PLAY_STATE_STOPPED:
        return SLOT_STOPPED
    if ps == pb.SLOT_PLAY_STATE_PLAYING:
        return SLOT_PLAYING
    if ps == pb.SLOT_PLAY_STATE_RECORDING:
        return SLOT_RECORDING
    if ps in (pb.SLOT_PLAY_STATE_SCHEDULED_FOR_PLAY_START,
              pb.SLOT_PLAY_STATE_SCHEDULED_FOR_PLAY_RESTART,
              pb.SLOT_PLAY_STATE_SCHEDULED_FOR_RECORD_START,
              pb.SLOT_PLAY_STATE_IGNITED):
        return SLOT_QUEUED
    if ps in (pb.SLOT_PLAY_STATE_SCHEDULED_FOR_PLAY_STOP,
              pb.SLOT_PLAY_STATE_SCHEDULED_FOR_RECORD_STOP):
        return SLOT_STOPPED
    if ps == pb.SLOT_PLAY_STATE_PAUSED:
        return SLOT_STOPPED
    return SLOT_EMPTY


class PlaytimeClient:
    """gRPC client for Playtime clip engine."""

    def __init__(self, host: str = "localhost", port: int = 39051,
                 matrix_id: int = 0, event_bus: EventBus | None = None):
        self.host = host
        self.port = port
        self.matrix_id = matrix_id
        self.event_bus = event_bus
        self._channel: grpc.Channel | None = None
        self._stub: pb_grpc.HelgoboxServiceStub | None = None
        self._connected = False
        self._lock = threading.Lock()

        # State: clip grid
        # slot_states[col][row] = SLOT_EMPTY/STOPPED/PLAYING/RECORDING/QUEUED
        self.slot_states: dict[tuple[int, int], int] = {}
        # slot_has_content[col][row] = True if slot has clips
        self.slot_has_content: dict[tuple[int, int], bool] = {}
        # Matrix dimensions discovered from server
        self.num_columns = 0
        self.num_rows = 0
        # Track info from Playtime
        self.track_names: dict[int, str] = {}  # track_list_index → name
        self._track_id_to_name: dict[str, str] = {}  # track_id → name
        self.column_names: dict[int, str] = {}  # column_index → display name
        self.tempo = 120.0

        # Streaming threads
        self._slot_stream_thread: threading.Thread | None = None
        self._matrix_stream_thread: threading.Thread | None = None
        self._running = False

    def connect(self) -> bool:
        """Connect to Playtime's gRPC server."""
        try:
            self._channel = grpc.insecure_channel(f"{self.host}:{self.port}")
            self._stub = pb_grpc.HelgoboxServiceStub(self._channel)

            # Test connection with a quick matrix update request
            req = pb.GetOccasionalMatrixUpdatesRequest(matrix_id=self.matrix_id)
            stream = self._stub.GetOccasionalMatrixUpdates(req, timeout=3)
            first = next(stream)
            stream.cancel()

            self._connected = True
            log.info("Connected to Playtime gRPC at %s:%d", self.host, self.port)

            # Get initial state
            self._fetch_initial_state()
            return True
        except Exception as e:
            log.error("Failed to connect to Playtime: %s", e)
            self._connected = False
            return False

    def start_streaming(self) -> None:
        """Start background threads for real-time state updates."""
        if not self._connected:
            return
        self._running = True

        self._slot_stream_thread = threading.Thread(
            target=self._stream_slot_updates,
            name="playtime-slots",
            daemon=True,
        )
        self._slot_stream_thread.start()

        self._matrix_stream_thread = threading.Thread(
            target=self._stream_matrix_updates,
            name="playtime-matrix",
            daemon=True,
        )
        self._matrix_stream_thread.start()

        log.info("Playtime streaming started")

    def stop(self) -> None:
        """Stop streaming and close connection."""
        self._running = False
        if self._channel:
            self._channel.close()
        self._connected = False
        log.info("Playtime client stopped")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # --- Trigger actions ---

    def trigger_slot(self, col: int, row: int) -> None:
        """Toggle play/stop for a clip slot."""
        if not self._connected:
            return
        try:
            req = pb.TriggerSlotRequest(
                slot_address=pb.FullSlotAddress(
                    matrix_id=self.matrix_id,
                    slot_address=pb.SlotAddress(column_index=col, row_index=row),
                ),
                action=pb.TRIGGER_SLOT_ACTION_TRIGGER,
            )
            self._stub.TriggerSlot(req, timeout=2)
            log.info("Triggered slot [%d, %d]", col, row)
        except grpc.RpcError as e:
            log.warning("TriggerSlot error: %s", e.details())

    def stop_slot(self, col: int, row: int) -> None:
        """Explicitly stop a clip slot."""
        if not self._connected:
            return
        try:
            req = pb.TriggerSlotRequest(
                slot_address=pb.FullSlotAddress(
                    matrix_id=self.matrix_id,
                    slot_address=pb.SlotAddress(column_index=col, row_index=row),
                ),
                action=pb.TRIGGER_SLOT_ACTION_STOP,
            )
            self._stub.TriggerSlot(req, timeout=2)
        except grpc.RpcError as e:
            log.warning("StopSlot error: %s", e.details())

    def trigger_scene(self, row: int) -> None:
        """Trigger a scene (play all clips in a row)."""
        if not self._connected:
            return
        try:
            req = pb.TriggerRowRequest(
                row_address=pb.FullRowAddress(
                    matrix_id=self.matrix_id, row_index=row,
                ),
                action=pb.TRIGGER_ROW_ACTION_PLAY,
            )
            self._stub.TriggerRow(req, timeout=2)
            log.info("Triggered scene %d", row)
        except grpc.RpcError as e:
            log.warning("TriggerScene error: %s", e.details())

    def stop_column(self, col: int) -> None:
        """Stop all clips in a column (track)."""
        if not self._connected:
            return
        try:
            req = pb.TriggerColumnRequest(
                column_address=pb.FullColumnAddress(
                    matrix_id=self.matrix_id, column_index=col,
                ),
                action=pb.TRIGGER_COLUMN_ACTION_STOP,
            )
            self._stub.TriggerColumn(req, timeout=2)
            log.info("Stopped column %d", col)
        except grpc.RpcError as e:
            log.warning("StopColumn error: %s", e.details())

    def stop_all(self) -> None:
        """Stop all clips in the matrix."""
        if not self._connected:
            return
        try:
            req = pb.TriggerMatrixRequest(
                matrix_id=self.matrix_id,
                action=pb.TRIGGER_MATRIX_ACTION_STOP_ALL_CLIPS,
            )
            self._stub.TriggerMatrix(req, timeout=2)
            log.info("Stopped all clips")
        except grpc.RpcError as e:
            log.warning("StopAll error: %s", e.details())

    # --- State queries ---

    def get_slot_state(self, col: int, row: int) -> int:
        """Get current state for a slot. Returns SLOT_EMPTY if unknown."""
        return self.slot_states.get((col, row), SLOT_EMPTY)

    def get_grid_state(self, num_cols: int = 8, num_rows: int = 8,
                       col_offset: int = 0, row_offset: int = 0) -> list[list[int]]:
        """Get an 8x8 grid of slot states for the display.

        Returns grid[row][col] to match session mode's grid layout.
        Slots with content but stopped show as SLOT_STOPPED (1).
        Slots without content show as SLOT_EMPTY (0).
        """
        grid = []
        for row in range(num_rows):
            row_states = []
            for col in range(num_cols):
                ac = col + col_offset
                ar = row + row_offset
                state = self.slot_states.get((ac, ar), SLOT_EMPTY)
                # If slot is "stopped" but has no content, show as empty
                if state == SLOT_STOPPED and not self.slot_has_content.get((ac, ar), False):
                    state = SLOT_EMPTY
                row_states.append(state)
            grid.append(row_states)
        return grid

    # --- Internal: initial state fetch ---

    def _fetch_initial_state(self) -> None:
        """Fetch complete initial state from Playtime."""
        self._fetch_initial_slots()
        self._fetch_initial_matrix()

    def _fetch_initial_slots(self) -> None:
        """Get initial slot play states."""
        try:
            req = pb.GetOccasionalSlotUpdatesRequest(matrix_id=self.matrix_id)
            stream = self._stub.GetOccasionalSlotUpdates(req, timeout=5)
            first = next(stream)
            self._process_slot_updates(first)
            stream.cancel()
        except Exception as e:
            log.warning("Failed to fetch initial slot states: %s", e)

    def _fetch_initial_matrix(self) -> None:
        """Get initial matrix state (including persistent data with clip info)."""
        try:
            req = pb.GetOccasionalMatrixUpdatesRequest(matrix_id=self.matrix_id)
            stream = self._stub.GetOccasionalMatrixUpdates(req, timeout=5)
            first = next(stream)
            self._process_matrix_updates(first)
            stream.cancel()
        except Exception as e:
            log.warning("Failed to fetch initial matrix state: %s", e)

    # --- Internal: streaming ---

    def _stream_slot_updates(self) -> None:
        """Background thread: stream real-time slot state changes."""
        while self._running:
            try:
                req = pb.GetOccasionalSlotUpdatesRequest(matrix_id=self.matrix_id)
                stream = self._stub.GetOccasionalSlotUpdates(req)
                for update in stream:
                    if not self._running:
                        break
                    changed = self._process_slot_updates(update)
                    if changed and self.event_bus:
                        self.event_bus.publish("playtime_state_changed",
                                               {"type": "slots"})
            except grpc.RpcError as e:
                if self._running:
                    log.warning("Slot stream error: %s, reconnecting...", e.code())
                    import time
                    time.sleep(2)
            except Exception as e:
                if self._running:
                    log.error("Slot stream unexpected error: %s", e)
                    import time
                    time.sleep(2)

    def _stream_matrix_updates(self) -> None:
        """Background thread: stream matrix-level changes."""
        while self._running:
            try:
                req = pb.GetOccasionalMatrixUpdatesRequest(matrix_id=self.matrix_id)
                stream = self._stub.GetOccasionalMatrixUpdates(req)
                for update in stream:
                    if not self._running:
                        break
                    self._process_matrix_updates(update)
            except grpc.RpcError as e:
                if self._running:
                    log.warning("Matrix stream error: %s, reconnecting...", e.code())
                    import time
                    time.sleep(2)
            except Exception as e:
                if self._running:
                    log.error("Matrix stream unexpected error: %s", e)
                    import time
                    time.sleep(2)

    # --- Internal: message processing ---

    def _process_slot_updates(self, reply) -> bool:
        """Process a GetOccasionalSlotUpdatesReply. Returns True if any state changed."""
        changed = False
        with self._lock:
            for su in reply.slot_updates:
                col = su.slot_address.column_index
                row = su.slot_address.row_index
                field = su.WhichOneof("update")
                if field == "play_state":
                    new_state = _play_state_to_slot_state(su.play_state)
                    old_state = self.slot_states.get((col, row))
                    if old_state != new_state:
                        self.slot_states[(col, row)] = new_state
                        changed = True
                        if new_state != SLOT_STOPPED:
                            log.debug("Slot [%d,%d] → %s", col, row,
                                      pb.SlotPlayState.Name(su.play_state))
                elif field == "complete_persistent_data":
                    # Persistent data contains clip info
                    self._parse_slot_persistent_data(col, row,
                                                     su.complete_persistent_data)
        return changed

    def _process_matrix_updates(self, reply) -> None:
        """Process a GetOccasionalMatrixUpdatesReply.

        Process track_list first so _track_id_to_name is populated
        before parsing persistent data.
        """
        # First pass: track_list (needed for column name resolution)
        for mu in reply.matrix_updates:
            if mu.WhichOneof("update") == "track_list":
                for i, track in enumerate(mu.track_list.tracks):
                    self.track_names[i] = track.name or ""
                    if track.id:
                        self._track_id_to_name[track.id] = track.name or ""

        # Second pass: everything else
        for mu in reply.matrix_updates:
            field = mu.WhichOneof("update")
            if field == "track_list":
                continue  # already processed
            elif field == "tempo":
                self.tempo = mu.tempo
            elif field == "complete_persistent_data":
                self._parse_matrix_persistent_data(mu.complete_persistent_data)
            elif field == "everything_has_changed" and mu.everything_has_changed:
                self._fetch_initial_state()
                if self.event_bus:
                    self.event_bus.publish("playtime_state_changed",
                                           {"type": "full_refresh"})

    def _parse_matrix_persistent_data(self, data_str: str) -> None:
        """Parse the matrix JSON to discover which slots have clips."""
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            return

        columns = data.get("columns", [])
        self.num_columns = len(columns)

        # Find max rows from the rows array
        rows = data.get("rows", [])
        self.num_rows = len(rows)

        # Clear and rebuild content map + column names
        with self._lock:
            self.slot_has_content.clear()
            self.column_names.clear()
            for col_idx, col_data in enumerate(columns):
                # Map column to its track name
                track_id = col_data.get("clip_play_settings", {}).get("track", "")
                if track_id and track_id in self._track_id_to_name:
                    self.column_names[col_idx] = self._track_id_to_name[track_id]
                else:
                    self.column_names[col_idx] = f"Col {col_idx + 1}"

                slots = col_data.get("slots", [])
                for slot_data in slots:
                    row_idx = slot_data.get("row", 0)
                    clips = slot_data.get("clips", [])
                    has_content = len(clips) > 0
                    self.slot_has_content[(col_idx, row_idx)] = has_content

        log.info("Matrix: %d columns, %d rows, %d slots with content",
                 self.num_columns, self.num_rows,
                 sum(1 for v in self.slot_has_content.values() if v))

        if self.event_bus:
            self.event_bus.publish("playtime_state_changed",
                                   {"type": "matrix_data"})

    def _parse_slot_persistent_data(self, col: int, row: int, data_str: str) -> None:
        """Parse individual slot persistent data."""
        try:
            data = json.loads(data_str)
            clips = data.get("clips", [])
            self.slot_has_content[(col, row)] = len(clips) > 0
        except json.JSONDecodeError:
            pass
