# Playtime Integration Setup

The Push 2 Session mode connects directly to Playtime's gRPC API for clip control and real-time state feedback. No ReaLearn or MIDI bridging is required.

## Architecture

```
Push 2 pads → push2reaper daemon → gRPC (port 39051) → Playtime clip engine
                                  ← gRPC streaming    ← Playtime state updates
```

## Prerequisites

1. **Reaper** running
2. **Helgobox** extension installed (includes Playtime)
   - Download: https://www.helgoboss.org/projects/helgobox/
3. **Playtime** instance active in Reaper (Helgobox VST on a track with the clip matrix set up)
4. **push2reaper daemon** running

## Setup

1. Add Helgobox as an FX on a track in Reaper
2. Open Playtime and create your clip matrix (columns/tracks and scenes/rows)
3. Add clips to slots as desired
4. Start the push2reaper daemon — it will auto-connect to Playtime's gRPC server on port 39051
5. Press the Session button on Push 2

The daemon automatically:
- Discovers the matrix dimensions (columns and rows)
- Fetches which slots have content
- Streams real-time play state updates
- Shows clip states on both the display and pad LEDs

## Controls

| Control | Action |
|---------|--------|
| **Pads** | Toggle play/stop for the clip at that position |
| **Upper row 1-2** | Scene bank navigation (← →) |
| **Upper row 3-8** | Trigger scenes (play all clips in a row) |
| **Lower row** | Stop all clips in a column (track) |
| **Encoders** | Track volume |

## Pad Colors

| Color | Meaning |
|-------|---------|
| Dark gray | Empty slot (no clip) |
| White | Has clip, stopped |
| Green | Playing |
| Red | Recording |
| Yellow | Queued (scheduled to play/record) |

## Configuration

The gRPC port can be configured in your config YAML:

```yaml
playtime:
  host: 127.0.0.1
  port: 39051  # Helgobox gRPC server port
```

Default port is 39051. Check Helgobox settings if your server runs on a different port (look for `realearn.ini` configuration).

## Troubleshooting

### "Playtime not available" in logs
- Verify Helgobox is loaded as an FX in Reaper
- Check the gRPC port: `ss -tlnp | grep 39051`
- The Helgobox server starts when the FX is loaded; make sure Reaper is running first

### Clips don't trigger
- Verify the gRPC connection with: `python -c "from playtime.client import PlaytimeClient; c = PlaytimeClient(); print(c.connect())"`
- Check that Playtime has clips in the slots you're triggering
- The daemon log shows `Triggered slot [col, row]` for each pad press

### Display shows empty grid
- Session mode needs Playtime connected to show clip states
- Without Playtime, all slots show as empty (dark gray)
- Check daemon logs for "Connected to Playtime gRPC" message

## Technical Details

The integration uses a reconstructed protobuf schema (`src/playtime/proto/helgobox.proto`) based on analysis of the Helgobox source code. The gRPC service is `generated.HelgoboxService` running on HTTP/2.

Key gRPC methods used:
- `TriggerSlot` — play/stop individual clips
- `TriggerRow` — trigger scenes
- `TriggerColumn` — stop all clips in a column
- `TriggerMatrix` — stop all clips
- `GetOccasionalSlotUpdates` — stream real-time clip state changes
- `GetOccasionalMatrixUpdates` — stream matrix state (tempo, track list, persistent data)
