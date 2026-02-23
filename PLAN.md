# AbletonBridge: Multi-Phase Implementation Plan

**Based on:** [ADVERSARIAL_ANALYSIS.md](./ADVERSARIAL_ANALYSIS.md)
**Date:** 2026-02-23
**Phases:** 6 (ordered by criticality)
**Estimated total scope:** ~40 work items across performance, architecture, features, reliability, and testing

---

## Phase 0: Critical Fixes (Unblock Everything Else)

**Goal:** Eliminate server-hang scenarios and provide foundational capability introspection.
**Prerequisite for:** All subsequent phases.
**Estimated effort:** 1-2 days

### 0.1 Fix Device URI Resolution Blocking (60s hang)

**Problem:** `_resolve_device_uri()` at `server.py:969` enters a polling loop that blocks the entire MCP event loop for up to 60 seconds when the browser cache isn't ready.

**Changes:**
- `MCP_Server/server.py`: Replace the `for _ in range(120): time.sleep(0.5)` polling loop with a bounded 5-second wait using `threading.Event`
- Add a `_browser_cache_ready = threading.Event()` that is set by `_browser_cache_warmup()` upon completion
- If the event doesn't fire within 5s, return the input as-is with a warning rather than blocking

```python
# Before (blocks up to 60s):
for _ in range(120):
    time.sleep(0.5)
    with _browser_cache_lock:
        resolved = _device_uri_map.get(name_lower)

# After (bounded 5s wait):
_browser_cache_ready.wait(timeout=5.0)
with _browser_cache_lock:
    resolved = _device_uri_map.get(name_lower)
if not resolved:
    logger.warning("Cache not ready or device '%s' not found, passing through", uri_or_name)
    return uri_or_name
```

### 0.2 Add `get_server_capabilities` Tool

**Problem:** Claude has no way to know which features are available (M4L connected? Browser cache ready? ElevenLabs configured?) without trial-and-error.

**Changes:**
- `MCP_Server/server.py`: Add a new tool `get_server_capabilities` that returns:
  - `ableton_connected`: bool (TCP socket alive)
  - `m4l_connected`: bool (M4L ping cache status)
  - `browser_cache_ready`: bool (cache populated)
  - `browser_cache_items`: int (number of cached items)
  - `elevenlabs_available`: bool (API key configured)
  - `server_version`: str
  - `m4l_version`: str or null
  - `tool_count`: int
  - `m4l_tool_count`: int (tools that require M4L)

This tool should be the first tool Claude calls in any session.

### 0.3 Fix Stale Version Fallback

**Problem:** `_get_server_version()` at `server.py:1589` falls back to hardcoded "1.9.0" when the actual version is 3.x.

**Changes:**
- `MCP_Server/server.py`: Update fallback to read from a `__version__` constant defined at module top, or parse `pyproject.toml` at startup

---

## Phase 1: Performance — Latency Reduction

**Goal:** Reduce per-tool-call latency by 50-70% for common operations.
**Estimated effort:** 2-3 days

### 1.1 Implement Tiered Command Delays

**Problem:** All 90+ modifying commands get blanket 100ms pre-delay + 100ms post-delay at `server.py:206-223`, adding 200ms overhead even to instant operations like `set_tempo`.

**Changes:**
- `MCP_Server/server.py`: Replace the single `_MODIFYING_COMMANDS` set with three tiers:

```python
# Tier 0: No delay — instant property setters
_INSTANT_COMMANDS = frozenset([
    "set_tempo", "set_track_name", "set_clip_name", "set_track_color",
    "set_clip_color", "set_track_mute", "set_track_solo", "set_track_arm",
    "set_metronome", "set_track_pan", "set_track_volume",
    "set_return_track_volume", "set_return_track_pan", "set_master_volume",
    "set_track_send", "set_crossfader", "set_cue_volume",
    "start_playback", "stop_playback", "continue_playing",
    "undo", "redo", "set_song_time", "set_song_loop",
    "set_clip_looping", "set_device_parameter", "set_device_enabled",
    "set_macro_value", "set_track_monitoring", "set_track_delay",
    "set_clip_launch_mode", "set_clip_launch_quantization",
    "set_clip_legato", "set_draw_mode", "set_follow_song",
    "fire_clip", "stop_clip", "fire_scene", "stop_all_clips",
    "select_scene", "select_track", "select_device", "set_detail_clip",
    "set_clip_properties", "set_clip_follow_actions",
    "set_scene_name", "set_scene_tempo", "set_scene_color",
    "tap_tempo", "set_arrangement_overdub", "set_session_record",
    "re_enable_automation", "end_undo_step",
    "set_track_fold", "set_track_collapse",
    "set_panning_mode", "set_split_stereo_pan",
])

# Tier 1: 50ms post-delay — note/clip/automation operations
_LIGHT_DELAY_COMMANDS = frozenset([
    "add_notes_to_clip", "add_notes_extended", "remove_notes_range",
    "clear_clip_notes", "quantize_clip_notes", "transpose_clip_notes",
    "set_clip_loop_points", "set_clip_start_end", "set_clip_pitch",
    "set_clip_start_time", "set_clip_grid",
    "create_clip_automation", "clear_clip_automation",
    "create_track_automation", "clear_track_automation",
    "create_step_automation", "clear_clip_envelope", "clear_all_clip_envelopes",
    "duplicate_clip", "duplicate_clip_loop", "duplicate_clip_region",
    "crop_clip", "reverse_clip", "set_clip_warp", "set_warp_mode",
    "move_clip_playing_pos", "duplicate_clip_slot",
    "set_device_parameters_batch", "set_drum_pad", "copy_drum_pad",
    "set_chain_selector", "set_chain_properties",
    "capture_midi", "apply_groove",
    "set_groove_settings", "set_song_settings",
    "set_fire_button_state", "clip_scrub_native", "clip_stop_scrub",
    "add_warp_marker", "move_warp_marker", "remove_warp_marker",
    "set_compressor_sidechain", "set_eq8_properties",
    "set_simpler_properties", "simpler_sample_action", "manage_sample_slices",
])

# Tier 2: 100ms post-delay — structural changes (everything else modifying)
# Includes: create_midi_track, create_audio_track, delete_track,
# load_instrument_or_effect, load_browser_item, group_tracks,
# create_scene, delete_scene, freeze_track, etc.
```

- Update `send_command()` to apply delay by tier:

```python
if command_type in _INSTANT_COMMANDS:
    pass  # no delay
elif command_type in _LIGHT_DELAY_COMMANDS:
    time.sleep(0.05)  # 50ms post-delay only
else:
    if is_modifying:
        time.sleep(0.1)  # 100ms post-delay only (remove pre-delay)
```

### 1.2 Replace Browser Cache Warmup Sleep with Event-Driven Trigger

**Problem:** `_browser_cache_warmup()` at `server.py:893` unconditionally sleeps 5 seconds.

**Changes:**
- `MCP_Server/server.py`: Replace `time.sleep(5)` with a wait on the Ableton connection event:

```python
# Replace:
time.sleep(5)
for _ in range(20):
    if _ableton_connection and _ableton_connection.sock:
        break
    time.sleep(0.5)

# With:
_ableton_connected_event = threading.Event()
# (set this event inside get_ableton_connection() on first success)
_ableton_connected_event.wait(timeout=15.0)
if not _ableton_connected_event.is_set():
    logger.warning("Browser warmup: Ableton not connected after 15s, skipping")
    return
time.sleep(0.5)  # brief settle after connection confirmed
```

### 1.3 Add Async Tool Handlers

**Problem:** All 331 tool handlers are synchronous, blocking the FastMCP async event loop during TCP I/O.

