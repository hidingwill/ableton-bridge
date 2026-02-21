# AbletonMCP

**249 tools connecting Claude AI to Ableton Live** (230 core + 19 optional ElevenLabs voice/SFX tools)

AbletonMCP gives Claude direct control over your Ableton Live session through the Model Context Protocol. Create tracks, write MIDI, design sounds, mix, automate, browse instruments, snapshot presets, and navigate deep into device chains and modulation matrices — all through natural language conversation.

---

## What It Can Do

### Music Creation

> "Create a MIDI track, load Operator, and write an 8-bar bass line in E minor"
>
> "Make a 4-bar jazz chord progression — Cm7, Fm7, Dm7b5, G7 — with voice leading"
>
> "Build a Metro-Boomin-style 808 beat using grid notation"
>
> "Set the tempo to 128 BPM, create 4 tracks, and set up a minimal techno arrangement"
>
> "What key is this song in? Set the scale to D minor"
>
> "Enable punch-in recording so I only record over the chorus section"
>
> "Undo the last change — I don't like how that sounds"
>
> "Duplicate the 4-bar section at bar 9 to fill out the chorus"

### Sound Design

> "Load Wavetable on track 1 and design a warm detuned supersaw pad"
>
> "Discover all hidden parameters on my Wavetable synth"
>
> "Set filter cutoff to 0.3 and resonance to 0.7 on track 2's device"
>
> "Snapshot the current Operator preset, tweak it brighter, then morph back 50% toward the original"
>
> "Generate an aggressive reese bass preset for Operator"
>
> "Create a macro that links filter cutoff, reverb send, and delay feedback to one knob"
>
> "Switch the EQ Eight to Mid/Side mode and enable oversampling"
>
> "Set the Compressor side-chain input to the kick drum track"
>
> "Browse the Hybrid Reverb IR categories and load a large hall impulse response"

### Deep Device Access (Max for Live)

> "Show me what's inside the Drum Rack on track 3 — all chains and nested devices"
>
> "Get all parameters of the compressor nested inside chain 0 of my Instrument Rack"
>
> "Read the Simpler sample info — show me warp markers, slices, and playback mode"
>
> "Set Wavetable's LFO1 modulation to filter cutoff at 0.6"
>
> "Batch-set 12 hidden parameters on my synth in one shot"
>
> "Get all the cue points in my arrangement and jump to the chorus marker"
>
> "Show me what grooves are in the groove pool and set the timing to 80%"
>
> "Watch the tempo property for changes while I adjust it in Ableton"
>
> "Analyze the audio levels on track 3 — what's the meter reading?"
>
> "Show me the spectrum analysis of the master track"
>
> "Analyze the full spectrum of track 5 using cross-track routing"

### Mixing & Arrangement

> "Set track 1 volume to -6 dB and pan slightly left"
>
> "Create a reverb return track and send drums to it at 30%"
>
> "Create a filter sweep automation from 0.2 to 0.9 over 8 bars on track 2"
>
> "Mute tracks 3 and 4, solo track 1, and arm track 2 for recording"
>
> "Insert 4 bars of silence at bar 17 in the arrangement"
>
> "Convert the drums on track 2 to MIDI and put them in a new Drum Rack"
>
> "Mute the kick drum pad and solo the snare in the Drum Rack"
>
> "Get arrangement clips on all tracks and give me an overview of the structure"
>
> "Which clips are currently playing? Show me their positions"
>
> "Add a Compressor to track 2 by name — faster than browsing"

### Session Management

> "Give me a full overview of all tracks — names, devices, arm states, volumes"
>
> "Snapshot every device on tracks 0 through 3 as 'verse preset'"
>
> "Compare my 'verse' and 'chorus' snapshots and show what changed"
>
> "Search the browser for 'vocoder' and load it on the master track"
>
> "List all my snapshots and delete the ones from yesterday's session"
>
> "Set track 3 monitoring to IN so I can hear live input"
>
> "Store the current macro settings as a variation, then randomize"
>
> "Show me the Arranger view and zoom in"
>
> "What's the current tuning system? Is Ableton Link enabled?"
>
> "Control the Looper — start recording, then overdub"
>
> "Show me the warp markers on this audio clip and adjust the timing"

---

## Architecture

