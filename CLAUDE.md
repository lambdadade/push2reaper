# Push 2 Reaper Controller — AI Development Instructions

This file describes the project architecture for AI assistants working on this codebase.

## Project Overview

**push2reaper** is a Python daemon that bridges the Ableton Push 2 hardware controller with Reaper DAW via OSC on Linux. It runs an asyncio event loop that reads Push 2 input (MIDI), routes it through a modal interface system, sends OSC commands to Reaper, receives OSC feedback, and renders a 960x160 display at 30 fps.

**Python version**: 3.10+ (uses `X | Y` union syntax)
**Platform**: Linux only (Push 2 USB access via libusb, udev rules required)
**Entry point**: `src/main.py` → `Push2ReaperDaemon`

## Architecture

### Event Flow

```
Push 2 (USB/MIDI) → push2-python callbacks → EventBus → Daemon handlers → Active Mode
    ↓                                                                          ↓
Display ← Mode.render() ← PIL Image (960x160)                    OSC Client → Reaper
                                                                   OSC Server ← Reaper
                                                                       ↓
                                                                  ReaperState (cached)

                                                         PlaytimeClient → gRPC → Playtime
                                                              ↑ streaming ← gRPC ← Playtime
                                                              ↓
                                                         EventBus ("playtime_state_changed")
```

### Key Design Patterns

1. **Event Bus** (`core/event_bus.py`): Thread-safe pub/sub. Hardware publishes events (`button_pressed`, `pad_pressed`, `encoder_rotated`, etc.), daemon subscribes handlers. State changes also flow through the bus.

2. **Mode System** (`modes/base.py`): All modes inherit from `Mode` base class. The daemon holds `self._mode` and delegates all input events to it. Modes implement:
   - `enter(daemon)` / `exit(daemon)` — lifecycle hooks
   - `on_button(daemon, button, name) → bool` — return True if handled
   - `on_encoder(daemon, encoder, increment)`
   - `on_pad_pressed(daemon, row, col, velocity)` / `on_pad_released(...)` / `on_aftertouch(...)`
   - `on_state_changed(daemon, data)`
   - `render(daemon) → Image.Image` — called 30x/sec for display

3. **Scale overlay pattern**: Scale mode saves the previous mode on entry and restores it on exit. Unhandled buttons in scale mode trigger `toggle_scale_mode()` + re-dispatch.

4. **Global vs. mode-specific buttons**: Transport, undo/redo, navigation, mode switching, and octave buttons are handled in `main.py._on_button()` before delegating to the mode. This prevents modes from needing to re-implement transport controls.

5. **Pad color dedup**: `PadManager.set_color()` skips MIDI sends if the color hasn't changed. Modes that write pad colors directly (drum, session) must call `pads.invalidate_cache()` in their `exit()` method so the next mode's colors repaint correctly.

6. **OSC nudge pattern**: Encoder movements use `nudge_*()` methods that take `(current_value, increment)` and return the new clamped value. The caller updates both the OSC client and local state.

7. **Playtime gRPC integration** (`playtime/client.py`): `PlaytimeClient` connects to Helgobox's gRPC server (port 39051, service `generated.HelgoboxService`). Two daemon threads stream real-time updates:
   - `_stream_slot_updates` — receives `SlotPlayState` changes and `complete_persistent_data` (JSON with clip info including names)
   - `_stream_matrix_updates` — receives matrix-level state (track list, tempo, persistent data with full clip matrix structure)
   - State is stored in dicts keyed by `(col, row)` tuples: `slot_states`, `slot_has_content`, `slot_clip_names`
   - Changes publish `playtime_state_changed` events on the EventBus; session mode subscribes to update pad colors in real-time
   - The proto schema (`playtime/proto/helgobox.proto`) was reverse-engineered from the Helgobox Rust source — the `complete_persistent_data` fields are JSON strings, not protobuf messages
   - Processing order matters: `track_list` must be processed before `complete_persistent_data` so track ID → name mapping is available for column name resolution

### Module Map

