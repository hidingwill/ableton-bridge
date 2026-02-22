# AbletonBridge Max for Live Bridge (v4.0.0)

Optional deep Live Object Model (LOM) access that extends the standard AbletonBridge Remote Script. Now an **Audio Effect** device (upgraded from MIDI Effect) — enabling real-time audio analysis via `plugin~`. Adds **43 tools** (46 OSC commands) for:

- Hidden/non-automatable parameters on any Ableton device
- Device chain navigation inside Instrument Racks, Audio Effect Racks, and Drum Racks
- Enhanced chain discovery with return chains and drum pad properties (in_note, out_note, choke_group)
- Chain device parameter discovery and control (including hidden parameters inside rack chains)
- Simpler/Sample deep access (markers, warp settings, slices)
- Wavetable modulation matrix control
- Cue points & arrangement locators
- Groove pool access and modification
- Event-driven property monitoring (~10ms latency)
- Undo-clean parameter control
- Audio analysis (cross-track meter levels + MSP spectral data)
- Cross-track MSP analysis via send-based routing (RMS, peak, spectrum from any track)
- Application version detection (enables version-gating for features)
- Automation state introspection (detect active/overridden automation per parameter)
- Note surgery by stable note ID (in-place edit without destructive remove+add)
- Chain-level mixing (volume, pan, sends, mute/solo per rack chain)
- Device AB comparison (save/toggle A/B presets, Live 12.3+)
- Clip scrubbing (quantized scrub within a clip, like mouse scrubbing)
- Split stereo panning (independent left/right pan control)
- **NEW** Rack chain insertion via LOM (Live 12.3+)
- **NEW** Device insertion into rack chains via LOM
- **NEW** Drum chain input note (pad) reassignment
- **NEW** Take lane deep access (names, active status)
- **NEW** Rack variation store/recall via LOM
- **NEW** Arrangement clip creation (MIDI/audio) via LOM

## What It Adds

| Capability | Without M4L | With M4L |
|---|---|---|
| Public device parameters | Yes | Yes |
| Hidden/non-automatable parameters | No | **Yes** |
| Rack chain navigation | No | **Yes** |
| Simpler sample control | Basic | **Deep** (markers, slices, warp) |
| Wavetable modulation matrix | No | **Yes** |
| Cue points / locators | No | **Yes** |
| Groove pool | No | **Yes** |
| Event monitoring (live.observer) | No | **Yes** (~10ms) |
| Undo-clean parameter sets | No | **Yes** |
| Audio analysis (any track meters) | No | **Yes** (LOM cross-track) |
| Spectral analysis (8-band) | No | **Yes** (fffb~ filter bank) |
| App version detection | No | **Yes** (LiveAPI) |
| Automation state introspection | No | **Yes** (per-parameter) |
| Return chains (rack sends) | No | **Yes** |
| Drum pad in_note/out_note/choke | No | **Yes** |
| Note editing by stable ID | No | **Yes** (in-place, non-destructive) |
| Chain-level mixing (volume/pan/sends) | No | **Yes** (ChainMixerDevice) |
| Device AB comparison | No | **Yes** (Live 12.3+) |
| Clip scrubbing (quantized) | No | **Yes** (Clip.scrub) |
| Split stereo panning | No | **Yes** (L/R independent) |
| Rack chain insertion (LOM) | No | **Yes** (Live 12.3+) |
| Device into chain (LOM) | No | **Yes** (Live 12.3+) |
| Drum chain note assignment | No | **Yes** (Live 12.3+) |
| Take lane deep access | No | **Yes** (LOM) |
| Rack variation store/recall | No | **Yes** (LOM) |
| Arrangement clip creation | No | **Yes** (LOM) |

## How It Works

```
MCP Server
  ├── TCP :9877 → Remote Script (242 tools)
  └── UDP :9878 / :9879 → M4L Bridge (43 tools, 46 OSC commands)
```