```text
Claude AI  <--MCP-->  MCP Server  <--TCP:9877-->  Ableton Remote Script
                          |            <--UDP:9882-->  (real-time params)
                          +---<--UDP/OSC:9878/9879-->  M4L Bridge (optional)
                          |
                          +---<--HTTP:9880-->  Web Status Dashboard

              ElevenLabs MCP Server (optional, separate process)
                          |
                          +---<--HTTPS-->  ElevenLabs API
```

- **Remote Script** (TCP+UDP) — 197 tools. Runs as a Control Surface inside Ableton. TCP:9877 for all commands. UDP:9882 for fire-and-forget real-time parameter updates at 50+ Hz.
- **M4L Bridge** (UDP/OSC) — 35 tools. A Max for Live **Audio Effect** device that accesses hidden parameters, rack chain internals, Simpler sample data, Wavetable modulation matrices, cue points, groove pool, event monitoring, undo-clean parameter control, cross-track audio metering, 8-band spectral analysis, cross-track MSP analysis via send routing, app version detection, automation state introspection, enhanced chain discovery, note surgery by ID, chain-level mixing, device AB comparison, clip scrubbing, and split stereo panning.
- **ElevenLabs Server** (optional) — 19 tools. AI voice generation, sound effects, voice cloning, transcription. Requires `ELEVENLABS_API_KEY`.
- **Web Dashboard** — real-time status, tool call metrics, and server logs at `http://127.0.0.1:9880`.

---

## Tools by Category (230 + 19 Optional)

| Category | Count | Channel |
|---|---|---|
| Session & Transport | 20 | TCP |
| Song Scale & Harmony | 2 | TCP |
| Punch Recording | 1 | TCP |
| Link Sync | 2 | TCP |
| Selection State | 1 | TCP |
| Track Management | 16 | TCP |
| Track Mixing | 7 | TCP |
| Take Lanes / Comping | 2 | TCP |
| Clip Management | 22 | TCP |
| Clip Playing Status | 1 | TCP |
| Warp Markers | 4 | TCP |
| MIDI Notes | 8 | TCP |
| Automation | 4 | TCP |
| ASCII Grid Notation | 2 | TCP |
| Transport & Recording | 11 | TCP |
| Arrangement Editing | 7 | TCP |
| Audio Clips | 7 | TCP |
| MIDI & Performance | 3 | TCP |
| Scenes | 6 | TCP |
| Return Tracks | 6 | TCP |
| Master Track | 2 | TCP |
| Devices & Parameters | 22 | TCP |
| Insert Device by Name | 1 | TCP |
| Looper Control | 1 | TCP |
| Tuning System | 1 | TCP |
| Real-time Parameters | 2 | UDP |
| View & Selection | 6 | TCP |
| Browser & Loading | 10 | TCP |
| Snapshot & Versioning | 9 | TCP |
| Preset Morph | 1 | TCP |
| Smart Macros | 4 | TCP |
| Preset Generator | 1 | TCP |
| Parameter Mapper | 4 | TCP |
| Rack Presets | 1 | TCP |
| Deep Device Access | 10 | UDP/OSC |
| Chain Discovery & Control | 3 | UDP/OSC |
| App Version Detection | 1 | UDP/OSC |
| Automation State Introspection | 1 | UDP/OSC |
| Note Surgery by ID | 3 | UDP/OSC |
| Chain-Level Mixing | 2 | UDP/OSC |
| Device AB Comparison | 1 | UDP/OSC |
| Clip Scrubbing | 1 | UDP/OSC |
| Split Stereo Panning | 2 | UDP/OSC |
| Cue Points & Locators | 2 | UDP/OSC |
| Groove Pool | 2 | UDP/OSC |
| Event Monitoring | 3 | UDP/OSC |
| Undo-Clean Params | 1 | UDP/OSC |
| Audio Analysis (cross-track) | 3 | UDP/OSC |
| **Subtotal** | **230** | |
| ElevenLabs Voice/SFX | 19 | HTTPS (optional) |
| **Total** | **249** | |

---

## Stability & Reliability

AbletonMCP is built to handle real-world sessions without crashing Ableton. Every crash discovered during development was traced to a root cause and fixed with a targeted safeguard:

- **Chunked async LiveAPI operations** — large device discovery (93+ parameters) is split into 4-param chunks with 50ms delays between each. Prevents synchronous LiveAPI overload that crashes Ableton's scripting engine.

- **Chunked response protocol** — large responses (>1.5KB JSON) are split into 2KB pieces, each base64-encoded independently with URL-safe conversion, wrapped in a chunk envelope, and sent via deferred `Task.schedule()`. The Python server detects, buffers, and reassembles automatically. Small responses pass through unchanged (backward compatible).

