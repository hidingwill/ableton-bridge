# AbletonBridge: Remaining Work Plan (v2)

**Supersedes:** PLAN.md (Phases 0-2 complete, 3/4/6 partial, 5 not started)
**Based on:** [PLAN_REVIEW.md](./PLAN_REVIEW.md), [ADVERSARIAL_ANALYSIS.md](./ADVERSARIAL_ANALYSIS.md)
**Date:** 2026-02-23
**Phases:** 4 (ordered by impact and dependency)

---

## Phase A: Tool Consolidation & Cleanup

**Goal:** Reduce tool count from 334 toward ~280, remove dead code, and fix duplicate tools.
**Prerequisite for:** Phase C (consistent error responses depend on fewer tools to migrate).
**Risk:** Low — removals are behind consolidated replacements that already exist.

### A.1 Remove Duplicate Tools in `session.py`

**Problem:** Two tools do the same thing with different names.

| Duplicate | Keep | Remove | Why |
|---|---|---|---|
| `set_song_time` (line 147) | `set_playback_position` (line 261) | `set_song_time` | `set_playback_position` is the clearer name |

**Changes:**
- `tools/session.py`: Remove the `set_song_time` tool definition (lines 146-157)
- `constants.py`: Remove `"set_song_time"` from `TIER_0_COMMANDS` if present (already covered by `set_playback_position`)

### A.2 Remove Redundant Loop Setters in `session.py`

**Problem:** `set_loop_start` (line 226), `set_loop_end` (line 238), and `set_loop_length` (line 250) are all superseded by `set_song_loop` (line 159), which accepts optional `start` and `length` parameters.

**Changes:**
- `tools/session.py`: Remove `set_loop_start`, `set_loop_end`, `set_loop_length` (lines 225-259)
- `constants.py`: Remove `"set_loop_start"`, `"set_loop_end"`, `"set_loop_length"` from `TIER_2_COMMANDS`

**Note:** `set_song_loop` doesn't currently accept an `end` parameter. Add an optional `end` param that sets `length = end - start` so no functionality is lost.

### A.3 Remove Legacy Mixer Variants

**Problem:** `set_mixer` (mixer.py:428) already consolidates volume/pan/mute/solo across track types. The 9 individual tools remain, inflating the tool count and Claude's context.

**Remove these tools (keep `set_mixer` and `batch_set_mixer`):**

| Tool | Line | Replaced by |
|---|---|---|
| `set_track_volume` | mixer.py:10 | `set_mixer(track_type="track", volume=X)` |
| `set_track_pan` | mixer.py:29 | `set_mixer(track_type="track", pan=X)` |
| `set_track_mute` | mixer.py:48 | `set_mixer(track_type="track", mute=X)` |
| `set_track_solo` | mixer.py:67 | `set_mixer(track_type="track", solo=X)` |
| `set_return_track_volume` | mixer.py:127 | `set_mixer(track_type="return", volume=X)` |
| `set_return_track_pan` | mixer.py:146 | `set_mixer(track_type="return", pan=X)` |
| `set_return_track_mute` | mixer.py:165 | `set_mixer(track_type="return", mute=X)` |
| `set_return_track_solo` | mixer.py:184 | `set_mixer(track_type="return", solo=X)` |
| `set_master_volume` | mixer.py:203 | `set_mixer(track_type="master", volume=X)` |

**Impact:** Reduces mixer.py from 22 tools to 13 tools. The `set_mixer` tool internally calls the same Remote Script commands, so no backend changes needed.

