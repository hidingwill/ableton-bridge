# Changelog

All notable changes to AbletonMCP Beta will be documented in this file.

---

## v2.9.1 — 2026-02-15

### Hardening Round 8 — Safety, Thread-Safety, Security & Correctness (30+ fixes)

Internal hardening sweep across Remote Script, ElevenLabs MCP, and documentation. No new tools, no API changes.

#### Remote Script: Thread-Safety

- **fix**: TCP `schedule_message` fallback — when `schedule_message()` raises `AssertionError` (Ableton shutting down), no longer calls `main_thread_task()` inline from the client handler thread. Now logs and returns an error response, matching the UDP path behavior.
- **fix**: UDP `schedule_message` fallback — same pattern: drops update with log message instead of executing on the wrong thread.
- **fix**: UDP thread-safety — `self._song` is no longer captured on the UDP thread; all Live API access now happens inside `task()` closures that run on the main thread via `schedule_message`.

#### Remote Script: Audio Handlers

- **fix**: `freeze_track` / `unfreeze_track` — return `success: False` + `requires_manual_action: True` when programmatic freeze is unavailable, so callers know the operation did not complete.
- **fix**: Bare `except: pass` in audio sample enumeration replaced with `except Exception as sample_err:` + `ctrl.log_message()` with clip name.
- **fix**: `get_audio_clip_info` / `analyze_audio_clip` — file path sanitized to basename only (prevents leaking local filesystem paths).
- **fix**: `character_map` added missing key `3` ("pitched") for re_pitch warp mode; summary guard skips "unknown" warp character labels.

#### Remote Script: Automation Handlers

- **fix**: `_find_parameter` send-name parsing — restricted to well-formed single-letter send names (`^send\s*[a-z]$`); rejects false matches like "resend" or "send_abc".
- **fix**: `create_clip_automation` — clip-level time clamping now uses `clip_length - 0.001` (was `clip_length`), consistent with `create_track_automation`'s epsilon; prevents inserting a breakpoint at the invalid clip-end position.

#### Remote Script: Browser Handlers

- **fix**: `get_browser_items_at_path` — replaced unreachable `if not path_parts` dead branch (always non-empty after `split("/")`) with early `if not path` guard that actually catches empty input.

#### Remote Script: Mixer Handlers

- **fix**: `set_crossfade_assign` — added implementation to `handlers.mixer` so the dispatch table entry no longer raises `AttributeError`.

#### Remote Script: Clip Handlers

- **fix**: `add_notes_to_clip` Strategy 3 — returns `len(note_specs)` (notes added) not `len(live_notes)` (total notes).
- **fix**: `add_warp_marker` — uses positional args `clip.add_warp_marker(bt)` / `clip.add_warp_marker(bt, sample_time)` instead of dict.

#### Remote Script: Device Handlers

- **fix**: `_resolve_display_value_bruteforce` — detects float-range parameters and raises clear `ValueError` instead of infinite-looping.
- **refactor**: 7 specialized device helpers (`_get_drum_rack`, `_get_rack_device`, `_get_compressor_device`, `_get_eq8_device`, `_get_hybrid_reverb_device`, `_get_transmute_device`, `_get_simpler_device`) now accept `track_type` parameter and use `resolve_track()` — all 17 public callers propagate `track_type`, enabling device operations on return and master tracks.
- **fix**: `sliced_simpler_to_drum_rack` — now accepts `track_type` parameter and uses `resolve_track()` instead of `get_track()`, enabling Simpler-to-Drum-Rack conversion on return/master tracks.
- **fix**: `control_looper` — now accepts `track_type` parameter and uses `resolve_track()` instead of `get_track()`, enabling looper control on return/master tracks.

#### Remote Script: MIDI Handlers

- **fix**: `clear_clip_notes` — uses `clip.length + 1` for counting range (matches removal range).
- **fix**: `apply_groove` — docstring and response now clearly state `groove_amount` is a global song property; added `applied_scope: "song"` and explanatory `note` to return dict.

#### Remote Script: Session Handlers

- **fix**: `set_song_settings` — full validate-then-apply pattern: all inputs validated into `validated{}` dict before mutating song state.

#### Remote Script: Track Handlers

- **fix**: `group_tracks` — raises `NotImplementedError` with guidance instead of returning silent `grouped: False`. Moved raise outside try/except to eliminate double-logging.

#### Remote Script: Dispatch Table

- **fix**: `__init__.py` dispatch table — `delete_device`, `set_macro_value`, and 19 other device handler dispatch entries were passing `ctrl` positionally into the `track_type` parameter slot, breaking return/master track support and dropping controller logging. All 21 entries now use explicit `track_type=p.get("track_type", "track"), ctrl=ctrl` keyword arguments to prevent future signature drift.

#### ElevenLabs MCP: Security

- **fix**: `utils.py` `make_output_file` — filenames now use an 8-character SHA-256 hash of user input instead of raw `text[:5]`, preventing user-provided text from leaking into filenames and logs.
- **fix**: `server.py` `text_to_speech` / `text_to_sound_effects` — log lines no longer include output filenames (which contained user text snippets); replaced with safe metadata (`chars=`, `duration=`).
- **fix**: `server.py` `check_subscription` — no longer returns raw `model_dump_json()` which could expose billing/account metadata; returns only usage-relevant fields (tier, character count/limit, voice limit, status, reset time).
- **fix**: `server.py` `_get_client` — missing API key now raises `ElevenLabsMcpError` (via `make_error()`) instead of raw `ValueError`, consistent with all other validation paths.
- **fix**: `server.py` — all 19 tool functions wrapped with `@_safe_api` decorator that catches `httpx.TimeoutException`, `httpx.HTTPStatusError`, and generic exceptions, re-raising them as `ElevenLabsMcpError` with actionable context. Prevents raw stack traces from leaking to MCP clients.
- **fix**: `server.py` `search_voice_library` — `page` and `page_size` validated before forwarding to API (`page >= 0`, `1 <= page_size <= 100`).
- **fix**: `server.py` `text_to_voice` — empty-description guard now rejects `None`, `""`, and whitespace-only input (was only checking `== ""`).
- **fix**: `server.py` `voice_clone` — replaced `raise RuntimeError(...)` with `make_error(...)` so the error is `ElevenLabsMcpError` and handled consistently by `_safe_api`.
- **fix**: `model.py` `McpVoice` — `fine_tuning_status` type changed from `Optional[Dict]` to `Optional[str]`; `get_voice` passes the fine-tuning `state` string, not the dict, so Pydantic v2 no longer raises `ValidationError`.
- **fix**: `__main__.py` — `--print` output now redacts API keys/secrets/tokens via `_redact_config()` deep-copy.
- **fix**: `__main__.py` — config merge loads existing JSON and merges only the ElevenLabs server entry (was clobbering entire config).
- **fix**: `__main__.py` — `get_claude_config_path()` now returns the platform-specific path even if directory doesn't exist (first-time users). Caller creates it via `mkdir(parents=True)`.
- **fix**: `__main__.py` — corrupt/unreadable config file now logs a warning via `logger.warning()` before falling back to `{}`.
- **fix**: `__main__.py` — accepts file path argument (resolves to parent directory).
- **fix**: `__main__.py` — config file I/O now uses `encoding="utf-8"` to prevent corruption on non-ASCII platforms.

#### ElevenLabs MCP: Reliability