- **URL-safe base64 encoding** — all M4L bridge data uses `A-Z a-z 0-9 - _` only. Standard base64 `+` and `/` characters conflict with Max's OSC address routing and are never used.

- **Deferred `Task.schedule()` processing** — all M4L outlet calls are deferred to avoid blocking Ableton's main audio/UI thread. No synchronous outlet from discovery callbacks.

- **LiveAPI cursor reuse** — rack chain discovery uses `goto()` to reuse 3 cursor objects instead of creating ~193 new LiveAPI instances per call. Prevents Max `[js]` memory exhaustion on large drum racks.

- **Fire-and-forget parameter writes** — `set()` calls do not read back the value afterward. Post-set `get()` readback was the #1 crash pattern across hidden params, wavetable props, and chain device params.

- **Dynamic timeouts** — M4L command timeouts scale with operation size (~150ms per parameter, minimum 10s). No fixed timeouts that fail on large devices.

- **Socket drain on send** — clears stale UDP responses before each new command to prevent response contamination from prior calls.

- **Singleton guard** — exclusive TCP port lock (9881) prevents duplicate MCP server instances from conflicting.

- **Disk-persisted browser cache** — 6,400+ browser items cached to `~/.ableton-mcp/browser_cache.json.gz`. Loaded instantly on startup (~50ms). Background refresh keeps it current. No 2-3 minute wait on first launch.

- **Auto-reconnect with exponential backoff** — both TCP and UDP connections recover automatically from Ableton restarts or network interruptions.

---

## Flexibility

- **Works with any MCP client** — Claude Desktop, Cursor, or any tool that speaks the Model Context Protocol
- **197 tools without Max for Live** — the TCP/UDP Remote Script covers tracks, clips, MIDI, mixing, automation, browser, snapshots, macros, presets, drum pads, rack variations, grooves, audio-to-MIDI conversion, device-specific controls (Simpler, Transmute, Compressor, EQ8, Hybrid Reverb), song settings, scale/harmony, punch recording, Link sync, view/selection, warp markers, tuning system, looper control, take lanes, metering, real-time parameter control, and navigation. M4L is optional.
- **+35 deep-access tools with M4L** — hidden parameters, rack chain internals, Simpler samples, Wavetable modulation, cue points/locators, groove pool, event-driven monitoring, undo-clean parameter control, cross-track audio metering, 8-band spectral analysis, cross-track MSP analysis via send routing, app version detection, automation state introspection, chain discovery, note surgery by ID, chain-level mixing, device AB comparison, clip scrubbing, split stereo panning
- **+19 optional ElevenLabs tools** — AI voice generation, sound effects, voice cloning, transcription, conversational AI agents. Requires API key.
- **Web dashboard** — live monitoring of connection status, tool calls, and server logs at port 9880
- **Ableton Live 10, 11, and 12** — graceful API fallbacks for version-specific features (extended notes, capture MIDI, arrangement placement)
- **Cross-platform** — Windows and macOS
- **Quick setup** — `uv run` for the MCP server, copy one folder for the Remote Script, drop one M4L device for the bridge

---

## Version

**v2.9.1** — see [CHANGELOG.md](CHANGELOG.md) for full release history.

---

## Optional: ElevenLabs Voice & SFX Server

AbletonMCP includes an optional ElevenLabs integration that provides 19 additional tools for AI voice generation, sound effects, voice cloning, and conversational AI agents. Generated audio saves directly to your Ableton User Library for easy import.

### Setup

1. Install dependencies: `pip install -e ".[elevenlabs]"`
2. Set your API key: `export ELEVENLABS_API_KEY=your_key_here` (or add to `.env`)
3. Add to your Claude Desktop config as a second server:

```json
{
  "mcpServers": {
    "ableton-mcp": {
      "command": "uv",
      "args": ["run", "ableton-mcp-stable"]
    },
    "elevenlabs": {
      "command": "uv",
      "args": ["run", "elevenlabs-mcp"],
      "env": {
        "ELEVENLABS_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Usage

> "Generate a robot voice saying 'drop the bass' and load it into Simpler on track 3"
>
> "Create thunder sound effect, 3 seconds long"
>
> "Transcribe the audio clip on my desktop"
>
> "Clone my voice from these 3 samples and use it for text-to-speech"