The server sends OSC commands with typed arguments. The M4L device processes them via the Live Object Model and returns URL-safe base64-encoded JSON responses. Large responses (>1.5KB) are automatically chunked into ~3.6KB UDP packets and reassembled by the server.

## Pre-Built Devices

Two pre-built `.amxd` devices are included for different Ableton versions:

```
M4L_Device/
├── Suite/
│   ├── Devicev2.amxd      ← Ableton Live 12 Suite (stable release)
│   └── m4l_bridge.js
├── Beta/
│   ├── Devicev2.amxd      ← Ableton Live 12.x Beta
│   └── m4l_bridge.js
└── README.md
```

**Quick start:** Copy the appropriate folder's `Devicev2.amxd` and `m4l_bridge.js` to your User Library (`User Library/Presets/Audio Effects/Max Audio Effect/`), then drag the device onto any audio track.

Both versions contain the same `m4l_bridge.js` — the `.amxd` patch files differ slightly because they were saved in different Ableton versions.

## Setup Instructions

### Prerequisites

- Ableton Live **Suite** or **Standard + Max for Live** add-on
- AbletonBridge Remote Script already installed and working

### Using the Pre-Built Device (Recommended)

1. Copy `Devicev2.amxd` and `m4l_bridge.js` from `Suite/` or `Beta/` (matching your Ableton version) to `User Library/Presets/Audio Effects/Max Audio Effect/`
2. In Ableton, find the device in your User Library browser
3. Drag it onto any audio track
4. The device will immediately start listening on UDP port 9878

### Building the .amxd Device Manually

If you need to build the device from scratch (e.g., for a different Ableton version), follow these steps:

1. **Open Ableton Live**

2. **Create a new Max Audio Effect**:
   - In the browser, go to **Max for Live → Max Audio Effect**
   - Drag it onto any audio track (or MIDI track with an instrument)

3. **Open the Max editor** (click the wrench icon on the device)

4. **Build the core patch** with these 3 objects connected in order:

   ```
   [udpreceive 9878]
        |
   [js m4l_bridge.js]
        |
   [udpsend 127.0.0.1 9879]
   ```

   To add each object: press **N** to create a new object, type the text (e.g., `udpreceive 9878`), then press Enter. Connect them top-to-bottom with patch cables.

5. **Add audio passthrough** — connect the default `plugin~` and `plugout~` objects:

   ```
   [plugin~]  →  [plugout~]
   ```

   This ensures the device passes audio through without muting the track.

6. **Add audio analysis chain** *(optional — RMS/peak are auto-derived from spectrum if this chain is missing)*:

   ```
   [plugin~]          [plugin~]
       |                   |
   [peakamp~ 100]     [peakamp~ 100]
       |                   |
   [snapshot~ 200]     [snapshot~ 200]
       \                 /
     [pack f f 0. 0.]
            |
     [prepend audio_data]
            |
     [js m4l_bridge.js]  ← connect to EXISTING [js] object
   ```

   Two `plugin~` objects tap left/right channels. `peakamp~` extracts peak amplitude, `snapshot~` converts to messages. **Important**: the left-channel `snapshot~` MUST connect to the **first** (leftmost) inlet of `pack` — `pack` only fires when its first inlet receives a value.

   > **Note:** If this chain is not connected, the bridge automatically derives RMS/peak from the spectrum data (step 7). The derived values are a good approximation. This chain provides true stereo RMS/peak for higher precision.

7. **Add spectrum analysis chain** (for `analyze_track_spectrum`):

   ```
   [plugin~]
       |
   [fffb~ 8]          ← 8-band fixed filter bank
    ||||||||
    8× [abs~]          ← REQUIRED: rectify bipolar signal to amplitude
    ||||||||
    8× [snapshot~ 100] ← one per outlet
    ||||||||
   [pack 0. 0. 0. 0. 0. 0. 0. 0.]
       |
   [prepend spectrum_data]
       |
   [js m4l_bridge.js]  ← connect to EXISTING [js] object
   ```

   `fffb~ 8` splits audio into 8 frequency bands. Each band output is a raw bipolar signal — `abs~` converts it to absolute amplitude before `snapshot~` samples it. Without `abs~`, spectrum values will be meaningless (random positive/negative sample values).