- **fix**: `server.py` `voice_clone` — `response = None` initialization + post-finally guard prevents `UnboundLocalError` when API call fails.
- **fix**: `server.py` `add_knowledge_base_to_agent` — file handle leak fixed: `open()` moved inside `try` block so `finally` always closes it. Path validation (`handle_input_file`) runs first, outside the try.
- **fix**: `server.py` `add_knowledge_base_to_agent` — KB creation is now atomic: the agent-attach logic (agents.get → config traversal → kb append → agents.update) is wrapped in a try/except; on any failure, the newly-created KB document is deleted via `conversational_ai.knowledge_base.delete()` to prevent orphaned documents accumulating on the server. If the compensating delete itself fails, a warning is logged with the orphaned KB ID.
- **fix**: `server.py` `make_outbound_call` — phone number PII: log now shows last 4 digits (`***1234`) instead of first 5 digits (country+area code).
- **refactor**: `server.py` — renamed `output_file_name` → `output_file` across all tools; removed redundant `output_path / output_file` joins since `make_output_file` already returns an absolute Path.
- **fix**: `server.py` `speech_to_text` — transcript file now opens with `encoding="utf-8"` so non-ASCII characters are preserved on all platforms.
- **fix**: `convai.py` — `max_tokens` uses `if max_tokens is not None` instead of `if max_tokens` (allows 0).
- **fix**: `model.py` — `ConvaiAgent` → `ConvAiAgent` for consistent capitalization.

#### ElevenLabs MCP: Path Safety

- **fix**: `utils.py` `make_output_file` — exception chaining: `raise ... from err` preserves original traceback.
- **fix**: `utils.py` `make_output_path` — containment check validates absolute `output_directory` against `base_path`.
- **fix**: `utils.py` `handle_input_file` — validates absolute paths against `base_path`.
- **fix**: `utils.py` `make_error` — added `-> NoReturn` return type annotation with `typing.NoReturn` import for static analysis correctness.
- **fix**: `utils.py` `find_similar_filenames` — return type annotation corrected from `list[tuple[str, int]]` to `list[tuple[Path, int]]` (function actually returns `Path` objects, not strings); docstring updated `directory` parameter from `str` to `Path`.
- **fix**: `utils.py` `make_output_file` — `full_id` parameter now honored: uses full SHA-256 hex digest when `True`, 8-char prefix when `False` (was always using 8-char prefix).

#### Documentation

- **fix**: README — M4L tool count corrected from `+24` to `+38`.
- **fix**: README — MD028 blank lines between blockquotes use `>` prefix.
- **fix**: README — MD040 architecture code fence tagged with `text` language.
- **fix**: README — tool counts unified: 230 core + 19 optional = 249 total; architecture section updated to 197 TCP/UDP + 35 M4L; flexibility section corrected to match.
- **fix**: CHANGELOG — Transmute entry reworded from "(Not working already)" to "(Known broken — Ableton API limitation)".

#### MCP Server

- **fix**: `MCP_Server/__init__.py` — `__version__` updated from `"1.8.2"` to `"2.9.1"` to match pyproject.toml.
- **fix**: `grid_notation.py` — unreachable `line.startswith(' ')` check (post-`strip()`) replaced with pre-strip check on raw line so indented lines are correctly skipped.
- **fix**: `grid_notation.py` — `PREFERRED_LABELS` pitch 40 changed from `'SN'` to `'RM'` to match `DRUM_LABELS` where 40 maps to rimshot, preserving the distinct label.

#### Package Metadata

- **fix**: `pyproject.toml` — description removed "Beta" to match `ableton-mcp-stable` package name.
- **fix**: `pyproject.toml` — `[project.urls]` corrected to canonical `ahujasid/ableton-mcp` repository.
- **fix**: `pyproject.toml` — elevenlabs optional-dependencies: pinned `httpx>=0.24.0` (minimum version supporting explicit `Timeout`); replaced `fuzzywuzzy` with `rapidfuzz` (C++ backend, no `python-Levenshtein` warning).
- **fix**: `utils.py` — updated `from fuzzywuzzy import fuzz` → `from rapidfuzz import fuzz` (drop-in compatible `token_sort_ratio`).

### Tool count: **230** + **19 optional** (ElevenLabs) = **249 total**

> **Note:** Versions v2.8.0–v2.9.0 reported 232 core / 251 total due to a
> tabulation error (197 TCP/UDP + 35 M4L = 232, but 2 categories were
> double-counted). The correct total is 230 core + 19 optional = 249.

---

## v2.9.0 — 2026-02-14

### Performance & Code Quality Sweep

Internal refactoring across all 4 layers — no new tools, no API changes, no behavior changes.

#### Remote Script: O(1) Command Dispatch (was O(n))
- **perf**: Replaced 530-line if/elif dispatch chain with two dict lookup tables (`_MODIFYING_HANDLERS`, `_READONLY_HANDLERS`) — O(1) command routing
- **DRY**: Merged two near-identical `_dispatch_on_main_thread` / `_dispatch_on_main_thread_readonly` wrappers into single `_dispatch_on_main_thread_impl`

#### Remote Script: Shared Validation Helpers
- **refactor**: Extracted `handlers/_helpers.py` with `get_track()`, `get_clip_slot()`, `get_clip()`, `get_scene()` — eliminates ~85 inline validation patterns across all 11 handler files
- Consistent error messages and bounds checking in one place

#### MCP Server: Grid Notation Performance
- **perf**: Pre-compiled regex patterns at module level (was recompiling on every call)
- **perf**: String `+=` in loops replaced with list + `"".join()` (O(n) vs O(n²))
- **perf**: `is_drum_track()` merged from 3 passes to single pass over notes

#### MCP Server: M4L Response Parsing
- **perf**: Reordered base64 decode — tries URL-safe first (the common path since v2.0.0), eliminating 1 exception per response

#### MCP Server: Gzip Browser Cache
- **perf**: Browser disk cache now uses gzip compression (~85% smaller files, faster I/O)
- Backward compatible: loads legacy `.json` caches if `.json.gz` not found

#### M4L Bridge: Object Lookup Maps
- **perf**: Replaced linear array scans with object property lookups in `setSimplerSampleProperty`, `setDeviceProperty`, and readonly checks — O(1) vs O(n)

#### ElevenLabs MCP: Reliability & Streaming
- **fix**: httpx client now has explicit timeouts (60s request, 10s connect) + atexit cleanup
- **fix**: `voice_clone` file handles properly closed in `finally` block (was leaking on mid-list errors)
- **fix**: Path containment uses `relative_to()` instead of fragile string prefix check
- **perf**: Audio data streamed to disk chunk-by-chunk (was `b"".join()` full buffer in memory)

### No tool count change — Total tools: **232** + **19 optional** (ElevenLabs) = **251 total** *(corrected to 230/249 in v2.9.1)*

---

## v2.8.1 — 2026-02-11

### Server: Browser Cache — Faster Startup, Less Overhead

- **Disk cache lifetime**: 24 hours → **7 days** — browser items rarely change, no need to rescan daily
- **Startup skip**: if a valid disk cache exists (<7 days old), the server loads it instantly and **skips the live Ableton rescan** entirely — eliminates the 15-30s background scan on every restart
- **No more in-session auto-refresh**: the 5-minute TTL that silently triggered a full browser rescan mid-session is removed — searches always return the cached data instantly
- **Manual refresh only**: call `refresh_browser_cache` when you actually add/remove packs or plugins; otherwise the cache just works
- Net effect: **faster server startup**, **no surprise rescans**, **less TCP traffic to Ableton**, fewer wasted Claude tool calls waiting on browser timeouts

### Remote Script Bug Fixes & Hardening (24 fixes across 9 handler files)

#### Repository Cleanup
- **fix**: Deleted duplicated nested `AbletonMCP_Remote_Script/AbletonMCP_Remote_Script/` directory — was causing maintenance drift with the canonical outer handlers