**⚠️ Prerequisite — Thread Safety:** The server currently has 15+ global mutable stores
(`_snapshot_store`, `_macro_store`, `_param_map_store`, `_m4l_ping_cache`,
`_ableton_connection`, `_m4l_connection`, `_tool_call_log`, `_tool_call_counts`,
`_device_uri_map`, etc.) of which only 3 are protected by locks (`_tool_call_lock`,
`_server_log_lock`, `_browser_cache_lock`). Moving tool handlers to a thread pool
via `asyncio.to_thread()` would allow concurrent tool execution, turning every
unprotected global into a data race. **This must be addressed before or atomically
with the async conversion.**

**Changes (two sub-steps, in strict order):**

**Step 1 — Add global tool execution lock (serializing bridge):**

Until per-store locks are added in Phase 2.6, use a single `threading.Lock` to
serialize all tool execution. This unblocks the async event loop (the `await`
yields control back to FastMCP while the tool waits for the lock) without
introducing concurrency against unprotected globals:

```python
import asyncio

# Serializing lock — ensures only one tool handler touches global state at a time.
# This is a temporary bridge until Phase 2.6 adds granular per-store locks.
# At that point, this lock should be removed and tools can run fully concurrent.
_tool_execution_lock = threading.Lock()

def _tool_handler(error_prefix: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                def _guarded():
                    with _tool_execution_lock:
                        return func(*args, **kwargs)
                return await asyncio.to_thread(_guarded)
            except ValueError as e:
                return f"Invalid input: {e}"
            except ConnectionError as e:
                return f"M4L bridge not available: {e}"
            except Exception as e:
                logger.error("Error %s: %s", error_prefix, e)
                return f"Error {error_prefix}: {e}"
        return wrapper
    return decorator
```

This gives us the async event loop benefit (FastMCP can handle MCP protocol
messages, healthchecks, etc. while a tool blocks on Ableton I/O) without
enabling unsynchronized concurrent access to shared state.

**Step 2 — Remove serializing lock after Phase 2.6:**

Once Phase 2.6 adds per-store locks to all mutable globals, remove
`_tool_execution_lock` and let tools run fully concurrently:

```python
# After Phase 2.6 — tools are individually thread-safe
def _tool_handler(error_prefix: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except ValueError as e:
                return f"Invalid input: {e}"
            except ConnectionError as e:
                return f"M4L bridge not available: {e}"
            except Exception as e:
                logger.error("Error %s: %s", error_prefix, e)
                return f"Error {error_prefix}: {e}"
        return wrapper
    return decorator
```

**Note:** Even with per-store locks, the Ableton TCP connection itself is
inherently serial (one command at a time over a single socket). True concurrent
tool execution requires either (a) connection pooling or (b) multiplexed
request IDs — both out of scope for Phase 2. The practical concurrency win
is freeing the event loop, not parallel Ableton commands.

---

## Phase 2: Architecture — Modularize the Server

**Goal:** Split the monolithic 11,839-line `server.py` into a maintainable module structure. Enable testing and independent development of feature areas.
**Prerequisite for:** Phase 4 (testing).
**Estimated effort:** 3-5 days

### 2.1 Define Module Structure

Create the following directory layout:

```
MCP_Server/
├── __init__.py                 # Package init, re-export main()
├── server.py                   # FastMCP setup, lifespan, main() (~200 lines)
├── connections/
│   ├── __init__.py
│   ├── ableton.py              # AbletonConnection class (~240 lines)
│   └── m4l.py                  # M4LConnection class + helpers (~510 lines)
├── cache/
│   ├── __init__.py
│   └── browser.py              # Browser cache, device URI map (~310 lines)
├── dashboard/
│   ├── __init__.py
│   └── server.py               # Dashboard HTTP server + HTML (~300 lines)
├── tools/
│   ├── __init__.py              # Registers all tool modules with the mcp instance
│   ├── _common.py               # Shared helpers: _tool_handler, _validate_*, _m4l_result
│   ├── session.py               # Transport, tempo, recording, playback tools
│   ├── tracks.py                # Track CRUD, routing, monitoring tools
│   ├── clips.py                 # Clip CRUD, notes, loop points, launch tools
│   ├── devices.py               # Device parameters, macros, drum pads, racks
│   ├── browser.py               # Browser search, load instrument, presets
│   ├── mixer.py                 # Volume, pan, sends, crossfader tools
│   ├── automation.py            # Clip/track automation, envelopes
│   ├── arrangement.py           # Arrangement clips, time editing
│   ├── creative.py              # Generation tools (chords, drums, arpeggios, bass, euclidean)
│   ├── m4l_tools.py             # All M4L bridge tools (hidden params, chains, etc.)
│   ├── snapshots.py             # Snapshot/macro/parameter map stores
│   └── audio.py                 # Audio analysis, warp, freeze tools
├── grid_notation.py             # Unchanged — ASCII-to-MIDI compiler
└── validation.py                # Input validation helpers (~80 lines)
```