8. **Add the JavaScript file**:
   - Copy `m4l_bridge.js` from this directory to the same folder where your `.amxd` device is saved
   - In the Max editor, the `[js m4l_bridge.js]` object should find it automatically
   - If not, use the Max file browser to locate it

9. **Save the device**:
   - **Lock the patch** first (Cmd+E / Ctrl+E)
   - **File → Save As...** in the Max editor
   - Save as `AbletonBridge.amxd` in your User Library
   - Recommended path: `User Library/Presets/Audio Effects/Max Audio Effect/`

10. **Close the Max editor**

### Why Audio Effect (not MIDI Effect)?

The device was originally a MIDI Effect, but `plugin~` in a MIDI Effect receives **no audio** — it sits before the instrument in the signal chain, so there's nothing to analyze. As an Audio Effect, `plugin~` taps the post-instrument audio signal, enabling real-time RMS/peak measurement and spectral analysis.

All 41 OSC commands, LiveAPI access, observers, and cross-track meter reading work identically in both device types. The only difference is that MSP audio analysis (`plugin~`, `peakamp~`, `fffb~`) now actually receives audio.

### Loading the Device

1. Open your Ableton Live project
2. Find `AbletonBridge` in your User Library browser
3. Drag it onto **any track** — audio tracks work directly; MIDI tracks need an instrument before the device
4. The device will immediately start listening on UDP port 9878

### Verifying the Connection

Use the `m4l_status` MCP tool to check if the bridge is connected:

```
m4l_status()  →  "M4L bridge connected (v3.6.0)"
```

## Available MCP Tools (When Bridge Is Loaded)

### Hidden Parameter Access

| Tool | Description |
|---|---|
| `m4l_status()` | Check bridge connection status |
| `discover_device_params(track, device)` | List ALL parameters (hidden + public) for any device |
| `get_device_hidden_parameters(track, device)` | Get full parameter info including hidden ones |
| `set_device_hidden_parameter(track, device, param_index, value)` | Set any parameter by LOM index |
| `batch_set_hidden_parameters(track, device, params)` | Set multiple hidden params in one call |
| `list_instrument_rack_presets()` | List saved Instrument Rack presets (VST/AU workaround) |

### Device Chain Navigation (v2.0.0)

| Tool | Description |
|---|---|
| `discover_rack_chains(track, device, chain_path?)` | Discover chains, nested devices, and drum pads in Racks. Use `chain_path` (e.g. `"chains 0 devices 0"`) for nested racks |
| `get_chain_device_parameters(track, device, chain, chain_device)` | Read all params of a nested device |
| `set_chain_device_parameter(track, device, chain, chain_device, param, value)` | Set a param on a nested device |

### Simpler / Sample Deep Access (v2.0.0)

| Tool | Description |
|---|---|
| `get_simpler_info(track, device)` | Get Simpler state: playback mode, sample file, markers, warp, slices |
| `set_simpler_sample_properties(track, device, ...)` | Set sample markers, warp mode, gain, etc. |
| `simpler_manage_slices(track, device, action, ...)` | Insert, remove, move, clear, or reset slices |

### Wavetable Modulation Matrix (v2.0.0)

| Tool | Description |
|---|---|
| `get_wavetable_info(track, device)` | Get oscillator wavetables, mod matrix, unison, filter routing |
| `set_wavetable_modulation(track, device, target, source, amount)` | Set modulation amount (Env2/Env3/LFO1/LFO2 → target) |
| `set_wavetable_properties(track, device, ...)` | Set wavetable selection, effect modes (via M4L). Unison/filter/voice properties are read-only (Ableton API limitation) |

### Cue Points & Locators (v3.0.0)