#### Dispatch & Session
- **fix**: `stop_arrangement_recording` dispatch passed `ctrl` as `stop_playback` — callers can now control `stop_playback` correctly
- **fix**: `set_groove_settings` — validate `groove_amount` is 0.0–1.0 before assigning
- **fix**: `set_tempo` — removed double-logging (validation logged error before raising, then outer except logged again)

#### Automation
- **fix**: `clear_track_automation` — coerce `start_time`/`end_time` to float at function start to prevent string comparison bugs

#### Arrangement
- **fix**: `duplicate_clip_to_arrangement` — clamp `time` to `max(0.0, float(time))` to reject negative offsets

#### Audio
- **fix**: `reverse_clip` — replaced broken `clip.sample` check (never existed on audio clips) with Simpler device detection via `class_name == 'OriginalSimpler'`
- **fix**: `freeze_track` — replaced fake `track.freeze = True` with `is_frozen`/`can_be_frozen` checks; returns structured response with message explaining LOM limitation (no longer raises `NotImplementedError`)
- **fix**: `unfreeze_track` — same pattern; returns structured response instead of raising

#### Browser
- **fix**: `load_browser_item` — check `item.is_loadable` before calling `load_item()` to prevent opaque API errors on folders/categories
- **fix**: `load_sample` — same `is_loadable` guard

#### Clips
- **fix**: `create_clip` — validate length is positive before calling API
- **fix**: `add_notes_to_clip` Strategy 3 — legacy `set_notes()` path now fetches and merges existing notes instead of overwriting them
- **fix**: `add_notes_to_clip` Strategy 3 — return value now reports count of notes *added* (consistent with Strategy 1 & 2), not total notes in clip
- **fix**: `set_clip_loop_points` — validate `loop_start < loop_end` upfront with descriptive `ValueError`
- **fix**: `set_clip_pitch` — validate pitch_coarse (-48..+48) and pitch_fine (-50..+50) bounds

#### Scenes
- **fix**: `set_scene_tempo` — validate tempo: accept 0 (clear override) or 20–999 BPM

#### Devices
- **fix**: `get_macro_values` / `set_macro_value` — use `visible_macro_count` for Live 12 (supports up to 16 macros, was hardcoded to 8)
- **fix**: `sliced_simpler_to_drum_rack` — suppress ImportError traceback chain with `from None`
- **fix**: `set_simpler_properties` — report `sample_missing: true` + `unapplied_sample_fields` when sample params are supplied but no sample is loaded

#### MIDI
- **fix**: `quantize_clip_notes` / `transpose_clip_notes` — handle immutable note objects in extended API path; falls through to legacy remove+set_notes on `AttributeError`
- **fix**: `add_notes_extended` — removed unused `e1`/`e2` exception variables (lint cleanup)
- **fix**: `get_notes_extended` / `remove_notes_extended` — switched from keyword to positional arguments (`from_pitch, pitch_span, from_time, time_span`) to avoid parameter-name mismatches across Live versions; silent `except` now logs via ctrl instead of swallowing errors

### No tool count change — Total tools: **232** + **19 optional** (ElevenLabs) = **251 total** *(corrected to 230/249 in v2.9.1)*

---

## v2.8.0 — 2026-02-11

### M4L Bridge v3.6.0 — 9 new M4L tools (bridge: 32 → 41 OSC commands)

#### Note Surgery by ID (3 tools — M4L-exclusive, Live 11+)
- `get_clip_notes_with_ids` — get all MIDI notes with stable note IDs for in-place editing
- `modify_clip_notes` — non-destructive in-place note editing by ID (velocity, pitch, timing, probability)
- `remove_clip_notes_by_id` — surgical note removal by ID (no range-based collateral)

#### Chain-Level Mixing (2 tools — M4L-exclusive)
- `get_chain_mixing` — read volume, pan, sends, mute, solo of a rack chain's mixer_device
- `set_chain_mixing` — set any combination of chain mixing properties (Drum Rack balancing, Instrument Rack mixing)

#### Device AB Comparison (1 tool — Live 12.3+)
- `device_ab_compare` — save/toggle/query AB preset comparison slots on any device

#### Clip Scrubbing (1 tool — M4L-exclusive)
- `clip_scrub` — quantized scrubbing within a clip (like mouse scrubbing, respects Global Quantization)

#### Split Stereo Panning (2 tools — M4L-exclusive)
- `get_split_stereo` — read left/right split stereo pan values
- `set_split_stereo` — set independent L/R panning for a track

### Total tools: 223 → **232** (+9) + **19 optional** (ElevenLabs) = **251 total** *(corrected to 230/249 in v2.9.1)*

---

## v2.7.1 — 2026-02-11

### M4L Bridge v3.3.0 — 5 new M4L tools (bridge: 29 → 32 OSC commands)

#### App Version Detection (1 tool)
- `get_ableton_version` — read Ableton Live major/minor/bugfix version via M4L LiveAPI. Enables version-gating for features like AB comparison (Live 12.3+)

#### Automation State Introspection (1 tool)
- `get_automation_states` — read automation_state (none/active/overridden) for all parameters of a device. M4L-exclusive — no TCP equivalent. Detects overridden automation before modifying parameters

#### Chain Discovery via M4L (3 tools — wired existing orphaned JS handlers)
- `discover_chains_m4l` — discover rack chains with enhanced detail: return chains, drum pad in_note/out_note/choke_group
- `get_chain_device_params_m4l` — discover ALL parameters (including hidden) of a device inside a rack chain
- `set_chain_device_param_m4l` — set any parameter on a device inside a rack chain

#### Enhanced Chain Discovery
- **Return chains**: `discoverChainsAtPath()` now enumerates return_chains (Rack-level sends) with their devices
- **Drum pad properties**: Added in_note, out_note, choke_group to drum pad enumeration

### Total tools: 216 → **221** (+5) + **19 optional** (ElevenLabs) = **240 total**

---

## v2.7.0 — 2026-02-10

### New Features: 19 new tools + 5 extended existing tools

Cross-referenced the Live Object Model (Max 9), Python API stubs, and Live 12.4 release notes to identify and implement all missing API coverage.

#### Scale & Root Note — Harmonic Awareness (2 tools)
- `get_song_scale` — read root_note (0-11), scale_name, scale_mode, scale_intervals
- `set_song_scale` — set root_note, scale_name, scale_mode for harmonically-correct AI composition

#### Punch In/Out Recording (extended existing tools)
- `set_punch_recording` — control punch_in, punch_out, count_in_duration
- Extended `get_song_transport` with punch_in, punch_out, count_in_duration, is_counting_in

#### Clip Playing Status (1 new tool + extended existing)
- `get_playing_clips` — scan all tracks for currently playing/triggered clips with positions
- Extended `get_clip_info` with is_triggered, playing_position, launch_mode, velocity_amount, legato

#### Selection State (1 tool)
- `get_selection_state` — read currently selected track, scene, clip, device, parameter, draw_mode, follow_song

#### Additional Song Properties (extended existing)
- Extended `get_song_settings` with tempo_follower_enabled, exclusive_arm, exclusive_solo, session_automation_record, song_length
- Extended `set_song_settings` with session_automation_record

#### Link Sync Status (2 tools)
- `get_link_status` — read link_enabled, start_stop_sync_enabled
- `set_link_enabled` — enable/disable Ableton Link and start/stop sync

#### Track Group Info (extended existing)
- Extended `get_track_info` with is_grouped, group_track_index, is_visible, is_showing_chains, can_show_chains, playing_slot_index, fired_slot_index

