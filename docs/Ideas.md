# Feature Ideas

## Guitar Player Features

### Looper Control Mode
Control a looper (Reaper SWS looper actions or a looper VST plugin) from the Push 2.
- Pad rows or buttons for Record / Overdub / Play / Stop / Clear / Undo per loop layer
- Display loop state + waveform on Push 2 screen
- Lower row buttons for multiple loop tracks
- Visual feedback: recording = red, playing = green, overdubbing = orange

### Touchstrip as Wah / Expression Pedal
Currently the touchstrip is mapped to pitch bend. For guitar, a wah or expression pedal mapping is more useful.
- Toggle between pitch bend and CC control (e.g., CC11 expression, or a custom CC mapped to a wah plugin)
- Shift+Touchstrip to switch between modes
- Visual indicator on display showing current touchstrip mode

### Tap Tempo
- Map a button (e.g., Shift+Metronome or a dedicated pad) to tap tempo
- Essential for syncing delays when playing live
- Display current BPM with visual beat indicator

### Input Monitor Toggle
- Quick button to toggle input monitoring on the selected track (Reaper action 40495)
- Essential when switching between playing and playback
- LED feedback: lit when monitoring is active

### Tuner Mode
- Read input signal frequency via ReaScript/reapy and display a chromatic tuner on the Push 2 screen
- Show note name, cents sharp/flat, tuning needle
- Ambitious but very practical for live use
- Could use ReaTune in the FX chain and read its output

### Pedalboard Mode
A mode where the 8 encoders map to one key parameter per FX in the chain (drive amount, delay time, reverb mix, etc.).
- Display shows the FX chain as a horizontal pedalboard with bypass states
- Lower row buttons toggle FX bypass on/off
- Upper row could switch between "one-knob-per-FX" and "deep edit" for selected FX
- Streamlined version of Device mode, focused on quick tweaks during playing

### Quick Record (Punch In/Out)
- Hold a pad to punch-in record, release to stop
- Good for capturing riffs spontaneously
- Visual feedback on the held pad (red while recording)

## U-He Zebra 3 Dedicated Mode

### Macro Page
- Map encoders 1-8 to Zebra 3's macro knobs 1-8
- Upper row button to switch to macros 9-16
- Display shows macro names and values with knob arcs
- Easiest starting point — uses existing FX parameter system

### Page-Based Parameter Control
Curated parameter groups navigated with upper row buttons:
- **OSC page**: Shape, tune, detune, level per oscillator
- **Filter page**: Cutoff, resonance, envelope amount, key tracking
- **Envelope page**: Attack, decay, sustain, release for amp/filter envelopes
- **LFO page**: Rate, depth, shape, sync for LFOs
- **Effects page**: Delay time/feedback, reverb size/mix, chorus rate/depth
- **Global page**: Voice count, glide, master tune, output level

### Preset Browsing
- Encoder 1 scrolls through presets
- Display shows preset name, category, and author
- Pads could trigger preset favorites

### Modulation Depth Control
- Select a modulation source (LFO, envelope, etc.)
- Encoders set modulation amounts per destination
- Display shows source → destination routing with depth values

### XY Pad on Pad Grid
- Map a region of pads to two Zebra parameters (e.g., filter cutoff on X axis, resonance on Y axis)
- Performative control for live sound design
- Visual color gradient on pads showing current position

## Priority Suggestions

**Highest impact for guitar:**
1. Looper Control Mode
2. Pedalboard Mode
3. Touchstrip as Wah/Expression

**Easiest Zebra 3 starting point:**
1. Macro Page (works through existing FX parameter OSC paths)