**Changes:**
- `tools/mixer.py`: Remove the 9 individual tool definitions (lines 10-221)
- `constants.py`: No change needed (the command names stay in tier sets — they're Remote Script commands, not MCP tool names)
- `tools/workflows.py`: Update `batch_set_mixer` to call `set_mixer` commands directly (it already uses the raw Remote Script commands, so no change needed)

### A.4 Consolidate Sidechain Setters in `devices.py`

**Problem:** `set_compressor_sidechain` (line 787) takes raw indices; `set_sidechain_by_name` (line 814) takes a track name. These can be one tool.

**Changes:**
- `tools/devices.py`: Merge into a single `set_compressor_sidechain` that accepts an optional `source_track_name` parameter. When provided, resolve the name to indices internally. When not provided, use the raw index parameters.
- Remove `set_sidechain_by_name` as a separate tool.

### A.5 Remove Dead Response Helpers or Start Using Them

**Problem:** `tool_success()` and `tool_error()` in `tools/_base.py` are never imported or called by any of the 334 tools — they're dead code.

**Decision point:** Either remove them (simplest) or defer to Phase C where they get adopted. Recommend: keep them, they'll be needed in Phase C.

### A.6 Add Missing Compound Tools from Original Plan

**Problem:** `create_drum_track` and `create_arrangement_section` were specified in PLAN.md Phase 3.1 but never implemented.

**Changes:**
- `tools/workflows.py`: Add `create_drum_track(pattern_style, name, clip_length, bpm)`:
  - Creates MIDI track, loads Drum Rack, creates clip, generates drum pattern, sets name
  - Reuses existing `generate_drum_pattern` from `tools/creative.py`

**Note:** `create_arrangement_section` is complex and vaguely specified. Skip it — the existing compound tools + prompts cover this workflow better.

**Net tool count reduction from Phase A: ~13 tools** (334 → ~321)

---

## Phase B: Test Coverage Expansion

**Goal:** Increase test coverage from 5 test files to 11, covering connections, cache, creative tools, and compound workflows.
**Prerequisite for:** Nothing — can start immediately in parallel with Phase A.
**Risk:** Low — tests are additive.

### B.1 Add Connection Tests

**File:** `tests/test_connections.py`

**Test targets:**
- `AbletonConnection.send_command()` with mocked socket:
  - Successful command round-trip (send JSON, receive JSON)
  - Tier-based delay application (verify Tier 0 has no sleep, Tier 1 has 50ms, Tier 2 has 100ms+100ms)
  - Non-idempotent command retry prevention (`max_attempts=1` for create/delete)
  - Socket reconnection on failure (idempotent commands get 2 attempts)
  - Timeout handling
- `AbletonConnection.send_udp_command()` — fire-and-forget sends
- `get_ableton_connection()` — singleton behavior, reconnection on stale socket

### B.2 Add M4L Connection Tests

**File:** `tests/test_m4l_connection.py`

**Test targets:**
- `M4LConnection._build_osc_message()` — OSC binary format correctness
- `M4LConnection._parse_m4l_response()` — JSON/binary parsing from UDP
- `M4LConnection._reassemble_chunked_response()` — multi-chunk reassembly:
  - Happy path (all chunks arrive in order)
  - Out-of-order chunks
  - Missing chunk → timeout
  - Non-chunk packet during reassembly (ignored)
- `M4LConnection.send_command_with_retry()` — retry on "busy" responses
- `M4LConnection._check_bridge_version()` — version mismatch warning

### B.3 Add Browser Cache Tests

**File:** `tests/test_browser_cache.py`

**Test targets:**
- `build_device_uri_map()` — priority resolution, duplicate name handling
- `resolve_device_uri()` — cache-ready path, cache-not-ready path with event timeout
- `populate_browser_cache()` — mock Ableton responses, verify flat cache + category cache
- `load_browser_cache_from_disk()` / `save_browser_cache_to_disk()` — gzip round-trip
- Cache TTL expiration logic

### B.4 Add Creative Tools Tests

**File:** `tests/test_creative_tools.py`

**Test targets (pure logic, no Ableton connection needed):**
- Chord generation: major/minor/diminished/augmented chord voicings
- Scale tables: all scale types produce correct intervals
- Drum pattern generation: different styles produce valid note lists
- Euclidean rhythm algorithm: known input/output pairs
- Arpeggio patterns: up/down/up-down/random modes
- Bass line generation: root-fifth patterns, walking bass

### B.5 Add Compound Workflow Tests

**File:** `tests/test_workflows.py`

**Test targets (with mocked Ableton connection):**
- `create_instrument_track` — verifies 4 commands sent in order
- `create_clip_with_notes` — verifies create + add_notes + set_name
- `setup_send_return` — verifies return track creation + effect load + send levels
- `get_full_session_state` — verifies 4 queries combined
- `apply_effect_chain` — verifies N load commands, error handling for failed loads
- `batch_set_mixer` — verifies correct Remote Script commands per track_type
- `save_effect_chain` / `load_effect_chain` — round-trip through `state.effect_chain_store`

### B.6 Add Validation Edge Case Tests

**Extend:** `tests/test_validation.py`

**Additional cases:**
- `_reduce_automation_points()` — RDP algorithm with pathological inputs (all same time, single point, exactly max_points)
- `_validate_notes()` — float pitch (should fail), boolean velocity (should fail)
- Integration between `_validate_automation_points()` and `_reduce_automation_points()` — validate then reduce pipeline

---

## Phase C: Reliability & Error Consistency

**Goal:** Standardize error responses, add disk persistence for effect chains, and address reliability gaps from the adversarial analysis.
**Prerequisite:** Phase A (fewer tools to migrate).
**Risk:** Medium — touching return values of existing tools could affect Claude's parsing. Migrate incrementally.

### C.1 Standardize Error Responses (Incremental)

**Problem:** 0% of tools use `tool_success()`/`tool_error()`. 64% return plain strings, 36% return `json.dumps()`. Claude must parse both formats.

**Strategy:** Don't migrate all 334 tools at once. Adopt the standard format for:
1. All new tools written in Phase A and beyond
2. All compound workflow tools (`workflows.py` — 9 tools)
3. All tools that currently return `json.dumps()` — change to `tool_success(message, data)`

Leave plain-string tools alone for now — they work, and the `_tool_handler` decorator already wraps errors consistently. The priority is ensuring JSON-returning tools have a consistent envelope.

**Changes:**
- `tools/workflows.py`: Update all 9 tools to use `tool_success()`
- `tools/_base.py`: Update `_tool_handler` decorator to wrap plain-string returns in `tool_success()`:

```python
async def wrapper(*args, **kwargs):
    try:
        result = await asyncio.to_thread(func, *args, **kwargs)
        # If the tool already returned JSON or used tool_success, pass through
        if isinstance(result, str) and result.startswith("{"):
            return result
        # Wrap plain string results in standard envelope
        return tool_success(result)
    except ValueError as e:
        return tool_error(f"Invalid input: {e}")
    except ConnectionError as e:
        return tool_error(f"M4L bridge not available: {e}")
    except Exception as e:
        logger.error("Error %s: %s", error_prefix, e)
        return tool_error(f"Error {error_prefix}: {e}")
```

This provides 100% coverage in one decorator change without touching individual tools.

### C.2 Add Effect Chain Disk Persistence

**Problem:** `state.effect_chain_store` is in-memory only. Templates are lost on server restart.

**Changes:**
- `tools/workflows.py`: After saving a template to `state.effect_chain_store`, also persist to `~/.ableton-bridge/chain_templates.json`
- On server startup (`server.py` lifespan), load templates from disk into `state.effect_chain_store`
- Follow the same pattern as `cache/browser.py` disk persistence (gzip optional — templates are small)

```python
CHAIN_TEMPLATES_PATH = os.path.join(
    os.path.expanduser("~"), ".ableton-bridge", "chain_templates.json"
)

def _save_chain_templates_to_disk():
    with state.store_lock:
        data = dict(state.effect_chain_store)
    os.makedirs(os.path.dirname(CHAIN_TEMPLATES_PATH), exist_ok=True)
    with open(CHAIN_TEMPLATES_PATH, "w") as f:
        json.dump(data, f, indent=2)

def _load_chain_templates_from_disk():
    if not os.path.exists(CHAIN_TEMPLATES_PATH):
        return
    with open(CHAIN_TEMPLATES_PATH) as f:
        data = json.load(f)
    with state.store_lock:
        state.effect_chain_store.update(data)
```

### C.3 Add M4L Chunked Response Sequence Validation

**Problem (analysis 6.2):** `_reassemble_chunked_response()` has no sequence validation. A lost chunk blocks until timeout with no retransmission. Out-of-order chunks are handled (dict keyed by index), but there's no detection of duplicate or corrupted chunks.

**Changes:**
- `connections/m4l.py` in `_reassemble_chunked_response()`:
  - Add duplicate chunk detection (log warning if same `_c` index arrives twice)
  - Add a progress log every 5 chunks for large responses
  - On timeout, include which chunk indices are missing in the error message

```python
while len(chunks) < total:
    try:
        data, _ = self.recv_sock.recvfrom(65535)
        parsed = self._parse_m4l_response(data)
        if "_c" in parsed and "_t" in parsed:
            idx = parsed["_c"]
            if idx in chunks:
                logger.warning("M4L chunk reassembly: duplicate chunk %d, ignoring", idx)
                continue
            chunks[idx] = parsed["_d"]
            if len(chunks) % 5 == 0:
                logger.info("M4L chunk reassembly: %d/%d", len(chunks), total)
        else:
            logger.warning("M4L chunk reassembly: non-chunk packet, ignoring")
    except socket.timeout:
        missing = sorted(set(range(total)) - set(chunks.keys()))
        logger.error("M4L chunk timeout: missing chunks %s", missing[:10])
        raise Exception(
            f"Timeout receiving chunked M4L response ({len(chunks)}/{total} chunks, "
            f"missing: {missing[:10]})"
        )
```

### C.4 Add Command-Specific Timeouts

**Problem (analysis 4.4):** All commands use a fixed 10s (read) or 15s (modify) timeout. Legitimately slow operations like `load_instrument_or_effect` or `freeze_track` can exceed this.

**Changes:**
- `connections/ableton.py`: Add a `SLOW_COMMANDS` dict mapping command names to custom timeouts:

```python
SLOW_COMMAND_TIMEOUTS = {
    "load_instrument_or_effect": 30.0,
    "load_sample": 30.0,
    "load_drum_kit": 30.0,
    "freeze_track": 60.0,
    "unfreeze_track": 30.0,
    "audio_to_midi": 30.0,
    "get_browser_items_at_path": 20.0,
}
```

- In `send_command()`, apply custom timeout when caller doesn't override:

```python
if timeout is None:
    timeout = SLOW_COMMAND_TIMEOUTS.get(command_type, 15.0 if is_modifying else 10.0)
```

### C.5 Improve Brute-Force Parameter Resolution

**Problem (analysis 1.7):** `_resolve_display_value_bruteforce()` iterates up to 10,000 values on Ableton's main thread. Already capped and has float-range detection, but missing: value caching and binary search.

**Changes (Remote Script side):**
- `AbletonBridge_Remote_Script/handlers/devices.py`: Add a per-parameter display-value cache:

```python
_display_value_cache = {}  # (param.name, param.min, param.max) -> {display: value}

def _resolve_display_value_bruteforce(param, display_string, ctrl=None):
    cache_key = (param.name, param.min, param.max)
    if cache_key in _display_value_cache:
        cached = _display_value_cache[cache_key]
        if display_string in cached:
            return cached[display_string]

    # ... existing iteration logic ...

    # On success, cache the entire mapping for this param
    if cache_key not in _display_value_cache:
        mapping = {}
        for v in range(lo, hi + 1):
            try:
                disp = param.str_for_value(float(v))
                if disp:
                    mapping[disp] = float(v)
            except Exception:
                pass
        _display_value_cache[cache_key] = mapping
    return float(v)
```

This turns the first call into O(n) and all subsequent calls for the same parameter type into O(1).

---

## Phase D: Feature Enhancements

**Goal:** Address the highest-impact Phase 5 gaps from the original plan.
**Prerequisite:** Phase A (clean tool surface). Phase C recommended but not required.
**Risk:** Medium — new tools that interact with Live's API may need iteration.

### D.1 Add Plugin Info Tool

**Changes:**
- `tools/devices.py`: Add `get_plugin_info(track_index, device_index, track_type)`:
  - Reports `class_name` (PluginDevice, AuPluginDevice, MxDeviceAudioEffect, etc.)
  - Parameter count (exposed vs. total if available)
  - Whether the device is "configured" (has more than default 32 parameters exposed)
  - Device-type-specific guidance (e.g., "This is a VST plugin. Parameters beyond the first 32 require using Ableton's Configure button.")

### D.2 Add Preset Browser Tools

**Changes:**
- `tools/browser.py`: Add `get_device_presets(track_index, device_index)`:
  - Navigates the browser tree for the loaded device's category
  - Lists available Ableton presets (.adv files) — NOT VST internal presets
  - Returns list of `{name, uri}` for each preset

- `tools/browser.py`: Add `load_device_preset(track_index, device_index, preset_name)`:
  - Finds preset by name in browser cache
  - Hot-swaps the current device with the preset version
  - Document limitation clearly: "Works with Ableton's preset system only. VST/AU internal presets are not accessible via the scripting API."

### D.3 Add Sidechain Routing by Track Name

Already covered by Phase A.4's consolidation of `set_compressor_sidechain` + `set_sidechain_by_name`.

### D.4 Add VST/AU Plugin Compatibility Documentation

**Changes:**
- Create `PLUGIN_COMPATIBILITY.md`:
  - Which parameter operations work (get/set automatable parameters)
  - What doesn't work (internal preset browser, full parameter access without Configure)
  - The "Configure" button requirement for >32 parameters
  - Known-good patterns for popular plugins
  - Latency and CPU monitoring limitations (not in scripting API)

### D.5 Add MCP Progress Notifications for Long Operations

**Problem (analysis 2.4):** Browser cache scan (5-15s), freeze operations (variable), and instrument loading get no progress feedback.

**Changes:**
- `tools/_base.py`: Add a `_long_running_handler` variant of `_tool_handler` that uses FastMCP's `ctx.report_progress()`:

```python
def _long_running_handler(error_prefix: str, estimated_steps: int = 0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(ctx: Context, *args, **kwargs):
            # Pass ctx through so the tool can report progress
            try:
                return await asyncio.to_thread(func, ctx, *args, **kwargs)
            except Exception as e:
                logger.error("Error %s: %s", error_prefix, e)
                return tool_error(f"Error {error_prefix}: {e}")
        return wrapper
    return decorator
```

- Apply to: `refresh_browser_cache`, `freeze_track`, `get_full_session_state`, `apply_effect_chain`, `load_instrument_or_effect`
- Tools call `ctx.report_progress(current, total)` at meaningful checkpoints

---

## Dependency Graph

```
Phase A (Tool Consolidation)     Phase B (Test Coverage)
    │                                │
    │  (A before C because fewer     │  (B independent — can run
    │   tools to migrate)            │   in parallel with A)
    │                                │
    └───────────┬────────────────────┘
                │
        Phase C (Reliability & Error Consistency)
                │
                │  (C before D because new tools
                │   should use the standard patterns)
                │
        Phase D (Feature Enhancements)
```

**Parallelization:** Phases A and B have no dependencies between them and can be developed concurrently.

---

## Items Explicitly Deferred

These adversarial analysis items are acknowledged but deferred as low-impact or infeasible:

| Item | Reason for Deferral |
|---|---|
| 1.6 M4L connection pooling | Ping cache TTL is workable; connection reuse is already implemented |
| 1.8 Dashboard lazy imports | Startup cost is ~200-500ms one-time; not worth the complexity |
| 1.10 JSON serialization overhead | No actionable improvement without protocol change (msgpack etc.) |
| 1.11 Tool call lock contention | Dashboard refresh is 3s interval; contention is negligible |
| 4.5 UDP backpressure | Fire-and-forget is intentional for real-time parameter updates; adding backpressure would defeat the purpose |
| 4.9 Unused ctx parameter | Will be used when MCP progress notifications land in Phase D.5 |
| 5.2 Dashboard XSS | Dashboard is localhost-only; XSS risk is minimal |
| 6.1 Connection loss state tracking | Complex; partial-completion recovery would require transaction semantics that the Remote Script doesn't support |
| 3.4-3.15 (Feature gaps) | Dependent on Ableton's scripting API limitations; out of scope for this plan |

---

## Success Metrics

| Metric | Current | After Phase A | After All Phases |
|---|---|---|---|
| Tool count | 334 | ~321 | ~323 (net: removed 13, added 2 in D) |
| Test files | 5 | 5 | 11 |
| Error response consistency | 0% standardized | 0% | ~100% (via decorator) |
| Effect chain persistence | In-memory only | In-memory only | Disk-persisted |
| Brute-force param resolution | 10K iterations, no cache | Same | Cached after first call |
| M4L chunk error diagnostics | "timeout" message | Same | Missing chunk indices reported |
| Slow command timeouts | Fixed 10s/15s | Same | Per-command (up to 60s for freeze) |
