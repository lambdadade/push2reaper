# Playtime / ReaLearn Integration Setup

This guide explains how to set up the Session mode's clip launching to work with Helgoboss Playtime in Reaper via ReaLearn.

## Overview

The Push 2 Session mode sends MIDI notes on channel 16 to trigger clip slots. Since Playtime doesn't have a direct OSC API, we use **ReaLearn** (part of Helgobox) as a bridge to translate these MIDI messages into Playtime clip actions.

```
Push 2 pads → push2reaper daemon → OSC note_on (ch 16) → Reaper vkb_midi
    → ReaLearn mapping → Playtime slot trigger
```

### Pad-to-MIDI Mapping

| Pad Position | MIDI Note | Purpose |
|-------------|-----------|---------|
| (row, col) | row * 8 + col | Trigger clip at slot [row][col] |
| Row 0, Col 0 | Note 0 | Top-left clip slot |
| Row 7, Col 7 | Note 63 | Bottom-right clip slot |
| Notes 120-127 | — | Stop clips for tracks 1-8 |

All notes are sent on **MIDI channel 16** (0-indexed: channel 15).

## Prerequisites

1. **Reaper** installed and running
2. **Helgobox** extension installed (includes both ReaLearn and Playtime)
   - Download from: https://www.helgoboss.org/projects/helgobox/
3. **push2reaper daemon** running with OSC configured
4. Reaper OSC control surface enabled (port 8000 receive, port 9000 send)

## Step 1: Add Helgobox to a Track

1. In Reaper, create a new track (or use the Master track)
2. Open the track's **FX chain** (click the FX button)
3. Click **Add** and search for **"Helgobox"**
4. Add it to the FX chain

The Helgobox window should open showing ReaLearn's interface with Input, Output, and mapping configuration.

## Step 2: Access Playtime

On Linux, Playtime's embedded UI doesn't work inside the FX window. Instead, access it via web browser:

1. In the Helgobox FX window, look for an **"App" button** or **globe icon** — this opens the web UI
2. If no button is visible, try opening `http://localhost:39051` in your browser
3. If that port doesn't respond, check Helgobox preferences for the web server port
4. The web UI should show both ReaLearn and Playtime tabs

**Alternative**: If the web UI isn't available, you can still create ReaLearn mappings without the Playtime visual UI — the mappings themselves control Playtime's engine.

## Step 3: Configure ReaLearn Input

ReaLearn needs to receive the MIDI notes that push2reaper sends via Reaper's virtual keyboard:

1. In the Helgobox/ReaLearn window, go to **Input** settings
2. Set the input to receive from **"<FX input>"** (this captures Reaper's virtual MIDI keyboard output)
3. The virtual keyboard MIDI (which our daemon sends via OSC `/vkb_midi/15/note/*`) will arrive as MIDI on channel 16

## Step 4: Create Clip Trigger Mappings

For each clip slot you want to control, create a ReaLearn mapping:

### Single Slot Mapping

1. In ReaLearn's mapping list, click **Add** to create a new mapping
2. **Source** section:
   - Type: **MIDI note**
   - Channel: **16**
   - Note number: The note for this slot (e.g., 0 for row 0/col 0)
3. **Target** section:
   - Type: **Playtime** > **Slot management action** (or similar Playtime target)
   - Column (track): The track index
   - Row (scene): The scene index
   - Action: **Trigger** (or **Record if empty**)

### Batch Mapping (recommended)

Instead of creating 64 individual mappings, use ReaLearn's **"Learn many"** or group mapping features:

1. Create a mapping with:
   - Source: MIDI note, Channel 16
   - Target: Playtime slot action
2. Use ReaLearn's parameter expressions to dynamically map note numbers to row/column:
   - Column = `note % 8` (note modulo 8)
   - Row = `note / 8` (note divided by 8, integer)

Consult ReaLearn's documentation for the exact syntax of dynamic/computed targets.

### Scene Trigger Mappings

For triggering entire scenes (all clips in a row):

1. **Source**: MIDI note on channel 16, specific note per scene
2. **Target**: Playtime > **Row action** > Trigger

### Stop Clip Mappings

For stopping clips per track (lower row buttons in session mode):

1. **Source**: MIDI notes 120-127 on channel 16
2. **Target**: Playtime > **Column action** > Stop
3. Map note 120 → track 1, note 121 → track 2, etc.

## Step 5: Verify

1. Start the push2reaper daemon
2. Enter Session mode (press **Session** button on Push 2)
3. Press a pad — you should see:
   - In daemon logs: `Session pad (row,col) → clip trigger note N`
   - In Reaper's OSC log: `/vkb_midi/15/note/N` messages
   - In ReaLearn: The mapping should show activity (input indicator lights up)
   - In Playtime: The corresponding clip slot should trigger

## Troubleshooting

### MIDI notes not reaching ReaLearn
- Verify OSC is working: Check Reaper's OSC log for `/vkb_midi/15/note/*` messages
- Ensure Helgobox FX is on a track that receives the virtual MIDI (try the Master track)
- Check ReaLearn input is set to `<FX input>`

### Clips don't trigger
- Verify the ReaLearn mapping target is set to a Playtime action (not a generic MIDI target)
- Check that Playtime has clips loaded in the slots you're trying to trigger
- Ensure column/row indices in the mapping match the clip matrix layout

### Web UI not loading
- Try different ports: `http://localhost:39051`, `http://localhost:39052`
- Check if Helgobox's web server is enabled in its settings
- On Linux, the embedded UI won't work — the browser approach is the only option

## Alternative Approach: Direct OSC to ReaLearn

Instead of going through Reaper's virtual keyboard, ReaLearn can listen on its own OSC port. This may be more reliable:

1. In ReaLearn settings, enable the **OSC input device** with a custom port (e.g., 10000)
2. Modify the push2reaper session mode to send OSC directly to ReaLearn's port instead of using `vkb_midi`
3. This requires changes to `src/modes/session.py` and `src/reaper/osc_client.py`

This approach is not yet implemented but is a planned improvement.

## Clip State Feedback

Currently, the session mode maintains an internal `_clip_states` grid but doesn't receive real-time clip state updates from Playtime. Future work:

- ReaLearn can send feedback when clip states change
- This feedback could update `_clip_states` and pad colors
- Requires configuring ReaLearn feedback mappings (Playtime state → MIDI/OSC output)