#### Application View Management (3 tools)
- `get_view_state` — check visibility of all views (Browser, Session, Arranger, Detail, etc.)
- `set_view` — show/hide/focus views, toggle browser
- `zoom_scroll_view` — zoom/scroll any view with direction and modifier support

#### Warp Markers (4 tools)
- `get_warp_markers` — read all warp markers (beat_time + sample_time) for a clip
- `add_warp_marker` — add warp marker at beat_time/sample_time position
- `move_warp_marker` — move existing warp marker by index
- `remove_warp_marker` — remove warp marker by index

#### Tuning System (1 tool)
- `get_tuning_system` — read microtonal tuning: name, pseudo_octave_in_cents, reference_pitch, note_tunings

#### Insert Device by Name (1 tool, Live 12.3+)
- `insert_device_by_name` — insert native Live devices by name at a position in device chain (faster than browser-based loading)

#### Looper Device Control (1 tool)
- `control_looper` — specialized Looper device control: record, overdub, play, stop, clear, undo, double_speed, half_speed, double_length, half_length, export to clip slot

#### Take Lanes / Comping (2 tools)
- `get_take_lanes` — read all take lanes and their clips for arrangement comping
- `create_take_lane` — create new take lane on a track

### Fixes
- **fix**: `set_punch_recording` — `count_in_duration` is read-only in Remote Script API (Python stubs say "Get" not "Get/Set"). Wrapped in try/except so `punch_in`/`punch_out` still work; returns warning note if count_in_duration fails
- **fix**: `get_tuning_system` — crashed on `ts.name` when no custom tuning active (default 12-TET returns uninitialized object). Now all properties individually guarded with sensible defaults ("Equal Temperament", 1200.0 cents). Added `lowest_note`/`highest_note` from LOM

### Total tools: 197 → **216** (+19) + **19 optional** (ElevenLabs) = **235 total**

---

## v2.6.1 — 2026-02-10

### Fixes
- **fix**: Spectrum chain requires `abs~` after each `fffb~` outlet — raw bipolar audio from `fffb~` gave negative/meaningless `snapshot~` values
- **fix**: Auto-derive RMS/peak from spectrum when `peakamp~` chain not connected — `spectrum_data()` now computes RMS (root-mean-square of band amplitudes) and peak (max band) as fallback
- **fix**: Value-based MSP data detection replaces fragile timestamp comparison — checks if any RMS/peak/spectrum values are nonzero instead of `last_update > startTime`
- **fix**: Increased cross-track wait time defaults (300–2000ms clamp, default 500ms) — was 150–1000ms/250ms, too short for reliable MSP capture
- **fix**: Removed duplicate `get_cue_points` / `get_groove_pool` tool registrations in server.py — were defined twice (Phase 7/8 M4L + Remote Script TCP), causing warnings
- **fix**: Added diagnostic logging in `_crossTrackCapture` for MSP data troubleshooting

### Documentation
- M4L Device README: updated spectrum chain diagram to include `abs~` after each `fffb~` outlet
- M4L Device README: marked `peakamp~` audio chain as optional (auto-derived from spectrum)
- M4L Device README: added troubleshooting for negative spectrum, zero RMS/peak, cross-track zeros
- Updated `analyze_cross_track_audio` docstring to note `abs~` requirement

### No tool count change — Total tools: **199** + **19 optional** (ElevenLabs) = **218 total**

---

## v2.6.0 — 2026-02-10

### New: Cross-Track MSP Audio Analysis via Send Routing (1 tool, requires M4L)

#### `analyze_cross_track_audio` — Real MSP analysis from any track
- Place the M4L Audio Effect device on a **return track** (e.g. Return A)
- Call `analyze_cross_track_audio(track_index=N)` to analyze any track's audio
- The bridge temporarily routes audio from track N → the return track via Ableton's send system
- Captures real MSP data: RMS (left/right), peak (left/right), 8-band spectrum (fffb~)
- **Non-destructive**: source track's main output continues to master normally
- Send level is **always restored** after capture (even on error)
- Configurable capture window: `wait_ms` (150-1000ms, default 250ms)
- Returns: RMS, peak, 8-band spectrum with labels (Sub/Bass/Low-Mid/Mid/Upper-Mid/Presence/Brilliance/Air), dominant band, spectral centroid, source+return meters

#### M4L Bridge v3.2.0
- New OSC command: `/analyze_cross_track` (track_index, wait_ms, request_id)
- New helper: `_findDeviceReturnTrackIndex()` — discovers which return track the device is on via LiveAPI id comparison
- New deferred callback: `_crossTrackCapture()` — runs after wait_ms via `Task.schedule()`
- Concurrency guard: `_crossTrackState` prevents overlapping cross-track analyses
- Safety: send level restored in both success and error paths
- Total bridge commands: 28 → **29**

### Total tools: 198 → **199** (+1 M4L) + **19 optional** (ElevenLabs) = **218 total**

---

## v2.5.0 — 2026-02-10

### M4L Bridge v3.1.0: Audio Effect + Cross-Track Analysis

#### Device Type: MIDI Effect → Audio Effect
- The M4L bridge device is now an **Audio Effect** (was MIDI Effect)
- `plugin~` in a MIDI Effect receives no audio — it sits before the instrument in the signal chain
- As an Audio Effect, `plugin~` taps post-instrument audio, enabling real-time RMS/peak and spectral analysis
- All 28 OSC commands, LiveAPI access, and observers work identically in both device types

#### Cross-Track Audio Metering
- `analyze_track_audio` now accepts an optional `track_index` parameter
  - `-1` (default): device's own track (backward compatible)
  - `0, 1, 2, ...`: read meters from any specific track
  - `-2`: read master track meters
- Reads LOM `output_meter_left`/`output_meter_right` for any track by path — no need to load the bridge on every track
- MSP data (RMS/peak) still comes from the device's own track only

#### 8-Band Spectral Analysis (fffb~)
- Max patch now uses `plugin~` → `fffb~ 8` → 8× `snapshot~ 100` → `pack` → `prepend spectrum_data` → `[js]`
- `fffb~` splits audio into 8 perceptually useful frequency bands
- Simpler and more reliable than raw FFT (`fft~` → `cartopol~`) — no subpatch needed
- `analyze_track_spectrum` returns bin magnitudes, dominant band, and spectral centroid

#### Audio Analysis Chain (peakamp~)
- Max patch uses `plugin~` → `peakamp~ 100` → `snapshot~ 200` → `pack` → `prepend audio_data` → `[js]`
- Two channels (L/R) for stereo RMS/peak measurement
- Audio passthrough via `plugin~` → `plugout~` ensures the device doesn't mute the track

#### Updated Documentation
- M4L Device README rewritten for Audio Effect setup (step-by-step wiring for all chains)
- Added troubleshooting for "spectrum data all zeros" (MIDI Effect vs Audio Effect)
- OSC reference updated: `/analyze_audio` now takes `track_index` integer parameter

---

## v2.4.0 — 2026-02-10

### New: M4L Bridge v3.0.0 — 5 New Capability Phases (10 tools)

#### Phase 7: Cue Points & Locators (2 tools, requires M4L)
- `get_cue_points` — list all arrangement locators with names and beat positions
- `jump_to_cue_point` — move playback position to a specific locator
- Accesses `live_set cue_points` — not available via the Python Remote Script

#### Phase 8: Groove Pool Access (2 tools, requires M4L)
- `get_groove_pool` — list all grooves with base, timing, velocity, random, quantize properties
- `set_groove_properties` — modify groove parameters (base64-encoded JSON payload)
- Accesses `live_set groove_pool grooves` via LOM