### 2.2 Extract Connection Classes

**Move from `server.py` to separate files:**
- `AbletonConnection` (lines 26-241) → `connections/ableton.py`
- `M4LConnection` (lines 243-804) → `connections/m4l.py`
- Move `_MODIFYING_COMMANDS` / tier sets into `connections/ableton.py`

### 2.3 Extract Cache Logic

**Move:**
- Browser cache globals + functions (lines 1048-1412) → `cache/browser.py`
- Move `_resolve_device_uri()` (line 948) into `cache/browser.py`
- Export `get_device_uri`, `search_cache`, `get_cache_status` functions

### 2.4 Extract Dashboard

**Move:**
- Dashboard HTML, server class, and startup/shutdown (lines 1029-1660) → `dashboard/server.py`
- Make dashboard opt-in via `ABLETON_BRIDGE_DASHBOARD_ENABLED=1` env var

### 2.5 Extract Tool Handlers

**Move each tool category into its own module:**
- Each module receives the `mcp` instance via a `register_tools(mcp)` function
- `tools/__init__.py` calls all `register_tools()` functions
- `server.py` imports `tools` and the registration happens automatically

**Pattern for each tool module:**
```python
# tools/session.py
from MCP_Server.tools._common import _tool_handler, _validate_range
from MCP_Server.connections.ableton import get_ableton_connection
import json

def register_tools(mcp):

    @mcp.tool()
    @_tool_handler("getting session info")
    def get_session_info(ctx) -> str:
        """Get detailed information about the current Ableton session"""
        ableton = get_ableton_connection()
        result = ableton.send_command("get_session_info")
        return json.dumps(result)

    # ... remaining session tools
```

### 2.6 Fix Global Mutable State

**⚠️ Blocks Phase 1.3 Step 2:** The serializing `_tool_execution_lock` added in
Phase 1.3 Step 1 cannot be removed until every store listed below has its own
lock. This sub-phase is the gate that unlocks full concurrent tool execution.

**Currently protected (3 of 15+):**
- `_tool_call_log` / `_tool_call_counts` → `_tool_call_lock` ✅
- `_server_log_buffer` → `_server_log_lock` ✅
- `_browser_cache_flat` / `_browser_cache_by_category` / `_device_uri_map` → `_browser_cache_lock` ✅

**Need per-store locks added:**
- `_snapshot_store`, `_macro_store`, `_param_map_store` → wrap with `threading.Lock()` in `tools/snapshots.py`
- `_m4l_ping_cache` → wrap with `threading.Lock()` in `connections/m4l.py`
- `_ableton_connection`, `_m4l_connection` → use `threading.Lock()` for access in `connections/__init__.py`
- `_browser_cache_timestamp`, `_browser_cache_populating` → already under `_browser_cache_lock` but verify all access sites
- `_server_start_time` → set once at startup, read-only after; document as safe
- `_dashboard_server` → set once at startup; document as safe
- `_singleton_lock_sock` → set/cleared only in lifespan; document as safe

**Implementation:** Replace bare dict/deque access patterns with a `ThreadSafeStore` helper:

```python
class ThreadSafeStore:
    """Dict-like store with built-in locking."""
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key, value):
        with self._lock:
            self._data[key] = value

    def delete(self, key):
        with self._lock:
            self._data.pop(key, None)

    def items(self):
        with self._lock:
            return list(self._data.items())
```

**Completion criteria:** Once all stores above are protected, remove
`_tool_execution_lock` from `_tool_handler` (Phase 1.3 Step 2) and verify
no regressions under concurrent tool calls.

---

## Phase 3: Performance — Compound Tools & Tool Consolidation

**Goal:** Reduce tool call count for common workflows by 3-5x. Reduce total tool count from 331 toward ~150-200.
**Estimated effort:** 3-5 days

### 3.1 Add Compound Workflow Tools

Create `tools/workflows.py` with high-level tools that orchestrate multiple Remote Script commands in a single MCP tool call:

| Compound Tool | Replaces | Commands Batched |
|---|---|---|
| `create_instrument_track(instrument, name, color_index)` | `create_midi_track` + `load_instrument_or_effect` + `set_track_name` + `set_track_color` | 3-4 |
| `create_clip_with_notes(track, slot, length, notes, name)` | `create_clip` + `add_notes_to_clip` + `set_clip_name` | 2-3 |
| `setup_send_return(effect_name, return_name, source_tracks, send_levels)` | `create_return_track` + `load_instrument_or_effect` + N x `set_track_send` | 3+N |
| `create_drum_track(pattern_style, name, clip_length)` | `create_midi_track` + load Drum Rack + `create_clip` + `generate_drum_pattern` + `set_track_name` | 5 |
| `get_full_session_state()` | `get_session_info` + `get_all_tracks_info` + `get_return_tracks_info` + `get_scenes` | 4 |
| `apply_effect_chain(track, effects[])` | N x `load_instrument_or_effect` (appended to track device chain) | N |
| `batch_set_mixer(settings[])` | N x `set_track_volume` / `set_track_pan` / `set_track_send` | N |
| `create_arrangement_section(tracks_data[], time, length)` | Multiple arrangement clip creation + note addition | Many |

Each compound tool calls `send_command` multiple times internally, avoiding MCP round-trip overhead per sub-operation.

### 3.2 Consolidate Overlapping Tools

Merge tools that differ only by `track_type` parameter:

| Current (3 tools) | Consolidated (1 tool) |
|---|---|
| `set_track_volume` + `set_return_track_volume` + `set_master_volume` | `set_volume(track_index, volume, track_type="track"\|"return"\|"master")` |
| `set_track_pan` + `set_return_track_pan` | `set_pan(track_index, pan, track_type)` |
| `set_track_mute` + `set_return_track_mute` | `set_mute(track_index, mute, track_type)` |
| `set_track_solo` + `set_return_track_solo` | `set_solo(track_index, solo, track_type)` |
| `get_clip_notes` + `get_notes_extended` | `get_clip_notes(track, clip, start_time, time_span, start_pitch, pitch_span, extended=False)` |

**Target:** Reduce from 331 → ~200 tools with no loss of functionality.

### 3.3 Add Grid Notation Input Tool

**Problem:** `grid_notation.py` exists but no tool directly accepts grid notation text.

**Changes:**
- `tools/creative.py`: Add `write_grid_notation(track_index, clip_index, notation_text)` that compiles ASCII grid notation to MIDI and writes to clip in one call
- Add `read_clip_as_grid(track_index, clip_index)` that reads clip notes and returns ASCII grid notation

---

## Phase 4: Reliability & Testing

**Goal:** Add test coverage, fix error handling gaps, and improve connection resilience.
**Estimated effort:** 4-6 days

### 4.1 Add Unit Test Suite

Create `tests/` directory:

```
tests/
├── conftest.py                 # Shared fixtures (mock connections, sample data)
├── test_validation.py          # Input validation helpers
├── test_grid_notation.py       # Grid notation compile/decompile
├── test_connections.py         # AbletonConnection/M4LConnection (mocked sockets)
├── test_browser_cache.py       # Cache population, URI resolution, disk persistence
├── test_creative_tools.py      # Chord generation, drum patterns, arpeggios, bass lines
├── test_tool_handlers.py       # Tool handler decorator, error wrapping
└── test_compound_tools.py      # Compound workflow tools
```

