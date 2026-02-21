"""MIDI: get notes (legacy + extended), quantize, transpose, clear, capture, groove."""

from __future__ import absolute_import, print_function, unicode_literals

import traceback

from ._helpers import get_clip


def get_clip_notes(song, track_index, clip_index, start_time, time_span, start_pitch, pitch_span, ctrl=None):
    """Get MIDI notes from a clip."""
    try:
        clip = _get_midi_clip(song, track_index, clip_index)

        # If time_span is 0, use entire clip length (+1 to include boundary notes)
        if time_span == 0.0:
            time_span = clip.length + 1

        # API: get_notes(start_time, start_pitch, time_span, pitch_span)
        notes_tuple = clip.get_notes(start_time, start_pitch, time_span, pitch_span)

        notes = []
        for note in notes_tuple:
            notes.append({
                "pitch": note[0],
                "start_time": note[1],
                "duration": note[2],
                "velocity": note[3],
                "mute": note[4] if len(note) > 4 else False,
            })

        return {
            "clip_name": clip.name,
            "clip_length": clip.length,
            "note_count": len(notes),
            "notes": notes,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting clip notes: " + str(e))
        raise


def add_notes_extended(song, track_index, clip_index, notes, ctrl=None):
    """Add MIDI notes with Live 11+ extended properties."""
    try:
        clip = _get_midi_clip(song, track_index, clip_index)

        # Try Live 11+ add_new_notes API
        if hasattr(clip, 'add_new_notes'):
            note_specs = []
            for n in notes:
                spec = {
                    "pitch": max(0, min(127, int(n.get("pitch", 60)))),
                    "start_time": max(0.0, float(n.get("start_time", 0.0))),
                    "duration": max(0.01, float(n.get("duration", 0.25))),
                    "velocity": max(1, min(127, int(n.get("velocity", 100)))),
                    "mute": bool(n.get("mute", False)),
                }
                if "probability" in n:
                    spec["probability"] = max(0.0, min(1.0, float(n["probability"])))
                if "velocity_deviation" in n:
                    spec["velocity_deviation"] = max(-127.0, min(127.0, float(n["velocity_deviation"])))
                if "release_velocity" in n:
                    spec["release_velocity"] = max(0, min(127, int(n["release_velocity"])))
                note_specs.append(spec)

            extended = False

            # Strategy 1: Try Live 12+ MidiNoteSpecification API
            try:
                import Live
                if hasattr(Live.Clip, 'MidiNoteSpecification'):
                    specs = []
                    for s in note_specs:
                        kwargs = {
                            "pitch": s["pitch"],
                            "start_time": s["start_time"],
                            "duration": s["duration"],
                            "velocity": s["velocity"],
                            "mute": s["mute"],
                        }
                        if "probability" in s:
                            kwargs["probability"] = s["probability"]
                        if "velocity_deviation" in s:
                            kwargs["velocity_deviation"] = s["velocity_deviation"]
                        if "release_velocity" in s:
                            kwargs["release_velocity"] = s["release_velocity"]
                        specs.append(Live.Clip.MidiNoteSpecification(**kwargs))
                    clip.add_new_notes(tuple(specs))
                    extended = True
                else:
                    raise AttributeError("MidiNoteSpecification not available")
            except Exception:
                # Strategy 2: Try dict format with add_new_notes
                try:
                    clip.add_new_notes(tuple([
                        {
                            "pitch": s["pitch"],
                            "start_time": s["start_time"],
                            "duration": s["duration"],
                            "velocity": s["velocity"],
                            "mute": s["mute"],
                            "probability": s.get("probability", 1.0),
                            "velocity_deviation": s.get("velocity_deviation", 0.0),
                            "release_velocity": s.get("release_velocity", 64),
                        } for s in note_specs
                    ]))
                    extended = True
                except Exception:
                    # Strategy 3: Legacy set_notes fallback (tuples)
                    # Fetch existing notes and merge so set_notes doesn't
                    # replace them.  Use clip.length + 1 to catch notes
                    # starting exactly at the clip boundary.
                    existing = clip.get_notes(0, 0, clip.length + 1, 128)
                    live_notes = list(existing)
                    for s in note_specs:
                        live_notes.append((s["pitch"], s["start_time"], s["duration"], int(s["velocity"]), s["mute"]))
                    clip.set_notes(tuple(live_notes))

            return {"note_count": len(note_specs), "extended": extended}
        else:
            # Legacy fallback — fetch existing notes and merge so set_notes
            # doesn't replace them.  Use clip.length + 1 to catch notes
            # starting exactly at the clip boundary.
            existing = clip.get_notes(0, 0, clip.length + 1, 128)
            live_notes = list(existing)
            for n in notes:
                pitch = max(0, min(127, int(n.get("pitch", 60))))
                start_time = max(0.0, float(n.get("start_time", 0.0)))
                duration = max(0.01, float(n.get("duration", 0.25)))
                velocity = max(1, min(127, int(n.get("velocity", 100))))
                mute = bool(n.get("mute", False))
                live_notes.append((pitch, start_time, duration, velocity, mute))
            clip.set_notes(tuple(live_notes))
            return {"note_count": len(notes), "extended": False}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error adding extended notes: " + str(e))
            ctrl.log_message(traceback.format_exc())
        raise


def get_notes_extended(song, track_index, clip_index, start_time, time_span, ctrl=None):
    """Get MIDI notes with Live 11+ extended properties."""
    try:
        clip = _get_midi_clip(song, track_index, clip_index)
        actual_time_span = time_span if time_span > 0 else clip.length + 1

        # Try Live 11+ get_notes_extended
        if hasattr(clip, 'get_notes_extended'):
            try:
                raw_notes = clip.get_notes_extended(0, 128, start_time, actual_time_span)
                notes = []
                for note in raw_notes:
                    note_dict = {
                        "pitch": note.pitch if hasattr(note, 'pitch') else note[0],
                        "start_time": note.start_time if hasattr(note, 'start_time') else note[1],
                        "duration": note.duration if hasattr(note, 'duration') else note[2],
                        "velocity": note.velocity if hasattr(note, 'velocity') else note[3],
                        "mute": note.mute if hasattr(note, 'mute') else (note[4] if len(note) > 4 else False),
                    }
                    if hasattr(note, 'probability'):
                        note_dict["probability"] = note.probability
                    if hasattr(note, 'velocity_deviation'):
                        note_dict["velocity_deviation"] = note.velocity_deviation
                    if hasattr(note, 'release_velocity'):
                        note_dict["release_velocity"] = note.release_velocity
                    notes.append(note_dict)
                return {
                    "clip_name": clip.name,
                    "clip_length": clip.length,
                    "note_count": len(notes),
                    "extended": True,
                    "notes": notes,
                }
            except Exception as exc:
                if ctrl:
                    ctrl.log_message("get_notes_extended failed, using legacy: " + str(exc))

        # Legacy fallback
        notes_tuple = clip.get_notes(start_time, 0, actual_time_span, 128)
        notes = []
        for note in notes_tuple:
            notes.append({
                "pitch": note[0],
                "start_time": note[1],
                "duration": note[2],
                "velocity": note[3],
                "mute": note[4] if len(note) > 4 else False,
            })
        return {
            "clip_name": clip.name,
            "clip_length": clip.length,
            "note_count": len(notes),
            "extended": False,
            "notes": notes,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting extended notes: " + str(e))
        raise


def remove_notes_range(song, track_index, clip_index, from_time, time_span, from_pitch, pitch_span, ctrl=None):
    """Remove notes within a specific time and pitch range."""
    try:
        clip = _get_midi_clip(song, track_index, clip_index)

        # Count notes before removal (+1 to include boundary notes)
        actual_time_span = time_span if time_span > 0 else clip.length + 1
        before = clip.get_notes(from_time, from_pitch, actual_time_span, pitch_span)
        count_before = len(before)

        if hasattr(clip, 'remove_notes_extended'):
            clip.remove_notes_extended(from_pitch, pitch_span, from_time, actual_time_span)
        else:
            clip.remove_notes(from_time, from_pitch, actual_time_span, pitch_span)

        return {
            "removed": True,
            "notes_removed": count_before,
            "from_time": from_time,
            "time_span": actual_time_span,
            "from_pitch": from_pitch,
            "pitch_span": pitch_span,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error removing notes range: " + str(e))
        raise


def clear_clip_notes(song, track_index, clip_index, ctrl=None):
    """Remove all MIDI notes from a clip."""
    try:
        clip = _get_midi_clip(song, track_index, clip_index)

        # Count notes before removing (use clip.length + 1 to match removal range)
        notes_before = clip.get_notes(0, 0, clip.length + 1, 128)
        notes_count = len(notes_before)

        # Remove all notes -- try Live 11+ API first, fall back to legacy
        # Use clip.length + 1 to include notes starting exactly at clip.length
        if hasattr(clip, 'remove_notes_extended'):
            clip.remove_notes_extended(0, 128, 0, clip.length + 1)
        else:
            clip.remove_notes(0, 0, clip.length + 1, 128)

        return {
            "cleared": True,
            "notes_removed": notes_count,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error clearing clip notes: " + str(e))
        raise


def quantize_clip_notes(song, track_index, clip_index, grid_size, ctrl=None):
    """Quantize MIDI notes in a clip to a grid."""
    try:
        if grid_size <= 0:
            raise ValueError("grid_size must be greater than 0")

        clip = _get_midi_clip(song, track_index, clip_index)

        notes_tuple = clip.get_notes(0, 0, clip.length + 1, 128)
        notes_count = len(notes_tuple)

        if notes_count == 0:
            return {"quantized": True, "notes_quantized": 0, "grid_size": grid_size}

        # Map grid_size (in beats) to Live's RecordQuantization enum
        grid_map = {
            1.0: 1,     # quarter notes
            0.5: 2,     # eighth notes
            0.25: 5,    # sixteenth notes
            0.125: 8,   # thirty-second notes
        }

        if hasattr(clip, 'quantize') and grid_size in grid_map:
            grid_value = grid_map[grid_size]
            clip.quantize(grid_value, 1.0)
        else:
            # Manual quantize fallback — prefer extended API to preserve
            # probability, velocity_deviation, release_velocity (Live 11+)
            used_extended = False
            if hasattr(clip, 'get_notes_extended') and hasattr(clip, 'apply_note_modifications'):
                raw_notes = clip.get_notes_extended(0, 128, 0, clip.length + 1)
                try:
                    for note in raw_notes:
                        old_time = note.start_time if hasattr(note, 'start_time') else note[1]
                        new_time = round(old_time / grid_size) * grid_size
                        if hasattr(note, 'start_time'):
                            note.start_time = new_time
                    clip.apply_note_modifications(raw_notes)
                    used_extended = True
                except AttributeError:
                    pass  # Immutable notes — fall through to legacy path
            if not used_extended:
                quantized_notes = []
                for note in notes_tuple:
                    pitch = note[0]
                    start_time = note[1]
                    duration = note[2]
                    velocity = note[3]
                    mute = note[4] if len(note) > 4 else False
                    quantized_time = round(start_time / grid_size) * grid_size
                    quantized_notes.append((pitch, quantized_time, duration, velocity, mute))

                # NOTE: remove+set is not atomic.  If set_notes fails after
                # remove, all notes are lost.  We attempt to restore the
                # original notes on failure.
                if hasattr(clip, 'remove_notes_extended'):
                    clip.remove_notes_extended(0, 128, 0, clip.length + 1)
                else:
                    clip.remove_notes(0, 0, clip.length + 1, 128)
                try:
                    clip.set_notes(tuple(quantized_notes))
                except Exception:
                    try:
                        clip.set_notes(tuple(notes_tuple))
                    except Exception as restore_err:
                        if ctrl:
                            ctrl.log_message("Failed to restore original notes after quantize error: " + str(restore_err))
                    raise

        return {
            "quantized": True,
            "notes_quantized": notes_count,
            "grid_size": grid_size,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error quantizing clip notes: " + str(e))
        raise


def transpose_clip_notes(song, track_index, clip_index, semitones, ctrl=None):
    """Transpose MIDI notes in a clip by a number of semitones."""
    try:
        clip = _get_midi_clip(song, track_index, clip_index)

        notes_tuple = clip.get_notes(0, 0, clip.length + 1, 128)
        if len(notes_tuple) == 0:
            return {"transposed": True, "notes_transposed": 0, "semitones": semitones}

        # Prefer extended API to preserve probability/velocity_deviation/release_velocity
        used_extended = False
        if hasattr(clip, 'get_notes_extended') and hasattr(clip, 'apply_note_modifications'):
            raw_notes = clip.get_notes_extended(0, 128, 0, clip.length + 1)
            try:
                for note in raw_notes:
                    old_pitch = note.pitch if hasattr(note, 'pitch') else note[0]
                    new_pitch = max(0, min(127, old_pitch + semitones))
                    if hasattr(note, 'pitch'):
                        note.pitch = new_pitch
                clip.apply_note_modifications(raw_notes)
                used_extended = True
            except AttributeError:
                pass  # Immutable notes — fall through to legacy path
        if not used_extended:
            transposed_notes = []
            for note in notes_tuple:
                pitch = note[0]
                start_time = note[1]
                duration = note[2]
                velocity = note[3]
                mute = note[4] if len(note) > 4 else False
                new_pitch = max(0, min(127, pitch + semitones))
                transposed_notes.append((new_pitch, start_time, duration, velocity, mute))

            # NOTE: remove+set is not atomic.  If set_notes fails after
            # remove, all notes are lost.  We attempt to restore the
            # original notes on failure.
            if hasattr(clip, 'remove_notes_extended'):
                clip.remove_notes_extended(0, 128, 0, clip.length + 1)
            else:
                clip.remove_notes(0, 0, clip.length + 1, 128)
            try:
                clip.set_notes(tuple(transposed_notes))
            except Exception:
                try:
                    clip.set_notes(tuple(notes_tuple))
                except Exception as restore_err:
                    if ctrl:
                        ctrl.log_message("Failed to restore original notes after transpose error: " + str(restore_err))
                raise

        return {
            "transposed": True,
            "notes_transposed": len(notes_tuple),
            "semitones": semitones,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error transposing clip notes: " + str(e))
        raise


# --- New commands from MacWhite ---


def capture_midi(song, ctrl=None):
    """Capture recently played MIDI."""
    try:
        if not hasattr(song, "capture_midi"):
            raise Exception("Capture MIDI is not available (requires Live 11 or later)")
        song.capture_midi()
        return {"captured": True}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error capturing MIDI: " + str(e))
        raise


def apply_groove(song, track_index, clip_index, groove_amount, ctrl=None):
    """Set global song.groove_amount. Validates clip exists but does NOT apply per-clip groove.

    NOTE: song.groove_amount is a global setting — it affects all clips that
    have a groove assigned, not just the specified clip.  The track_index and
    clip_index parameters are used only for input validation.
    """
    try:
        _get_midi_clip(song, track_index, clip_index)  # validate clip exists
        groove_amount = float(groove_amount)
        if groove_amount < 0.0 or groove_amount > 1.0:
            raise ValueError("groove_amount must be 0.0-1.0, got {0}".format(groove_amount))
        song.groove_amount = groove_amount
        return {
            "applied_scope": "song",
            "track_index": track_index,
            "clip_index": clip_index,
            "groove_amount": song.groove_amount,
            "note": "groove_amount is a global song property — affects all clips with a groove assigned",
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error applying groove: " + str(e))
        raise


# --- Helper ---


def _get_midi_clip(song, track_index, clip_index):
    """Get a MIDI clip with validation."""
    _, clip = get_clip(song, track_index, clip_index)
    if not hasattr(clip, 'get_notes'):
        raise Exception("Clip is not a MIDI clip")
    return clip