#### Phase 6: Event-Driven Monitoring (3 tools, requires M4L)
- `observe_property` — start watching a LOM property for changes via `live.observer` (~10ms latency vs 100ms+ TCP polling)
- `stop_observing` — stop watching a property
- `get_property_changes` — retrieve accumulated change events (ring buffer, clears after read)
- Useful for: `is_playing`, `tempo`, `current_song_time`, track `output_meter_level`

#### Phase 9: Undo-Clean Parameter Control (1 tool, requires M4L)
- `set_parameter_clean` — set a device parameter via M4L bridge with minimal undo impact
- Routes through M4L's LiveAPI instead of the TCP Remote Script

#### Phase 5: Audio Analysis (2 tools, requires M4L)
- `analyze_track_audio` — LOM meter levels (left/right) + MSP RMS/peak data (if Max patch configured)
- `analyze_track_spectrum` — FFT spectral data: bins, dominant frequency, spectral centroid (requires Max patch fft~ setup)
- Bridge accepts `audio_data` and `spectrum_data` messages from Max patch MSP objects

### M4L Bridge v3.0.0
- 10 new OSC commands: `/get_cue_points`, `/jump_to_cue_point`, `/get_groove_pool`, `/set_groove_properties`, `/observe_property`, `/stop_observing`, `/get_observed_changes`, `/set_param_clean`, `/analyze_audio`, `/analyze_spectrum`
- Observer system: ring buffer (200 entries per observer) with `LiveAPI` callback pattern
- Audio analysis data store: accepts `audio_data` and `spectrum_data` messages from Max patch
- Total bridge commands: 18 → **28**

### Total tools: 188 → **198** (+10 M4L) + **19 optional** (ElevenLabs) = **217 total**

---

## v2.3.0 — 2026-02-10

### New: UDP Real-Time Parameter Channel (2 tools)
- `realtime_set_parameter` — set a device parameter via UDP for low-latency, fire-and-forget control (no response confirmation). Ideal for filter sweeps, volume ramps, and real-time automation at 50+ Hz.
- `realtime_batch_set_parameters` — set multiple device parameters at once via UDP (fire-and-forget). Same low-latency semantics.
- **Remote Script**: Added UDP listener on port 9882 alongside existing TCP:9877. UDP commands reuse existing `handlers.devices.set_device_parameter()` and `set_device_parameters_batch()` with main-thread safety via `schedule_message`.

### New: ElevenLabs Voice & SFX Integration (19 tools, separate MCP server)
- Separate optional MCP server (`elevenlabs_mcp/`) for AI voice generation via the ElevenLabs API
- `text_to_speech` — generate speech with customizable voice, stability, speed
- `text_to_sound_effects` — generate sound effects from text description (0.5-5s)
- `speech_to_text` — transcribe audio with optional speaker diarization
- `speech_to_speech` — convert speech to another voice
- `text_to_voice` / `create_voice_from_preview` — design and save AI voices
- `voice_clone` — clone a voice from audio files
- `isolate_audio` — isolate vocals or background stems
- `search_voices` / `get_voice` / `search_voice_library` — browse and search voices
- `check_subscription` — check ElevenLabs API usage and limits
- `play_audio` — play generated audio locally
- `create_agent` / `list_agents` / `get_agent` / `add_knowledge_base_to_agent` — conversational AI agents
- `make_outbound_call` / `list_phone_numbers` — voice calls via agents
- Audio saves to `~/Documents/Ableton/User Library/eleven_labs_audio/` — import into Ableton via `query:UserLibrary#eleven_labs_audio:filename.mp3`
- Requires `ELEVENLABS_API_KEY` environment variable; install with `pip install -e ".[elevenlabs]"`

### Total tools: 186 → **188** (+2 UDP) + **19 optional** (ElevenLabs)

---

## v2.2.0 — 2026-02-10

### New: Track Metering & Crossfade (3 tools)
- `get_track_meters` — read output meter levels (left/right), playing slot index, and fired slot index for one or all tracks
- `set_track_fold` — collapse/expand group tracks (checks `is_foldable` first)
- `set_crossfade_assign` — set A/B crossfade assignment per track (0=NONE, 1=A, 2=B)

### New: Clip Region & Grid (3 tools)
- `duplicate_clip_region` — duplicate a region of notes within a MIDI clip with optional pitch transposition
- `move_clip_playing_pos` — jump to a position within a currently playing clip
- `set_clip_grid` — set clip view grid quantization and triplet mode

### New: Simpler & Sample (TCP) (4 tools)
- `get_simpler_properties` — read Simpler device state: playback mode, voices, retrigger, slicing mode, plus full sample info (markers, gain, warp mode, warp params, slicing config, slices, file path)
- `set_simpler_properties` — set Simpler device and sample properties (21 parameters: playback mode, voices, sample markers, gain, warp mode, 8 warp-mode-specific params, slicing config)
- `simpler_sample_action` — perform sample operations: reverse, crop, warp_as (beats), warp_double, warp_half
- `manage_sample_slices` — manage Simpler slices: insert, move, remove, clear, reset

### New: Browser Preview (1 tool)
- `preview_browser_item` — audition a browser item by URI, or stop the current preview

### Total tools: 175 → **186** (+11 new)

---

## v2.1.0 — 2026-02-10

### New: Song Settings & Navigation (4 tools)
- `get_song_settings` — read time signature, swing amount, clip trigger quantization, MIDI recording quantization, arrangement overdub, back to arranger, follow song, draw mode
- `set_song_settings` — set any combination of the above (time signature numerator/denominator, swing 0.0-1.0, quantization values, boolean flags)
- `trigger_session_record` — start a new session recording, optionally with a fixed bar length
- `navigate_playback` — jump_by (relative position jump), scrub_by (jump without stopping playback), play_selection (play the current arrangement selection)

### New: View & Selection (3 tools)
- `select_scene` — programmatically select a scene by index in Session view
- `select_track` — programmatically select a track (regular, return, or master)
- `set_detail_clip` — show a specific clip in Live's Detail view (bottom panel)

### New: Transmute Device Controls (2 tools) (Known broken — Ableton API limitation)
- `get_transmute_properties` — read frequency dial mode, pitch mode, mod mode, mono/poly mode, MIDI gate mode (each with available options list), polyphony, and pitch bend range
- `set_transmute_properties` — set any combination of Transmute mode indices, polyphony, and pitch bend range

### Total tools: 166 → **175** (+9 new)

---

## v2.0.2 — 2026-02-10

### New: Session & Transport (9 tools)
- `undo` / `redo` — undo/redo the last action (with `can_undo`/`can_redo` safety checks)
- `continue_playing` — resume playback from current position (instead of from start)
- `re_enable_automation` — re-enable all manually overridden automation
- `get_cue_points` — get all arrangement cue point markers (name + time)
- `set_or_delete_cue` — toggle a cue point at the current playback position
- `jump_to_cue` — jump to the next or previous cue point
- `get_groove_pool` — read global groove amount and all groove parameters
- `set_groove_settings` — set global groove amount or individual groove timing/quantization/random/velocity

### New: Track Tools (4 tools)
- `get_track_routing` — get input/output routing and available routing options
- `set_track_routing` — set input/output routing by display name (enables side-chain, resampling)
- `set_track_monitoring` — set monitoring state (IN / AUTO / OFF)
- `create_midi_track_with_simpler` — load audio clip into Simpler on a new MIDI track (Live 12+)