**Priority test targets:**
1. `validation.py` — all `_validate_*` functions with boundary cases
2. `grid_notation.py` — drum/melodic compile + decompile round-trips
3. `cache/browser.py` — URI resolution, cache loading/saving, TTL logic
4. `tools/creative.py` — chord progression math, Euclidean rhythm, scale tables
5. `connections/ableton.py` — command serialization, retry logic (with mock socket)
6. `connections/m4l.py` — OSC message building, chunked response reassembly

**Dependencies:** Add `pytest` to dev dependencies in `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-asyncio>=0.21"]
```

### 4.2 Fix M4L Command Queuing

**Problem:** M4L bridge returns "Discovery busy" / "Batch busy" when a second operation arrives during an active chunked operation (Section 1.5 of analysis).

**Changes:**
- `MCP_Server/connections/m4l.py` (after Phase 2 split): Add a command queue with retry logic:

```python
_M4L_RETRY_ATTEMPTS = 3
_M4L_RETRY_DELAY = 0.5  # seconds

def send_command_with_retry(self, command, params=None, timeout=None):
    for attempt in range(_M4L_RETRY_ATTEMPTS):
        result = self.send_command(command, params, timeout)
        if result.get("status") == "error" and "busy" in result.get("message", "").lower():
            time.sleep(_M4L_RETRY_DELAY * (attempt + 1))
            continue
        return result
    return result  # return last error after all retries
```

- Update all M4L tools to use `send_command_with_retry()`

### 4.3 Improve Error Consistency

**Problem:** Tools return a mix of JSON strings and plain text (Section 4.8 of analysis).

**Changes:**
- Define a standard return format in `tools/_common.py`:

```python
def tool_success(message: str, data: dict = None) -> str:
    """Standard success response."""
    result = {"status": "ok", "message": message}
    if data:
        result["data"] = data
    return json.dumps(result)

def tool_error(message: str) -> str:
    """Standard error response."""
    return json.dumps({"status": "error", "message": message})
```

- Migrate tools incrementally (new tools use the standard format; legacy tools are updated during Phase 2 split)

### 4.4 Add Input Size Limits

**Problem:** No limits on note counts, automation points, or parameter batch sizes (Section 5.3 of analysis).

**Changes:**
- `tools/_common.py`: Add validation constants and helpers:

```python
MAX_NOTES_PER_CALL = 10_000
MAX_AUTOMATION_POINTS = 500
MAX_BATCH_PARAMETERS = 200
MAX_SEARCH_QUERY_LENGTH = 500

def _validate_list_size(items, name, max_size):
    if len(items) > max_size:
        raise ValueError(f"{name} has {len(items)} items, maximum is {max_size}")
```

### 4.5 Add Idempotency Guards for Dangerous Retries

**Problem:** Retry logic can cause duplicate `create_midi_track` or `delete_track` operations (Section 6.5).

**Changes:**
- `connections/ableton.py`: Disable retry for non-idempotent commands:

```python
_NON_IDEMPOTENT_COMMANDS = frozenset([
    "create_midi_track", "create_audio_track", "create_return_track",
    "create_scene", "delete_track", "delete_scene", "delete_device",
    "delete_return_track", "delete_clip", "add_notes_to_clip",
    "add_notes_extended", "create_clip",
])

# In send_command():
max_attempts = 1 if command_type in _NON_IDEMPOTENT_COMMANDS else 2
```

---

## Phase 5: Feature Gaps — Plugin & Workflow Enhancements

**Goal:** Address the highest-impact feature gaps identified for Ableton plugin workflows.
**Estimated effort:** 5-8 days

### 5.1 Add Plugin Info Tool