| Tool | Description |
|---|---|
| `get_cue_points()` | List all arrangement locators with names and beat positions |
| `jump_to_cue_point(cue_point_index)` | Move playback position to a specific locator |

### Groove Pool (v3.0.0)

| Tool | Description |
|---|---|
| `get_groove_pool()` | List all grooves with base, timing, velocity, random, quantize properties |
| `set_groove_properties(groove_index, ...)` | Set groove base, timing, velocity, random, quantize_rate |

### Event-Driven Monitoring (v3.0.0)

| Tool | Description |
|---|---|
| `observe_property(lom_path, property_name)` | Start watching a LOM property (~10ms change detection) |
| `stop_observing(lom_path, property_name)` | Stop watching a property |
| `get_property_changes()` | Retrieve accumulated change events (clears after read) |

### Undo-Clean Parameter Control (v3.0.0)

| Tool | Description |
|---|---|
| `set_parameter_clean(track, device, param_index, value)` | Set parameter via M4L bridge with minimal undo impact |

### Audio Analysis (v3.1.0+)

| Tool | Description |
|---|---|
| `analyze_track_audio(track_index?)` | Get LOM meter levels for **any track** (cross-track). Optional `track_index`: -1=own track (default), 0+=specific track, -2=master |
| `analyze_track_spectrum()` | Get 8-band spectral data from fffb~ filter bank (device's own track) |
| `analyze_cross_track_audio(track_index, wait_ms?)` | **v3.6.0** Real MSP analysis (RMS, peak, 8-band spectrum) from **any track** via send-based routing. Device must be on a return track. |

### App Version & Automation (v3.6.0)

| Tool | Description |
|---|---|
| `get_ableton_version()` | Get Live version (major, minor, bugfix, display string). Enables version-gating for features like AB comparison (Live 12.3+) |
| `get_automation_states(track, device)` | Get automation state for all device parameters. Returns only params with automation: 0=none, 1=active, 2=overridden |

### Enhanced Chain Discovery (v3.6.0)

| Tool | Description |
|---|---|
| `discover_chains_m4l(track, device, extra_path?)` | Discover rack chains with enhanced detail: return chains, drum pad in_note/out_note/choke_group |
| `get_chain_device_params_m4l(track, device, chain, chain_device)` | Discover ALL parameters (including hidden) of a device inside a rack chain |
| `set_chain_device_param_m4l(track, device, chain, chain_device, param, value)` | Set any parameter on a device inside a rack chain |

### Note Surgery by ID (v3.6.0)

| Tool | Description |
|---|---|
| `get_clip_notes_with_ids(track, clip)` | Get all MIDI notes with stable note IDs for in-place editing |
| `modify_clip_notes(track, clip, modifications)` | Non-destructive in-place note editing by ID (velocity, pitch, timing, probability) |
| `remove_clip_notes_by_id(track, clip, note_ids)` | Surgical note removal — only removes exact notes by ID |

### Chain-Level Mixing (v3.6.0)

| Tool | Description |
|---|---|
| `get_chain_mixing(track, device, chain)` | Read chain mixer state: volume, pan, sends, mute, solo, chain_activator |
| `set_chain_mixing(track, device, chain, properties)` | Set any combination of chain mixing props (volume, panning, sends, mute, solo) |

### Device AB Comparison (v3.6.0, Live 12.3+)

| Tool | Description |
|---|---|
| `device_ab_compare(track, device, action)` | AB preset comparison: get_state, save, or toggle between A/B slots |

### Clip Scrubbing (v3.6.0)

| Tool | Description |
|---|---|
| `clip_scrub(track, clip, action, beat_time?)` | Quantized clip scrubbing (scrub / stop_scrub). Respects Global Quantization |

### Split Stereo Panning (v3.6.0)

| Tool | Description |
|---|---|
| `get_split_stereo(track)` | Read left/right split stereo pan values |
| `set_split_stereo(track, left, right)` | Set independent L/R panning for a track |

## Troubleshooting

**"M4L bridge not connected"**
- Ensure the AbletonBridge device is loaded on a track
- Check that port 9878 is not used by another application
- Make sure the patch is **locked** (not in edit mode) — `udpreceive` may not work while unlocked

**"Timeout waiting for M4L response"**
- The M4L device may be in edit mode — close the Max editor
- Try removing and re-adding the device to the track
- Double-click the `[js m4l_bridge.js]` object to reload the script

**Spectrum data all zeros**
- Audio must be playing through the track where the device is loaded
- The device must be an **Audio Effect** (not MIDI Effect) — `plugin~` in a MIDI Effect receives no audio
- On MIDI tracks, the device must be placed **after** an instrument in the chain

**Spectrum shows negative or near-zero values**
- Missing `abs~` objects between `fffb~` outlets and `snapshot~` objects. `fffb~` outputs raw bipolar audio signals — without `abs~`, `snapshot~` captures arbitrary instantaneous sample values (can be negative) instead of amplitudes
- Add one `abs~` object after each of the 8 `fffb~` outlets, before the corresponding `snapshot~ 100`

**RMS/peak zero but spectrum works**
- The `prepend audio_data` object is likely not connected to `[js m4l_bridge.js]` — draw a patch cable from its outlet to the [js] object
- Or: the left-channel `snapshot~ 200` is connected to the wrong inlet of `pack f f 0. 0.` — it must connect to the **first** (leftmost) inlet for pack to fire
- **Automatic fallback**: even without the peakamp~ chain, the bridge auto-derives RMS/peak from spectrum data. If you see non-zero RMS/peak labeled as "derived from spectrum", this fallback is active

**Cross-track analysis returns zeros (LOM meters show signal)**
- The send routing is working (LOM meters confirm audio), but the MSP chain isn't capturing it
- Ensure `abs~` objects are wired between `fffb~` and `snapshot~` (see spectrum chain diagram above)
- Try increasing `wait_ms` (e.g. `analyze_cross_track_audio(track_index=0, wait_ms=1000)`) to give the audio engine more time to propagate the send change
- Check the Max console (Window → Max Console) for diagnostic messages starting with "Cross-track capture:"

**Port conflicts**
- Default ports: 9878 (commands) and 9879 (responses)
- If these conflict with other software, edit the port numbers in:
  - The Max patch objects (`udpreceive` and `udpsend`)
  - `server.py` (`M4LConnection` class: `send_port` and `recv_port`)

## OSC Commands Reference (v4.0.0)

| Address | Arguments | Description |
|---|---|---|
| `/ping` | `request_id` | Health check — returns bridge version |
| `/discover_params` | `track_idx, device_idx, request_id` | Enumerate all LOM parameters |
| `/get_hidden_params` | `track_idx, device_idx, request_id` | Get hidden parameter details |
| `/set_hidden_param` | `track_idx, device_idx, param_idx, value, request_id` | Set a parameter by LOM index |
| `/batch_set_hidden_params` | `track_idx, device_idx, params_b64, request_id` | Set multiple params (chunked, base64 JSON) |
| `/check_dashboard` | `request_id` | Returns dashboard URL and bridge version |
| `/discover_chains` | `track_idx, device_idx, [extra_path], request_id` | Discover rack chains and drum pads |
| `/get_chain_device_params` | `track_idx, device_idx, chain_idx, chain_device_idx, request_id` | Get nested device params |
| `/set_chain_device_param` | `track_idx, device_idx, chain_idx, chain_device_idx, param_idx, value, request_id` | Set nested device param |
| `/get_simpler_info` | `track_idx, device_idx, request_id` | Get Simpler + sample info |
| `/set_simpler_sample_props` | `track_idx, device_idx, props_b64, request_id` | Set sample properties (base64 JSON) |
| `/simpler_slice` | `track_idx, device_idx, action, [slice_time], request_id` | Manage slices (insert/remove/move/clear/reset) |
| `/get_wavetable_info` | `track_idx, device_idx, request_id` | Get Wavetable state + mod matrix |
| `/set_wavetable_modulation` | `track_idx, device_idx, target_idx, source_idx, amount, request_id` | Set mod matrix amount |
| `/set_wavetable_props` | `track_idx, device_idx, props_b64, request_id` | Set Wavetable properties (base64 JSON) |
| `/get_cue_points` | `request_id` | List all arrangement locators |
| `/jump_to_cue_point` | `cue_point_idx, request_id` | Jump playback to a locator |
| `/get_groove_pool` | `request_id` | List all grooves with properties |
| `/set_groove_properties` | `groove_idx, props_b64, request_id` | Set groove properties (base64 JSON) |
| `/observe_property` | `lom_path, property_name, request_id` | Start observing a LOM property |
| `/stop_observing` | `lom_path, property_name, request_id` | Stop observing a property |
| `/get_observed_changes` | `request_id` | Get accumulated property changes |
| `/set_param_clean` | `track_idx, device_idx, param_idx, value, request_id` | Set param with minimal undo |
| `/analyze_audio` | `track_index, request_id` | Get audio meter levels + MSP data. `track_index`: -1=own, 0+=specific, -2=master |
| `/analyze_spectrum` | `request_id` | Get spectral analysis data (8-band fffb~) |
| `/analyze_cross_track` | `track_index, wait_ms, request_id` | Cross-track MSP analysis via send routing. Device must be on return track |
| `/get_app_version` | `request_id` | **v3.6.0** Get Ableton Live major/minor/bugfix version |
| `/get_automation_states` | `track_idx, device_idx, request_id` | **v3.6.0** Get automation_state (0=none, 1=active, 2=overridden) for all device parameters |
| `/get_clip_notes_by_id` | `track_idx, clip_idx, request_id` | **v3.6.0** Get all MIDI notes with stable note IDs |
| `/modify_clip_notes` | `track_idx, clip_idx, modifications_b64, request_id` | **v3.6.0** In-place modify notes by ID (base64 JSON) |
| `/remove_clip_notes_by_id` | `track_idx, clip_idx, note_ids_b64, request_id` | **v3.6.0** Remove notes by ID (base64 JSON) |
| `/get_chain_mixing` | `track_idx, device_idx, chain_idx, request_id` | **v3.6.0** Read chain mixer state |
| `/set_chain_mixing` | `track_idx, device_idx, chain_idx, props_b64, request_id` | **v3.6.0** Set chain mixer properties (base64 JSON) |
| `/device_ab_compare` | `track_idx, device_idx, action, request_id` | **v3.6.0** AB comparison: get_state/save/toggle (Live 12.3+) |
| `/clip_scrub` | `track_idx, clip_idx, action, beat_time, request_id` | **v3.6.0** Quantized clip scrub (scrub/stop_scrub) |
| `/get_split_stereo` | `track_idx, request_id` | **v3.6.0** Read L/R split stereo pan values |
| `/set_split_stereo` | `track_idx, left_val, right_val, request_id` | **v3.6.0** Set L/R split stereo pan values |
| `/rack_insert_chain` | `track_idx, device_idx, chain_idx, request_id` | **v4.0.0** Insert chain into rack (Live 12.3+) |
| `/chain_insert_device_m4l` | `track_idx, device_idx, chain_idx, device_uri, target_idx, request_id` | **v4.0.0** Insert device into rack chain |
| `/set_drum_chain_note` | `track_idx, device_idx, chain_idx, note, request_id` | **v4.0.0** Set drum pad input note (Live 12.3+) |
| `/get_take_lanes` | `track_idx, request_id` | **v4.0.0** Get take lane info (names, active status) |
| `/rack_store_variation` | `track_idx, device_idx, request_id` | **v4.0.0** Store current rack macro state as variation |
| `/rack_recall_variation` | `track_idx, device_idx, variation_idx, request_id` | **v4.0.0** Recall a stored rack variation |
| `/create_arrangement_midi_clip_m4l` | `track_idx, time, length, request_id` | **v4.0.0** Create MIDI clip in arrangement via LOM |
| `/create_arrangement_audio_clip_m4l` | `track_idx, time, length, request_id` | **v4.0.0** Create audio clip in arrangement via LOM |

## Technical Notes

### Device Type: Audio Effect

As of v3.1.0, the bridge is an **Audio Effect** (not MIDI Effect). This is required because `plugin~` in a MIDI Effect sits before the instrument in the signal chain and receives no audio. As an Audio Effect, `plugin~` taps the post-instrument audio, enabling MSP-based analysis (RMS, peak, spectrum).

All LOM-based tools (hidden params, rack chains, observers, cross-track meters) work identically regardless of device type. Only the MSP audio chain requires the Audio Effect placement.

### Cross-Track Audio Analysis

The `analyze_track_audio` tool reads LOM `output_meter_left`/`output_meter_right` for any track by path:
- `live_set tracks N` — any regular track
- `live_set master_track` — master track
- `this_device canonical_parent` — device's own track (default)

This works from a single device instance — no need to load the bridge on every track.

### Communication
- **Protocol**: Native OSC messages over UDP. Server builds typed OSC packets; M4L parses via Max's built-in OSC support.
- **Responses**: URL-safe base64-encoded JSON (`A-Z a-z 0-9 - _` only). Standard base64 `+` and `/` conflict with Max's OSC routing.
- **Device-agnostic**: Works with any Ableton instrument or effect. Always use `discover_device_params` first — LOM indices may vary between Live versions.
- **Non-interfering**: Runs alongside the Remote Script on separate UDP ports.

### Chunked Response Protocol (Rev 4)
Large device discovery (e.g. Wavetable with 93 parameters) produces responses that exceed Max's ~8KB outlet symbol limit and crash Ableton. The bridge handles this automatically:

1. Responses ≤1.5KB JSON are sent directly (backward compatible)
2. Larger responses are split into 2KB raw JSON pieces
3. Each piece is base64-encoded independently with URL-safe conversion
4. Wrapped in a chunk envelope (`{"_c":idx,"_t":total,"_d":"..."}`) and encoded again
5. All chunks sent via deferred `Task.schedule()` with 50ms delays (~3.6KB each)
6. Python server detects chunk metadata, buffers, and reassembles

Key safety: never creates the full base64 string in memory; `.replace()` for URL-safe conversion is O(n) native; no synchronous outlet from discovery callbacks.

### Crash Prevention
- **Chunked async discovery**: Large devices discovered 4 params/chunk with 50ms `Task.schedule()` delays. Prevents synchronous LiveAPI overload (>210 `get()` calls crashes Ableton).
- **LiveAPI cursor reuse**: `discover_rack_chains` uses `goto()` to reuse 3 cursor objects instead of creating ~193 per call. Prevents Max `[js]` memory exhaustion on large drum racks.
- **Fire-and-forget writes**: `set_device_hidden_parameter`, `set_chain_device_parameter`, and `set_wavetable_properties` do not read back after `set()`. Post-set `get("value")` readback was the #1 crash pattern.
- **Concurrency guards**: Discovery, batch set, and response send operations reject concurrent requests instead of corrupting shared state.
- **Error recovery**: Chunked discovery and response sending catch exceptions, clean up global state, and unblock future operations.

### Known Limitations
- **Wavetable voice properties** (`unison_mode`, `unison_voice_count`, `filter_routing`, `mono_poly`, `poly_voices`) are read-only — not exposed as DeviceParameters, and `LiveAPI.set()` silently fails. Hard Ableton API limitation.
- **MSP audio analysis** (RMS/peak/spectrum via `plugin~`) only works for the device's own track. Cross-track analysis uses LOM meters instead (always available for any track).
- **ASCII-only in responses** — Unicode characters above 127 corrupt Max's `[js]` base64 encoder. All response strings must use ASCII only.