### New: Clip Tools (5 tools)
- `set_clip_pitch` — set pitch transposition (coarse semitones + fine cents) for audio clips
- `set_clip_launch_mode` — set launch mode (trigger / gate / toggle / repeat)
- `set_clip_launch_quantization` — per-clip launch quantization override (none through 1/32, or global)
- `set_clip_legato` — enable/disable legato mode (seamless clip transitions)
- `audio_to_midi` — convert audio to MIDI using drums/harmony/melody algorithms (Live 12+)

### New: Scene Tools (1 tool)
- `set_scene_tempo` — set or clear per-scene tempo override (0 clears, 20-999 sets)

### New: Device Tools (12 tools)
- `get_drum_pads` — read all drum pad info (note, name, mute, solo) from a Drum Rack
- `set_drum_pad` — mute/solo individual drum pads by MIDI note number
- `copy_drum_pad` — copy pad contents from one note to another
- `get_rack_variations` — read macro variation count, selected index, mapping status
- `rack_variation_action` — store/recall/delete macro variations, randomize macros
- `sliced_simpler_to_drum_rack` — convert sliced Simpler to Drum Rack (Live 12+)
- `get_compressor_sidechain` — read Compressor side-chain routing and available sources
- `set_compressor_sidechain` — set Compressor side-chain source by display name
- `get_eq8_properties` — read EQ Eight edit mode (A/B), global mode (Stereo/L-R/M-S), oversample, selected band
- `set_eq8_properties` — set EQ Eight edit mode, global mode, oversample, selected band
- `get_hybrid_reverb_ir` — read Hybrid Reverb IR categories, files, selection, and time shaping
- `set_hybrid_reverb_ir` — set Hybrid Reverb IR category, file, attack/decay/size/time shaping

### Remote Script Fixes
- **`set_scene_tempo`**: Simplified to use `scene.tempo` API directly — 0 clears, 20-999 sets
- **Variable cleanup**: `l` → `length_val` in `set_song_loop`; added `pos` in `set_loop_end`; removed double-logging in 3 session handlers
- **`stop_arrangement_recording`**: Added optional `stop_playback` parameter
- **`set_compressor_sidechain`**: Rewrote to use DeviceIO path (`device.input_routings[0]`) — CompressorDevice properties are read-only, DeviceIO `routing_type`/`routing_channel` are writable
- **`_get_hybrid_reverb_device`**: Fixed class name check — Ableton reports `"Hybrid"` not `"HybridReverb"`

### M4L Bridge Fixes
- **Response interleaving**: Small responses now queue behind active chunked sends
- **`_batchProcessNextChunk`**: Wrapped in try/catch matching sibling functions
- **ES5 compat**: Reverted `let` to `var` in case "move" for Max's JS engine

### Total tools: 138 → **166** (+31 new, -3 already removed in v2.0.0)

---

## v2.0.1 — 2026-02-09

### Remote Script Fixes
- **Thread safety**: Read-only commands now marshaled onto main thread via `schedule_message` (was running on socket thread, risking LOM access violations)
- **Automation clamping**: Uses `parameter.min`/`parameter.max` instead of hardcoded 0.0–1.0 range
- **Automation sampling**: Fixed off-by-one — `get_clip_automation` now returns exactly 64 points (was 65)
- **Automation point reduction**: Server-side 3-stage pipeline (sort+dedup, collinear removal, RDP) enforces max 20 points per automation write — prevents cluttered envelopes
- **MIDI note API**: `add_notes_to_clip` uses Live 12 `MidiNoteSpecification` API with fallback chain (dict-based → legacy `set_notes`)
- **Loop validation**: `set_loop_end` rejects end ≤ start; `set_loop_length` and `set_song_loop` reject length ≤ 0
- **Time range validation**: `clear_track_automation` rejects end_time ≤ start_time
- **`group_tracks`**: Now honestly reports `grouped: false` with reason (Remote Script API limitation) instead of `grouped: true`
- **Dead code removed**: Unused `track` variable in `create_track_automation`
- **Audio helper extracted**: `_get_audio_clip()` replaces duplicated validation in 5 functions

### M4L Bridge Fixes
- **Concurrency guards**: `_discoverState`, `_batchState`, and `_responseSendState` now reject concurrent operations with error messages instead of silently corrupting state
- **Error recovery**: `_discoverNextChunk` and `_sendNextResponsePiece` wrapped in try/catch — cleans up global state and unblocks future operations on failure
- **Response queue**: Large response sends queue behind active sends and drain automatically via `_drainResponseQueue()`
- **Simpler slice "move"**: Added missing `case "move"` to `handleSimplerSlice` with 6-arg parsing
- **Base64 decode boundary**: Fixed `<=` to `<` comparisons preventing off-by-one in `_base64decode`

### Grid Notation Fixes
- **Flat accidental parsing**: Fixed `Bb`, `Eb` etc. — was uppercasing the entire note name including accidental
- **Pedal hi-hat label**: Pitch 44 changed from `'HC'` to `'HP'` (was colliding with closed hi-hat)
- **Mid tom label**: Pitch 47 changed from `'LT'` to `'MT'` (was mislabeled as low tom)

### No tool count change — Total tools: **138** (unchanged)

---

## v2.0.0 — 2026-02-09

### New: Device Chain Navigation (3 tools, requires M4L)
- `discover_rack_chains` — discover chains, nested devices, and drum pads inside Instrument/Audio Effect/Drum Racks
- `get_chain_device_parameters` — read all parameters of a device nested inside a rack chain
- `set_chain_device_parameter` — set a parameter on a device nested inside a rack chain
- LOM paths: `live_set tracks T devices D chains C devices CD`

### New: Simpler / Sample Deep Access (3 tools, requires M4L)
- `get_simpler_info` — get Simpler device state: playback mode, sample file path, markers, warp settings, slices, warp-mode-specific properties
- `set_simpler_sample_properties` — set sample start/end markers, warping, warp mode, gain, slicing sensitivity
- `simpler_manage_slices` — manage slices: insert at position, remove at position, clear all, reset to auto-detected
- LOM paths: `live_set tracks T devices D sample`

### New: Wavetable Modulation Matrix (3 tools, requires M4L)
- `get_wavetable_info` — get Wavetable device state: oscillator wavetable categories/indices, modulation matrix with active modulations, voice/unison/filter settings
- `set_wavetable_modulation` — set modulation amount in Wavetable's mod matrix (sources: Env2, Env3, LFO1, LFO2)
- `set_wavetable_properties` — set oscillator wavetable category/index, effect modes. Voice/unison/filter properties are read-only (Ableton API limitation)

### M4L Bridge v2.0.0
- 9 new OSC commands: `/discover_chains`, `/get_chain_device_params`, `/set_chain_device_param`, `/get_simpler_info`, `/set_simpler_sample_props`, `/simpler_slice`, `/get_wavetable_info`, `/set_wavetable_modulation`, `/set_wavetable_props`
- Generic LOM helper: `discoverParamsAtPath()` enables parameter discovery at arbitrary LOM paths (used by chain device params)
- LiveAPI cursor reuse: `discoverChainsAtPath()` uses `LiveAPI.goto()` to reuse 3 cursor objects instead of creating ~193 per call — prevents Max `[js]` memory exhaustion on large drum racks
- OSC packet builders: All 9 new commands have corresponding builders in `M4LConnection._build_osc_packet()`

### TCP Port: Snapshot / Restore / Morph / Macros
- `snapshot_device_state` — ported from M4L `discover_params` to TCP `get_device_parameters`. No longer requires M4L bridge.
- `restore_device_snapshot` — ported from `_m4l_batch_set_params()` to `_tcp_batch_restore_params()` using name-based parameters. No M4L needed.
- `snapshot_all_devices` — ported to TCP. Snapshots all devices across tracks without M4L.
- `restore_group_snapshot` — ported to TCP.
- `morph_between_snapshots` — ported to TCP. Now uses name-based parameter matching instead of index-based.
- `set_macro_value` — ported to TCP. Auto-looks up parameter names from device if not cached.
- `generate_preset` — fully rewritten to use TCP. No longer calls M4L `discover_params` (which caused timeouts and crashes).
- New helper: `_tcp_batch_restore_params()` — restores device parameters via TCP `set_device_parameters_batch` using name-based params.