| Module | Responsibility |
|--------|---------------|
| `main.py` | Daemon class, global button routing, mode switching, asyncio loop |
| `config.py` | YAML + .env config loading |
| `core/event_bus.py` | Thread-safe pub/sub |
| `core/logging_config.py` | Logging setup |
| `reaper/osc_client.py` | Send OSC to Reaper (all DAW control methods) |
| `reaper/osc_server.py` | Receive OSC from Reaper (dispatches to state) |
| `reaper/state.py` | `ReaperState` — thread-safe cached DAW state (`TrackInfo`, `FXInfo`) |
| `push2/hardware.py` | Push 2 connection, registers push2-python callbacks, creates sub-managers |
| `push2/buttons.py` | Button LED state management, `UPPER_ROW`/`LOWER_ROW` constants |
| `push2/encoders.py` | Encoder constants (`TRACK_ENCODERS`, `MASTER_ENCODER`, `TEMPO_ENCODER`) |
| `push2/pads.py` | `PadManager` — 8x8 pad grid colors with dedup cache |
| `push2/scales.py` | `ScaleState` — scale/root/layout definitions, `pad_note()` mapping |
| `push2/display.py` | PIL-to-BGR565 conversion, font loading |
| `push2/colors.py` | Custom color palette for push2-python |
| `modes/base.py` | `Mode` base class |
| `modes/mixer.py` | Default mode: volume/pan/send encoders, mute/solo/select buttons |
| `modes/scale.py` | Scale/root/layout selection overlay |
| `modes/drum.py` | Drum pads (4x4) + step sequencer grid |
| `modes/device.py` | FX parameter control via encoders |
| `modes/session.py` | Clip launcher for Playtime (via gRPC), real-time pad colors and clip names |
| `playtime/client.py` | `PlaytimeClient` — gRPC client for Playtime clip engine (state, streaming, triggers) |
| `playtime/helgobox_pb2.py` | Generated protobuf classes (from helgobox.proto) |
| `playtime/helgobox_pb2_grpc.py` | Generated gRPC stubs (manually fixed import path) |
| `playtime/proto/helgobox.proto` | Reconstructed protobuf schema for Helgobox gRPC API |
| `modes/browser.py` | FX browser trigger via Reaper actions |
| `modes/send.py` | Standalone send control (currently unused, sends integrated into mixer) |
| `ui/screens.py` | `MixerScreen` — 8 channel strips + transport bar |
| `ui/send_screen.py` | Send levels display |
| `ui/device_screen.py` | FX parameter knobs with arcs |
| `ui/drum_screen.py` | Drum pad + step grid info |
| `ui/scale_screen.py` | Scale selection display |
| `ui/session_screen.py` | Clip grid display |
| `ui/browser_screen.py` | Browser help text |

### ReaperState Structure

```python
class TrackInfo:
    index, name, volume (0.0-1.0), pan (0.0-1.0, 0.5=center)
    mute, solo, rec_arm, selected (bool)
    vu, vu_l, vu_r (0.0-1.0)
    volume_str, pan_str (display strings from Reaper)
    color (RGB tuple or None)
    automode (0=Trim, 1=Read, 2=Touch, 3=Write, 4=Latch)
    sends: list[dict] — [{name, volume, volume_str, pan}, ...]

class FXInfo:
    index, name
    params: list[dict] — [{name, value}, ...]

class ReaperState:
    tracks: dict[int, TrackInfo]  # 1-indexed track numbers
    playing, recording, paused, repeat: bool
    tempo: float
    master_volume, master_pan: float (0.0-1.0)
    bank_offset: int  # 0-indexed, first track in current bank
    selected_track: int
    fx: dict[int, list[FXInfo]]  # track_num → FX chain
```

### OSC Protocol

