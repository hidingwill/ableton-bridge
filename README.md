# AbletonBridge

**350 tools connecting Claude AI to Ableton Live** (331 core + 19 optional ElevenLabs voice/SFX tools)

AbletonBridge gives Claude direct control over your Ableton Live session through the Model Context Protocol. Create tracks, write MIDI, design sounds, mix, automate, browse instruments, snapshot presets, and navigate deep into device chains and modulation matrices — all through natural language conversation.

---

## What It Can Do

**Music Creation** — *"Create a MIDI track, load Operator, and write an 8-bar bass line in E minor"* · *"Build a Metro-Boomin-style 808 beat using grid notation"* · *"Make a 4-bar jazz chord progression — Cm7, Fm7, Dm7b5, G7 — with voice leading"*

**Sound Design** — *"Load Wavetable and design a warm detuned supersaw pad"* · *"Snapshot the current preset, tweak it brighter, then morph back 50%"* · *"Set the Compressor side-chain input to the kick drum track"*

**Deep Device Access** (M4L) — *"Show me what's inside the Drum Rack — all chains and nested devices"* · *"Set Wavetable's LFO1 modulation to filter cutoff at 0.6"* · *"Analyze the full spectrum of track 5 using cross-track routing"*

**Mixing & Arrangement** — *"Create a filter sweep automation from 0.2 to 0.9 over 8 bars"* · *"Create a reverb return track and send drums to it at 30%"* · *"Get arrangement clips on all tracks and give me a structure overview"*

**Creative Generation** — *"Generate a Euclidean rhythm with 16 steps and 5 pulses"* · *"Write a I-vi-IV-V chord progression with drop2 voicings"* · *"Create a trap drum pattern, 2 bars, with swing"*

**Session Management** — *"Full overview of all tracks — names, devices, volumes"* · *"Search the browser for 'vocoder' and load it on the master track"* · *"Snapshot every device on tracks 0-3 as 'verse preset'"*

---

## Architecture

```text
Claude AI  <--MCP-->  MCP Server  <--TCP:9877-->  Ableton Remote Script
                          |            <--UDP:9882-->  (real-time params)
                          +---<--UDP/OSC:9878/9879-->  M4L Bridge (optional)
                          +---<--HTTP:9880-->  Web Status Dashboard
```

- **Remote Script** (TCP+UDP) — runs inside Ableton as a Control Surface. TCP:9877 for commands, UDP:9882 for real-time parameter updates at 50+ Hz. Includes 21 server-side creative tools.
- **M4L Bridge** (UDP/OSC) — optional Audio Effect device for hidden parameters, rack chain internals, audio analysis, modulation matrices, event monitoring, and more.
- **ElevenLabs Server** (optional) — 19 tools for AI voice generation, sound effects, voice cloning. Requires `ELEVENLABS_API_KEY`.
- **Web Dashboard** — real-time status, tool metrics, and server logs at `http://127.0.0.1:9880`.

---

## Tool Overview (331 core + 19 optional = 350 total)

| Area | Examples | Count |
|---|---|---|
| Session & Transport | tempo, play/record, capture, Link, punch, song settings | ~36 |
| Tracks & Mixing | create/rename tracks, volume, pan, sends, crossfader, routing | ~35 |
| Clips & Scenes | create/edit clips, follow actions, warp markers, scenes | ~52 |
| MIDI & Automation | notes, grid notation, automation curves, performance | ~17 |
| Arrangement | arrangement clips, editing, audio clip creation | ~16 |
| Devices & Parameters | load/configure, rack chains, real-time control | ~31 |
| Browser & Presets | search/load instruments, snapshots, morph, macros, mapper | ~31 |
| Creative Generation | Euclidean rhythms, chords, drums, arpeggios, bass lines, transforms | ~21 |
| Deep Access (M4L) | hidden params, chain internals, audio analysis, note surgery | ~43 |
| **Core subtotal** | | **331** |
| ElevenLabs (optional) | voice generation, SFX, cloning, transcription | 19 |
| **Total** | | **350** |

See [CHANGELOG.md](CHANGELOG.md) for the complete per-tool breakdown.

---

## Stability & Reliability

AbletonBridge is built to handle real-world sessions without crashing Ableton:

- **Chunked async LiveAPI** — large device discovery split into 4-param chunks with 50ms delays
- **Chunked response protocol** — large responses split, base64-encoded, reassembled automatically
- **URL-safe base64** — `A-Z a-z 0-9 - _` only; avoids Max OSC routing conflicts
- **Deferred processing** — all M4L outlets use `Task.schedule()` to avoid blocking audio/UI thread
- **LiveAPI cursor reuse** — `goto()` reuses 3 cursors instead of creating ~193 new instances
- **Fire-and-forget writes** — no post-set readback (the #1 crash pattern)
- **Dynamic timeouts** — scale with operation size (~150ms/param, min 10s)
- **Socket drain** — clears stale UDP responses before each command
- **Singleton guard** — exclusive port lock prevents duplicate server instances
- **Disk-persisted cache** — 6,400+ browser items in gzip; instant startup (~50ms)
- **Auto-reconnect** — exponential backoff for TCP and UDP connections

---

## Flexibility

- **Any MCP client** — Claude Desktop, Cursor, Claude Code, or any MCP-compatible tool
- **288 tools without Max for Live** — full session control via TCP/UDP Remote Script; M4L is optional
- **+43 deep-access tools with M4L** — hidden parameters, rack internals, audio analysis, event monitoring
- **+19 optional ElevenLabs tools** — AI voice generation, sound effects, cloning, transcription
- **Ableton Live 10, 11, and 12** — graceful API fallbacks for version-specific features
- **Cross-platform** — Windows and macOS
- **Quick setup** — `uv run` for server, one folder for Remote Script, one M4L device for bridge

---

## Version

**v3.1.0** — see [CHANGELOG.md](CHANGELOG.md) for full release history.

---

## Optional: ElevenLabs Voice & SFX Server

19 tools for AI voice generation, sound effects, voice cloning, and transcription. Generated audio saves to your Ableton User Library.

See [installation_process.txt](installation_process.txt) for setup instructions, or add to your MCP config:

```json
{
  "elevenlabs": {
    "command": "uv",
    "args": ["run", "elevenlabs-mcp"],
    "env": { "ELEVENLABS_API_KEY": "your_key_here" }
  }
}
```