### Removed Redundant Tools (-3)
- `arm_track` — use `set_track_arm(arm=True)` instead
- `disarm_track` — use `set_track_arm(arm=False)` instead
- `get_return_tracks_info` — use `get_return_tracks` instead

### Bug Fixes & Improvements
- **Fixed `set_wavetable_properties` crash**: removed post-set `get()` read-back verification that crashed Ableton. Now uses fire-and-forget `set()` for oscillator properties via M4L
- **Fixed `set_device_hidden_parameter` crash**: removed post-set `paramApi.get("value")` readback in `setHiddenParam()` — same crash pattern as the wavetable fix. Now reports clamped value instead of reading back
- **Confirmed Wavetable voice properties read-only**: `unison_mode`, `unison_voice_count`, `filter_routing`, `mono_poly`, `poly_voices` are NOT exposed as DeviceParameters (verified against full 93-parameter list). Neither M4L `LiveAPI.set()` nor TCP `set_device_parameter` can write them — hard Ableton API limitation. `set_wavetable_properties` now returns a clear error message for these
- **Fixed `discover_rack_chains` nested rack support**: added optional `chain_path` parameter to target devices inside chains (e.g. `"chains 0 devices 0"` for nested racks)
- **Fixed `discover_rack_chains` crash on large drum racks**: refactored `discoverChainsAtPath` to reuse LiveAPI objects via `goto()` instead of creating ~193 new objects per call. Now uses 3 cursor objects total, preventing Max `[js]` memory exhaustion
- **Fixed `discover_device_params` crash on large devices** (e.g. Wavetable with 93 params): two root causes found and fixed:
  - Synchronous LiveAPI overload: >~210 `get()` calls in a single `[js]` execution crashes Ableton. Fixed by chunked async discovery (4 params/chunk with 50ms `Task.schedule()` delays)
  - Response size through outlet/udpsend: >~8KB base64 via Max `outlet()` crashes Ableton (symbol size limit + OSC routing issues with `+` and `/` characters in standard base64). Fixed by chunked response protocol (Rev 4): JSON is split into 2KB pieces, each base64-encoded independently with URL-safe conversion (`+`→`-`, `/`→`_`), wrapped in a chunk envelope, and sent via deferred `Task.schedule()`. Python server detects chunk metadata (`_c`/`_t` keys), buffers all pieces, decodes each, and reassembles the full JSON
- **Chunked response protocol**: M4L bridge splits large responses into multiple ~3.6KB UDP packets. Python server reassembles automatically. Small responses sent as-is (backward compatible). Key safety: never creates the full base64 string in memory, uses `.replace()` for O(n) URL-safe conversion, defers all `outlet()` calls via `Task.schedule()`
- **Fixed `set_chain_device_parameter` crash**: removed post-set `paramApi.get("value")` readback in `handleSetChainDeviceParam()` — same crash pattern as wavetable and hidden param fixes
- **Fixed `batch_set_hidden_parameters` LiveAPI exhaustion**: refactored `_batchProcessNextChunk()` to reuse a single cursor via `goto()` instead of creating new LiveAPI per parameter (93 objects → 1)
- **Fixed Remote Script crash on client disconnect**: wrapped `client.sendall()` response send in try/except to handle broken connections cleanly instead of propagating the error
- **Fixed `grid_to_clip` silent failures**: `except Exception: pass` replaced with proper error returns
- **Fixed `generate_preset` device targeting**: improved docstring guidance to target synth, not effects
- **Reduced bruteforce resolver logging**: removed per-iteration logging from `devices.py` — only MATCH and ERROR logged now
- **Improved documentation**: Moved automation and extended note features from Limitations to Features — these are capabilities, not limitations. Fixed `create_clip_automation` docstring that incorrectly said "arrangement automation is not supported"
- Total tools: 132 → **138** (+9 new, -3 removed)

---

## v1.9.0 — 2026-02-09

### New: ASCII Grid Notation (2 tools)
- `clip_to_grid` — read a MIDI clip as ASCII grid notation (auto-detects drum vs melodic)
- `grid_to_clip` — write ASCII grid notation to a MIDI clip (creates clip if needed)

### New: Transport & Recording Controls (10 tools)
- `get_loop_info` — get loop bracket start, end, length, and current playback time
- `get_recording_status` — get armed tracks, record mode, and overdub state
- `set_loop_start` — set loop start position in beats
- `set_loop_end` — set loop end position in beats
- `set_loop_length` — set loop length in beats (adjusts end relative to start)
- `set_playback_position` — move the playhead to a specific beat position
- `set_arrangement_overdub` — enable or disable arrangement overdub mode
- `start_arrangement_recording` — start arrangement recording
- `stop_arrangement_recording` — stop arrangement recording
- `set_metronome` — enable or disable the metronome
- `tap_tempo` — tap tempo (call repeatedly to set tempo by tapping)

### New: Bulk Track Queries (2 tools)
- `get_all_tracks_info` — get information about all tracks at once (bulk query)
- `get_return_tracks_info` — get detailed info about all return tracks (bulk query)