**Outgoing** (daemon → Reaper on port 8000):
- `/track/{N}/volume` (float 0.0-1.0), `/track/{N}/pan`, `/track/{N}/mute/toggle`, `/track/{N}/solo/toggle`
- `/track/{N}/send/{M}/volume` (M is 1-indexed)
- `/track/{N}/fx/{M}/fxparam/{P}/value` (M,P are 1-indexed in OSC, but 0-indexed in our state)
- `/track/{N}/automode` (int 0-4)
- `/vkb_midi/{ch}/note/{note}` (velocity int, 0=note-off)
- `/vkb_midi/{ch}/pitch` (float 0.0-1.0, 0.5=center)
- `/vkb_midi/{ch}/channelpressure`, `/vkb_midi/{ch}/polyaftertouch/{note}`
- `/play`, `/stop`, `/record`, `/click`, `/repeat`
- `/action` (int: Reaper command ID)

**Incoming** (Reaper → daemon on port 9000):
- Same paths as above — Reaper sends feedback for all subscribed parameters
- State updates go through `ReaperState.update_*()` methods which publish `state_changed` events

### Important Conventions

- **Track numbering**: Reaper OSC uses 1-indexed track numbers. Bank offset is 0-indexed. Track num = `bank_offset + 1 + encoder_index`.
- **FX/param indexing**: OSC paths use 1-indexed. Internal state (`FXInfo.index`, `param_idx`) is 0-indexed. The OSC client adds 1 when building paths.
- **Send indexing**: OSC paths use 1-indexed sends. Internal `track.sends` list is 0-indexed. The OSC client adds 1.
- **Normalized values**: All volumes and pans are 0.0-1.0. Pan 0.5 = center. The OSC client clamps all values.
- **Display**: 960x160 RGB PIL Images, converted to BGR565 numpy arrays for the Push 2 display.
- **Button constants**: Use `push2_python.constants` (e.g., `c.BUTTON_PLAY`, `c.BUTTON_MIX`). The `UPPER_ROW` and `LOWER_ROW` lists in `push2/buttons.py` map to the 8 buttons above/below the display.

### Adding a New Mode

1. Create `src/modes/my_mode.py` inheriting from `Mode`
2. Create `src/ui/my_screen.py` for the display rendering
3. In `main.py.__init__()`: instantiate the mode (`self._my_mode = MyMode()`)
4. In `main.py._on_button()`: add a button mapping to `switch_mode(self._my_mode)` (use toggle pattern)
5. Import the mode at the top of `main.py`
6. The mode's `enter()` should set up pad colors and button LEDs
7. The mode's `exit()` should call `pads.invalidate_cache()` + `pads.rebuild_grid()` if it wrote pad colors directly

### Adding OSC Parameters

1. **Outgoing**: Add method to `reaper/osc_client.py` (follow existing patterns, use `_send()`)
2. **Incoming**: Add regex + handler to `reaper/osc_server.py`, update `ReaperState` via `update_*()` methods
3. State changes automatically publish `state_changed` events via the event bus

## Running

```bash
cd push2reaper && source venv/bin/activate && python src/main.py
```

## Current State / Known Limitations

- **Session mode**: Connects directly to Playtime's gRPC API (port 39051) for clip control and real-time state feedback. No ReaLearn/MIDI bridging needed. Requires Helgobox with Playtime running in Reaper.
- **Browser mode**: Limited to opening Reaper windows via action IDs. No deep browser navigation (would need ReaScript).
- **Step sequencer**: Basic step toggle grid in drum mode. No actual MIDI item editing (would need ReaScript/reapy).
- **Send mode**: Integrated into mixer mode as the 3rd encoder mode. The standalone `modes/send.py` exists but isn't used.
- **Track colors**: Received from Reaper via OSC and displayed in mixer screen headers. Some Reaper configurations may not send colors.
- **No tests**: The project currently has no unit tests. All testing is done with hardware connected to Reaper.

## Dependencies

- `push2-python` (git: ffont/push2-python) — Push 2 hardware interface
- `python-osc` — OSC client/server
- `python-rtmidi` — MIDI I/O
- `Pillow` — Image rendering for display
- `PyYAML` — Config parsing
- `python-dotenv` — Environment variable loading
- `numpy` — BGR565 frame conversion
- `grpcio` — gRPC client for Playtime integration
- `protobuf` — Protocol Buffer serialization for gRPC