**Changes:**
- `tools/devices.py`: Add `get_plugin_info(track_index, device_index, track_type)`:
  - Reports device `class_name` (PluginDevice, AuPluginDevice, etc.)
  - Number of parameters exposed vs. total
  - Whether the plugin is configured (has exposed parameters)
  - Known limitations for the plugin type
  - Latency compensation info (if available via LOM)

### 5.2 Add Preset Browser Tools

**Changes:**
- `tools/browser.py`: Add tools for navigating device presets:
  - `get_device_presets(track_index, device_index)` — list available presets for a loaded device by navigating the browser tree for that device type
  - `load_device_preset(track_index, device_index, preset_name)` — load a specific preset by navigating and hot-swapping

**Note:** VST internal presets are NOT accessible via the scripting API. These tools work with Ableton's preset system (.adv files, browser presets). Document this limitation clearly in tool descriptions.

### 5.3 Add Effect Chain Template Tools

**Changes:**
- `tools/snapshots.py`: Extend the existing snapshot store:
  - `save_effect_chain(track_index, template_name)` — saves the ordered list of devices + their parameter states
  - `load_effect_chain(track_index, template_name)` — loads devices in order, sets parameters
  - `list_effect_chain_templates()` — lists saved templates
  - Persist templates to `~/.ableton-bridge/chain_templates.json`

### 5.4 Add Sidechain Routing by Track Name

**Changes:**
- `tools/devices.py`: Enhance `set_compressor_sidechain` with a `source_track_name` parameter that resolves the track name to the correct routing index:

```python
@mcp.tool()
def set_sidechain_from_track(ctx, track_index, device_index, source_track_name, ...):
    """Set up sidechain compression from a named source track.
    Example: set_sidechain_from_track(1, 0, source_track_name="Kick")
    """
    # Resolve track name to track index
    # Get available input routing types for the compressor
    # Find matching route and apply
```

### 5.5 Add Spectral/Loudness Analysis (M4L)

**Changes:**
- `M4L_Device/m4l_bridge.js`: Extend `handleAnalyzeAudio` to return:
  - RMS and peak levels over a configurable window
  - Simple spectral energy distribution (low/mid/high bands) via MSP objects
- `tools/m4l_tools.py`: Add `analyze_loudness(track_index, duration_ms)` tool

### 5.6 Document VST/AU Limitations

**Changes:**
- Add a `PLUGIN_COMPATIBILITY.md` documenting:
  - Which VST/AU operations work and which don't
  - The "Configure" requirement for >32 parameter plugins
  - Internal preset browser inaccessibility
  - Known-good workflow patterns for popular plugins (Serum, Vital, Kontakt)

---

## Phase 6: MCP Protocol Enrichment

**Goal:** Implement MCP Resources and Prompts to reduce tool overhead and improve Claude's workflow guidance.
**Estimated effort:** 3-4 days

### 6.1 Implement MCP Resources

**Changes:**
- `MCP_Server/server.py` (or `tools/resources.py`): Register MCP resources using FastMCP's resource API:

```python
@mcp.resource("ableton://session")
def get_session_resource() -> str:
    """Current Ableton session state (tempo, time sig, track count, transport)"""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_session_info")
    return json.dumps(result)

@mcp.resource("ableton://tracks")
def get_tracks_resource() -> str:
    """All tracks with names, types, armed status, device counts"""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_all_tracks_info")
    return json.dumps(result)

@mcp.resource("ableton://capabilities")
def get_capabilities_resource() -> str:
    """Server capabilities (M4L status, cache state, version info)"""
    return json.dumps(_build_capabilities_dict())
```

### 6.2 Implement MCP Prompts

**Changes:**
- `MCP_Server/server.py` (or `tools/prompts.py`): Register workflow prompt templates:

