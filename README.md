# Push 2 Reaper Controller

> **Beta Software** — This project is in early beta. Core features (mixer, transport, scales, drum pads) are functional, but some modes (session/clip launching, browser, device control) are incomplete or require additional setup. Expect bugs, missing features, and breaking changes.

A Linux daemon that turns the Ableton Push 2 into a fully functional hardware controller for [Reaper DAW](https://www.reaper.fm/) via OSC (Open Sound Control).

Provides mixer control, musical note input with configurable scales, drum pads, FX/device parameter editing, clip launching (via Playtime), and a real-time 960x160 display — all running natively on Linux.

## Features

### Mixer Mode (default)
- **8 channel strips** with volume faders, VU meters, pan indicators
- **Encoders 1-8**: Control volume, pan, or send levels (cycle with upper row buttons)
- **Lower row buttons**: Select+arm, mute, or solo tracks (toggle with Mute/Solo buttons)
- **Bank navigation**: Page Left/Right moves through tracks in groups of 8
- **Master encoder**: Master volume control
- **Tempo encoder**: BPM adjustment (20-300)

### Scale Mode (overlay)
- Press **Scale** button to toggle the scale selection overlay
- **15 scales**: Major, Minor, Dorian, Mixolydian, Lydian, Phrygian, Locrian, Harmonic Minor, Melodic Minor, Whole Tone, Pentatonic Major/Minor, Blues, Hungarian Minor, Diminished
- **12 root notes**: C through B
- **3 pad layouts**: 4th (Ableton default), 3rd, Sequential (chromatic)
- **In Key** toggle: Hide out-of-scale notes
- **Octave Up/Down**: Shift the pad grid range

### Drum Mode
- Press **Note** to enter drum mode (press again to return to mixer)
- **Bottom 4x4 pads**: 16 drum pads mapped to GM drum notes (channel 10)
- **Top 2 rows**: 16-step sequencer grid for the selected drum pad
- **Bank navigation**: Upper row buttons shift drum note bank by 16

### Device Mode
- Press **Device** to enter FX parameter control (press again to return)
- **Encoders 1-8**: Control 8 FX parameters at a time
- **Upper row**: Navigate parameter banks (buttons 1-2) and FX chain (buttons 7-8)
- **Display**: FX name with 8 parameter knobs showing arcs and percentages

### Session Mode (Playtime integration)
- Press **Session** to enter clip launcher mode
- **8x8 pad grid**: Trigger clip slots via MIDI (requires [Helgobox/Playtime](https://www.helgoboss.org/projects/helgobox/) + ReaLearn bridge)
- **Upper row**: Scene bank navigation
- **Lower row**: Stop clips per track
- See [docs/playtime-setup.md](docs/playtime-setup.md) for integration setup

### Browser Mode
- Press **Browse** to open Reaper's FX browser
- **Upper row**: FX Browser, FX Chain, Insert Virtual Instrument
- Pads still play notes while browsing

### Global Controls (always active)
| Button | Action |
|--------|--------|
| Play / Stop / Record | Transport controls |
| Metronome | Toggle click track |
| Repeat | Toggle loop mode |
| Undo | Undo (Shift+Undo = Redo) |
| Octave Up/Down | Shift pad note range |
| Left/Right arrows | Select prev/next track |
| Page Left/Right | Navigate track banks (8 at a time) |
| Add Device | Open Reaper FX browser |
| Add Track | Insert new track |
| Automate | Cycle automation mode (Trim/Read/Touch/Write/Latch) |
| Touchstrip | Pitch bend |

## Requirements

- **OS**: Linux (tested on Debian Trixie/Testing)
- **Python**: 3.10+
- **Hardware**: Ableton Push 2 connected via USB
- **DAW**: Reaper with OSC control surface enabled
- **System packages**: `libusb-1.0-0-dev` (for Push 2 USB access)

## Installation

### 1. Clone and set up the virtual environment

```bash
cd ~/AI  # or wherever you want it
git clone <repo-url> push2reaper
cd push2reaper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Install udev rules (one-time, for non-root USB access)

```bash
sudo bash scripts/install_udev_rules.sh
```

This creates `/etc/udev/rules.d/50-push2.rules` so you can access the Push 2 without root. Make sure your user is in the `plugdev` group:

```bash
sudo usermod -a -G plugdev $USER
```

Log out and back in (or unplug/replug the Push 2) for the rules to take effect.

### 3. Configure Reaper OSC

In Reaper:
1. Go to **Preferences > Control/OSC/Web**
2. Click **Add** and select **OSC (Open Sound Control)**
3. Set:
   - **Mode**: Configure device IP + local port
   - **Device IP**: `127.0.0.1`
   - **Device port**: `9000` (where the daemon listens)
   - **Local listen port**: `8000` (where Reaper listens)
4. Select the appropriate **pattern config** file or use the default
5. Click **OK**

Then enable the virtual MIDI keyboard (required for pad note input):
1. Go to **View > Virtual MIDI Keyboard** (or press **Alt+B**)
2. The virtual keyboard must be **active** for pad notes, aftertouch, and pitch bend to reach armed tracks
3. Do **not** configure a hardware MIDI device for the Push 2 in Reaper — all MIDI goes through OSC's virtual keyboard to avoid double notes

### 4. Run the daemon

```bash
bash scripts/start_daemon.sh
```

Or manually:

```bash
cd push2reaper
source venv/bin/activate
python src/main.py
```

## Configuration

### config/default_mappings.yaml

```yaml
osc:
  reaper_ip: "127.0.0.1"    # Reaper's IP address
  reaper_port: 8000          # Port Reaper listens on
  listen_port: 9000          # Port this daemon listens on

push2:
  fps: 30                    # Display refresh rate

encoders:
  sensitivity: 1.0           # Encoder scaling factor
```

### Environment variables (.env)

Copy `.env.example` to `.env` to override config:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `REAPER_OSC_IP` | `127.0.0.1` | Reaper IP address |
| `REAPER_OSC_PORT` | `8000` | Reaper OSC listen port |
| `LISTEN_PORT` | `9000` | Daemon OSC listen port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `DISPLAY_FPS` | `30` | Display refresh rate |

## Project Structure

```
push2reaper/
├── config/
│   └── default_mappings.yaml     # OSC, display, button config
├── scripts/
│   ├── install_udev_rules.sh     # Udev setup for USB access
│   └── start_daemon.sh           # Launcher script
├── src/
│   ├── main.py                   # Daemon entry point + global event routing
│   ├── config.py                 # YAML + .env config loader
│   ├── core/
│   │   ├── event_bus.py          # Thread-safe pub/sub system
│   │   └── logging_config.py     # Logging setup
│   ├── reaper/
│   │   ├── osc_client.py         # Sends OSC to Reaper (volume, transport, notes, etc.)
│   │   ├── osc_server.py         # Receives OSC feedback from Reaper
│   │   └── state.py              # Cached Reaper state (tracks, transport, FX)
│   ├── push2/
│   │   ├── hardware.py           # Push 2 connection + event handler registration
│   │   ├── buttons.py            # Button LED management
│   │   ├── encoders.py           # Encoder touch tracking
│   │   ├── pads.py               # Pad grid color management
│   │   ├── scales.py             # Musical scale definitions + pad note mapping
│   │   ├── display.py            # PIL-to-BGR565 frame conversion
│   │   └── colors.py             # Custom color palette registration
│   ├── modes/
│   │   ├── base.py               # Mode base class (lifecycle + event interface)
│   │   ├── mixer.py              # Mixer mode (volume/pan/send/mute/solo)
│   │   ├── scale.py              # Scale selection overlay
│   │   ├── drum.py               # Drum pads + step sequencer
│   │   ├── device.py             # FX parameter control
│   │   ├── session.py            # Clip launcher (Playtime)
│   │   ├── browser.py            # FX browser
│   │   └── send.py               # Standalone send control
│   └── ui/
│       ├── screens.py            # MixerScreen (8 channel strips + transport bar)
│       ├── send_screen.py        # Send levels display
│       ├── device_screen.py      # FX parameter knobs display
│       ├── drum_screen.py        # Drum pad + step grid display
│       ├── scale_screen.py       # Scale/root/layout selection display
│       ├── session_screen.py     # Clip grid display
│       └── browser_screen.py     # Browser help display
├── requirements.txt
├── setup.py
└── .env.example
```

## How It Works

```
Push 2 (USB)          push2reaper daemon              Reaper DAW
┌──────────┐    MIDI    ┌──────────────────┐   OSC    ┌──────────┐
│ Pads     │───────────>│ Event Bus        │────────> │ Tracks   │
│ Encoders │───────────>│   ↓              │────────> │ Transport│
│ Buttons  │───────────>│ Active Mode      │────────> │ FX       │
│ Display  │<───────────│ (mixer/drum/...) │<──────── │ Feedback │
│ LEDs     │<───────────│ UI Renderer      │<──────── │ State    │
└──────────┘            └──────────────────┘          └──────────┘
                            30 fps display
```

1. **Push 2 hardware** sends MIDI events (pad presses, encoder turns, button presses)
2. **push2-python** library receives them and publishes to the **Event Bus**
3. The **active Mode** handles events (e.g., encoder turn → adjust volume)
4. Mode calls **OSC Client** to send commands to Reaper
5. **OSC Server** receives feedback from Reaper and updates **ReaperState**
6. State changes trigger display updates
7. **UI Screen** renders a PIL image, converted to BGR565 and sent to the Push 2 display at 30 fps

## Troubleshooting

### Push 2 not detected
- Check USB connection: `lsusb | grep 2982`
- Verify udev rules: `ls -la /etc/udev/rules.d/50-push2.rules`
- Check group membership: `groups | grep plugdev`
- Try unplugging and replugging the Push 2

### No response from Reaper
- Verify Reaper OSC is configured (Preferences > Control/OSC/Web)
- Check ports match: daemon listens on 9000, sends to 8000
- Check Reaper's OSC log: Preferences > Control/OSC/Web > Log

### Pads don't produce sound
- **Virtual MIDI keyboard must be active**: View > Virtual MIDI Keyboard (Alt+B)
- Make sure the target track is **selected and record-armed** (use lower row buttons in mixer mode)
- Do **not** add Push 2 as a MIDI device in Reaper — this causes double notes

### Display shows but controls don't work
- Ensure Reaper is the active/focused DAW
- Check that the OSC device port in Reaper matches `listen_port` (9000)
- Verify tracks exist in the Reaper project

## License

MIT