### New: Track Management (5 tools)
- `create_return_track` — create a new return track
- `set_track_color` — set the color of a track (0-69, Ableton's palette)
- `arm_track` — arm a track for recording
- `disarm_track` — disarm a track (disable recording)
- `group_tracks` — group multiple tracks together

### New: Audio Clip Tools (6 tools)
- `get_audio_clip_info` — get audio clip details (warp mode, gain, file path)
- `analyze_audio_clip` — comprehensive audio clip analysis (tempo, warp, sample properties, frequency hints)
- `set_warp_mode` — set warp mode (beats, tones, texture, re_pitch, complex, complex_pro)
- `set_clip_warp` — enable or disable warping for an audio clip
- `reverse_clip` — reverse an audio clip
- `freeze_track` / `unfreeze_track` — freeze/unfreeze tracks to reduce CPU load

### New: Arrangement Editing (4 tools)
- `get_arrangement_clips` — get all clips in arrangement view for a track
- `delete_time` — delete a section of time from the arrangement (shifts everything after)
- `duplicate_time` — duplicate a section of time in the arrangement
- `insert_silence` — insert silence at a position (shifts everything after)

### New: Arrangement Automation (2 tools)
- `create_track_automation` — create automation for a track parameter (arrangement-level)
- `clear_track_automation` — clear automation for a parameter in a time range (arrangement-level)

### New: MIDI & Performance Tools (3 tools)
- `capture_midi` — capture recently played MIDI notes (Live 11+)
- `apply_groove` — apply groove to a MIDI clip
- `get_macro_values` — get current macro knob values for an Instrument Rack

### New: Cached Browser Tree (1 tool)
- `refresh_browser_cache` — force a full re-scan of Ableton's browser tree
- `search_browser` now uses an in-memory cache instead of querying Ableton directly — **instant results, no more timeouts**
- `get_browser_tree` returns cached data with URIs, so Claude can load instruments in fewer steps
- **Background warmup**: on startup, the server scans all 5 browser categories (Instruments, Sounds, Drums, Audio Effects, MIDI Effects) using a BFS walker up to **depth 4** — finds instruments AND their individual presets (e.g. `sounds/Operator/Bass/FM Bass`)
- Cache holds up to **5000 items**, auto-refreshes every **5 minutes**
- Fixes: `search_browser` no longer times out; Claude gets correct URIs instead of guessing wrong ones

### Performance & Code Streamlining
- **BFS queue fix**: Browser cache population now uses `deque.popleft()` (O(1)) instead of `list.pop(0)` (O(n))
- **Eliminated duplicate cache**: Removed unused per-category dict; added `_browser_cache_by_category` index for O(1) filtered search
- **Module-level `_CATEGORY_DISPLAY` constant**: No longer rebuilt on every `search_browser`/`get_browser_tree` call
- **Redundant double-lock removed**: `_get_browser_cache()` no longer acquires the lock twice on cache miss
- **Smarter cache warmup**: Polls for Ableton connection every 0.5s instead of blind 3s sleep — starts scanning as soon as ready
- **UDP drain bounded**: Socket drain loops capped at 100 iterations (was unbounded `while True`)
- **Hot-path logging → DEBUG**: Per-command INFO logs (send, receive, status) downgraded to DEBUG — eliminates 3 I/O calls per tool invocation
- **Lazy `%s` formatting**: ~25 logger calls switched from f-strings to `%s` style — skips string construction when log level is filtered
- **Cheaper dashboard log handler**: Stores lightweight tuples, defers timestamp formatting to when dashboard is actually viewed
- **Dashboard status build**: `top_tools` computed inside the lock — no more full dict copy on every 3s refresh
- **Fixed stale values**: Dashboard `tool_count` and comment updated from 81 → 131
- **Clean import**: `import collections` → `from collections import deque`

### Improvements
- Package renamed to `ableton-mcp-stable` for stable release channel
- Fixed server version detection (`importlib.metadata` now uses correct package name)
- Total tools: 94 -> **131** (+37 new tools)

---

## v1.8.2 — 2026-02-09

### Bug Fix: `batch_set_hidden_parameters` crash
- **Fixed**: `batch_set_hidden_parameters` was crashing Ableton when setting more than 2 parameters. The root cause was Max's OSC/UDP handling corrupting long base64-encoded payloads.
- **Server fix** (`server.py`): Replaced the single base64-encoded batch OSC message with sequential individual `set_hidden_param` UDP calls via a new `_m4l_batch_set_params()` helper. Includes 50ms inter-param delay for large batches to prevent overloading Ableton.
- **M4L fix** (`m4l_bridge.js`): Added chunked processing (6 params/chunk, 50ms delay) using Max's `Task` scheduler, URL-safe base64 decode support, and debug logging.
- **Safety**: Both server and M4L bridge now filter out parameter index 0 ("Device On") to prevent accidentally disabling devices during batch operations.
- **Dynamic timeout**: M4L `send_command` timeout now scales with parameter count (~150ms per param, minimum 10s) instead of a fixed 5s.
- Updated all internal callers: `restore_device_snapshot`, `restore_group_snapshot`, `morph_between_snapshots`, `set_macro_value`.
- Total tools: **94** (unchanged)

---

## v1.8.1 — 2026-02-09

### Repository Cleanup & Documentation
- Removed stale development files: `Ideas.txt`, `todo.txt`, `lastlog.txt`, `WhatItCanDoAndWhatItCant.txt`, `Installing process.txt`, `Latest bugfix.txt`
- Added `installation_process.txt` — comprehensive step-by-step installation guide covering Windows, macOS, Claude Desktop, Cursor, Smithery, and source installs
- Added `requirements.txt` — explicit dependency listing for pip-based installs
- Updated `M4Lfunctions.txt` — expanded M4L bridge capabilities documentation with practical examples
- Normalized line endings across `server.py`, `__init__.py`, and `README.md`

### No Code Changes
- `MCP_Server/server.py` — identical functionality to v1.8.0
- `AbletonMCP_Remote_Script/__init__.py` — identical functionality to v1.8.0
- Total tools: **94** (unchanged)

---

## v1.8.0 — 2026-02-09

### New: Arrangement View Workflow
- `get_song_transport` — get arrangement state (playhead, tempo, time signature, loop bracket, record mode, song length)
- `set_song_time` — set arrangement playhead position (in beats)
- `set_song_loop` — control arrangement loop bracket (enable/disable, set start/length)
- `duplicate_clip_to_arrangement` — copy session clip to arrangement timeline at beat position (Live 11+)

### New: Advanced Clip Operations
- `crop_clip` — trim clip to its loop region, discarding content outside
- `duplicate_clip_loop` — double the loop content (e.g. 4 bars -> 8 bars with content repeated)
- `set_clip_start_end` — control playback start/end markers without modifying notes

### New: Advanced MIDI Note Editing (Live 11+)
- `add_notes_extended` — add notes with probability, velocity_deviation, release_velocity
- `get_notes_extended` — get notes with extended properties
- `remove_notes_range` — selectively remove notes by time and pitch range

### New: Automation Reading & Editing
- `get_clip_automation` — read existing envelope data by sampling 64 points across clip
- `clear_clip_automation` — remove automation for a specific parameter
- `list_clip_automated_parameters` — discover all automated parameters in a clip

### Improvements
- Automation is no longer write-only; now supports reading, clearing, and discovering automated parameters
- Graceful fallback to legacy APIs on older Live versions
- Total tools: 81 -> **94** (+13 new tools)

---

## v1.7.1 — 2026-02-09

### Bug Fixes
- Fixed log handler: timestamp field now only contains timestamp (was duplicating full formatted line in log viewer)

### Improvements
- Added status banner to web dashboard: green (all connected), yellow (Ableton only), red (disconnected)

---

## v1.7.0 — 2026-02-09

### Maintenance
- Version bump to bypass uvx wheel cache (uvx was caching the first v1.6.0 wheel, preventing M4L auto-connect fixes from being picked up)
- No new features

---

## v1.6.0 — 2026-02-09

### New: Layer 0 Core Primitives
- `batch_set_hidden_parameters` — set multiple device params in one M4L round-trip
- `snapshot_device_state` / `restore_device_snapshot` — capture and recall full device states
- `list_snapshots` / `delete_snapshot` / `get_snapshot_details` / `delete_all_snapshots`

### New: Device State Versioning & Undo
- `snapshot_all_devices` — capture all devices across multiple tracks as a group
- `restore_group_snapshot` — restore entire device groups at once
- `compare_snapshots` — diff two snapshots showing changed parameters with deltas

### New: Preset Morph Engine
- `morph_between_snapshots` — interpolate between two device states (0.0 = A, 1.0 = B); quantized params snap at midpoint

### New: Smart Macro Controller
- `create_macro_controller` / `set_macro_value` / `list_macros` / `delete_macro` — link multiple device parameters to a single 0.0-1.0 control

### New: Intelligent Preset Generator
- `generate_preset` — discover all params + auto-snapshot current state for AI-driven preset creation

### New: VST/AU Parameter Mapper
- `create_parameter_map` / `get_parameter_map` / `list_parameter_maps` / `delete_parameter_map` — map cryptic parameter names to friendly names with categories

### Improvements
- M4L bridge: added `batch_set_hidden_params` OSC command with base64-encoded JSON
- Total tools: 61 -> **81** (+20 new tools)

---

## v1.5.1 — 2026-02-09

### Rebrand
- Renamed from "ableton-mcp" to "AbletonMCP Beta"
- Comprehensive README rewrite with full tool reference and architecture documentation

---

## v1.5.0 — 2026-02-09

### Initial Full Release
- M4L bridge integration for hidden/non-automatable parameter access
- Bug fixes and stability improvements
- Live 12 compatibility
- 61 MCP tools