```python
@mcp.prompt("create-beat")
def create_beat_prompt(genre: str = "rock", bars: int = 4) -> str:
    """Guided drum pattern creation workflow"""
    return f"""Create a {bars}-bar {genre} drum beat:
1. Use get_server_capabilities to check connection
2. Create a MIDI track with a Drum Rack
3. Create a {bars * 4}-beat clip
4. Generate a {genre} drum pattern
5. Set appropriate track volume and name"""

@mcp.prompt("mix-track")
def mix_track_prompt(track_name: str = "") -> str:
    """Structured mixing workflow for a single track"""
    return f"""Mix the track '{track_name}':
1. Read current session state via ableton://tracks resource
2. Get device parameters for existing effects
3. Apply gain staging (target -18dBFS average)
4. Add EQ8 for frequency shaping if not present
5. Add Compressor for dynamics if needed
6. Set pan position based on instrument role
7. Adjust send levels for reverb/delay"""
```

### 6.3 Add Version Compatibility Check

**Changes:**
- `MCP_Server/connections/m4l.py`: On first successful M4L ping, compare server version with M4L bridge version. Log a warning if they differ significantly.
- Include version info in `get_server_capabilities` output.

---

## Dependency Graph

```
Phase 0 (Critical Fixes)
    │
    ├── Phase 1 (Latency Reduction)
    │   ├── 1.1 Tiered Delays ── can start immediately after Phase 0
    │   ├── 1.2 Cache Warmup ── can start immediately after Phase 0
    │   └── 1.3 Async Handlers
    │       ├── Step 1: with serializing lock ── can land in Phase 1
    │       └── Step 2: remove lock ── BLOCKED on Phase 2.6 (per-store locks)
    │               │
    │               └── Phase 3 (Compound Tools) ── needs tiered delays + safe concurrency
    │
    └── Phase 2 (Modularize) ── can start immediately after Phase 0
            │
            ├── 2.6 Thread Safety ── MUST complete before Phase 1.3 Step 2
            │
            ├── Phase 4 (Testing) ── needs modules split to write tests
            │
            └── Phase 5 (Feature Gaps) ── easier to add features in modular codebase
                    │
                    └── Phase 6 (MCP Enrichment) ── benefits from all prior phases
```

**Parallelization:** Phase 1 (1.1, 1.2, 1.3 Step 1) and Phase 2 can be developed
in parallel. Phase 1.3 Step 2 (removing the serializing lock for full concurrency)
is explicitly blocked on Phase 2.6 completing per-store thread safety. Phase 3
depends on Phase 1 (tiered delays) being merged first.

**Critical ordering constraint:** `asyncio.to_thread()` without the serializing lock
MUST NOT land until all 15 global mutable stores have per-store locks (Phase 2.6).
The serializing lock in Step 1 is the safety bridge that makes this safe to ship
incrementally.

---

## Success Metrics

| Metric | Current | Phase 1 Target | Phase 3 Target |
|---|---|---|---|
| Simple property set latency | ~300ms | ~50ms | ~50ms |
| "Create a beat" workflow (5 tools) | ~1.5s | ~1.0s | ~300ms (1 compound tool) |
| Full session read (20 tracks) | ~6s | ~4s | ~1s (batch + resources) |
| Browser search (cold cache) | 5-15s | ~2s | ~2s |
| Tool count | 331 | 331 | ~200 |
| Test coverage | 0% | 0% | ~40% (Phase 4) |
| M4L "busy" failures | 100% on rapid calls | 100% | ~0% (retry logic) |

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Phase 2 module split introduces regressions | Medium | High | Add Phase 4 tests before splitting; maintain backward-compatible imports |
| Tiered delays cause stability issues | Low | Medium | Test each tier against Ableton; keep Tier 2 as fallback |
| Compound tools add complexity without adoption | Low | Low | Track tool usage via dashboard; deprecate unused tools |
| Push 3 Python API deprecation | Medium (long-term) | High | Phase 5 expands M4L bridge capabilities as hedge |
| FastMCP async wrapper breaks existing tools | Low | High | Serializing lock in Phase 1.3 Step 1 preserves single-threaded semantics; reversible |
| Async + unprotected globals = data races | **High if misordered** | **Critical** | Phase 1.3 Step 2 (lock removal) is hard-gated on Phase 2.6 completion; CI check should enforce |
