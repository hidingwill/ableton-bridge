"""Clip creation, notes, naming, fire/stop, delete, colors, loop, markers."""

from __future__ import absolute_import, print_function, unicode_literals

import collections.abc

from ._helpers import get_track, get_clip_slot, get_clip


def create_clip(song, track_index, clip_index, length, ctrl=None):
    """Create a new MIDI clip in the specified track and clip slot."""
    try:
        track, clip_slot = get_clip_slot(song, track_index, clip_index)
        if clip_slot.has_clip:
            raise Exception("Clip slot already has a clip")
        length = float(length)
        if length <= 0:
            raise ValueError("Clip length must be positive, got {0}".format(length))
        clip_slot.create_clip(length)
        return {
            "name": clip_slot.clip.name,
            "length": clip_slot.clip.length,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating clip: " + str(e))
        raise


def add_notes_to_clip(song, track_index, clip_index, notes, ctrl=None):
    """Add MIDI notes to a clip."""
    try:
        _, clip = get_clip(song, track_index, clip_index)

        # Validate and normalize note data
        note_specs = []
        for note in notes:
            note_specs.append({
                "pitch": max(0, min(127, int(note.get("pitch", 60)))),
                "start_time": max(0.0, float(note.get("start_time", 0.0))),
                "duration": max(0.01, float(note.get("duration", 0.25))),
                "velocity": max(1, min(127, int(note.get("velocity", 100)))),
                "mute": bool(note.get("mute", False)),
            })

        # Strategy 1: Live 12+ MidiNoteSpecification API
        try:
            import Live
            if hasattr(Live.Clip, 'MidiNoteSpecification'):
                specs = []
                for s in note_specs:
                    specs.append(Live.Clip.MidiNoteSpecification(
                        pitch=s["pitch"], start_time=s["start_time"],
                        duration=s["duration"], velocity=s["velocity"],
                        mute=s["mute"]))
                clip.add_new_notes(tuple(specs))
                return {"note_count": len(notes)}
        except Exception as exc:
            if ctrl:
                ctrl.log_message("Strategy 1 (MidiNoteSpecification) failed: " + str(exc))

        # Strategy 2: Legacy tuple-based add_new_notes (Live 11+)
        if hasattr(clip, 'add_new_notes'):
            try:
                legacy_tuples = tuple(
                    (s["pitch"], s["start_time"], s["duration"], s["velocity"], s["mute"])
                    for s in note_specs
                )
                clip.add_new_notes(legacy_tuples)
                return {"note_count": len(notes)}
            except Exception as exc:
                if ctrl:
                    ctrl.log_message("Strategy 2 (add_new_notes tuples) failed: " + str(exc))

        # Strategy 3: Legacy set_notes fallback
        # Fetch existing notes and merge so set_notes doesn't replace them.
        # Use clip.length + 1 to ensure notes at the exact boundary are captured.
        existing = clip.get_notes(0, 0, clip.length + 1, 128)
        live_notes = list(existing)
        for s in note_specs:
            live_notes.append((s["pitch"], s["start_time"], s["duration"], int(s["velocity"]), s["mute"]))
        clip.set_notes(tuple(live_notes))
        return {"note_count": len(note_specs)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error adding notes to clip: " + str(e))
        raise


def set_clip_name(song, track_index, clip_index, name, ctrl=None):
    """Set the name of a clip."""
    try:
        _, clip = get_clip(song, track_index, clip_index)
        clip.name = name
        return {"name": clip.name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip name: " + str(e))
        raise


def fire_clip(song, track_index, clip_index, ctrl=None):
    """Fire a clip."""
    try:
        _, clip_slot = get_clip_slot(song, track_index, clip_index)
        if not clip_slot.has_clip:
            raise Exception("No clip in slot")
        clip_slot.fire()
        return {"fired": True}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error firing clip: " + str(e))
        raise


def stop_clip(song, track_index, clip_index, ctrl=None):
    """Stop a clip."""
    try:
        _, clip_slot = get_clip_slot(song, track_index, clip_index)
        clip_slot.stop()
        return {"stopped": True}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error stopping clip: " + str(e))
        raise


def delete_clip(song, track_index, clip_index, ctrl=None):
    """Delete a clip from a clip slot."""
    try:
        _, clip_slot = get_clip_slot(song, track_index, clip_index)
        if not clip_slot.has_clip:
            raise Exception("No clip in slot")
        clip_name = clip_slot.clip.name
        clip_slot.delete_clip()
        return {
            "deleted": True,
            "clip_name": clip_name,
            "track_index": track_index,
            "clip_index": clip_index,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error deleting clip: " + str(e))
        raise


def get_clip_info(song, track_index, clip_index, ctrl=None):
    """Get detailed information about a clip."""
    try:
        _, clip = get_clip(song, track_index, clip_index)

        result = {
            "name": clip.name,
            "length": clip.length,
            "is_playing": clip.is_playing,
            "is_recording": clip.is_recording,
            "is_midi_clip": hasattr(clip, 'get_notes'),
        }

        # Try to get additional properties if available
        try:
            if hasattr(clip, 'start_marker'):
                result["start_marker"] = clip.start_marker
            if hasattr(clip, 'end_marker'):
                result["end_marker"] = clip.end_marker
            if hasattr(clip, 'loop_start'):
                result["loop_start"] = clip.loop_start
            if hasattr(clip, 'loop_end'):
                result["loop_end"] = clip.loop_end
            if hasattr(clip, 'looping'):
                result["looping"] = clip.looping
            if hasattr(clip, 'warping'):
                result["warping"] = clip.warping
            if hasattr(clip, 'color_index'):
                result["color_index"] = clip.color_index
        except Exception:
            pass

        # Playing/triggered status
        try:
            result["is_triggered"] = clip.is_triggered
        except Exception:
            pass
        try:
            result["playing_position"] = clip.playing_position
        except Exception:
            pass
        try:
            result["launch_mode"] = int(clip.launch_mode)
        except Exception:
            pass
        try:
            result["velocity_amount"] = clip.velocity_amount
        except Exception:
            pass
        try:
            result["legato"] = clip.legato
        except Exception:
            pass

        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting clip info: " + str(e))
        raise


def duplicate_clip(song, track_index, clip_index, target_clip_index, ctrl=None):
    """Duplicate a clip to another slot on the same track."""
    try:
        track = get_track(song, track_index)
        if clip_index < 0 or clip_index >= len(track.clip_slots):
            raise IndexError("Source clip index out of range")
        if target_clip_index < 0 or target_clip_index >= len(track.clip_slots):
            raise IndexError("Target clip index out of range")
        source_slot = track.clip_slots[clip_index]
        target_slot = track.clip_slots[target_clip_index]
        if not source_slot.has_clip:
            raise Exception("No clip in source slot")
        if target_slot.has_clip:
            raise Exception("Target slot already has a clip")
        source_slot.duplicate_clip_to(target_slot)
        return {
            "duplicated": True,
            "source_index": clip_index,
            "target_index": target_clip_index,
            "clip_name": source_slot.clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error duplicating clip: " + str(e))
        raise


def set_clip_looping(song, track_index, clip_index, looping, ctrl=None):
    """Set the looping state of a clip."""
    try:
        _, clip = get_clip(song, track_index, clip_index)
        clip.looping = bool(int(looping))
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "looping": clip.looping,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip looping: " + str(e))
        raise


def set_clip_loop_points(song, track_index, clip_index, loop_start, loop_end, ctrl=None):
    """Set the loop start and end points of a clip."""
    try:
        _, clip = get_clip(song, track_index, clip_index)

        loop_start = float(loop_start)
        loop_end = float(loop_end)
        if loop_start >= loop_end:
            raise ValueError(
                "loop_start ({0}) must be less than loop_end ({1})".format(loop_start, loop_end))

        # Set in safe order to avoid loop_start >= loop_end errors
        if loop_end > clip.loop_start:
            clip.loop_end = loop_end
            clip.loop_start = loop_start
        else:
            clip.loop_start = loop_start
            clip.loop_end = loop_end

        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "loop_start": clip.loop_start,
            "loop_end": clip.loop_end,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip loop points: " + str(e))
        raise


def set_clip_color(song, track_index, clip_index, color_index, ctrl=None):
    """Set the color of a clip."""
    try:
        _, clip = get_clip(song, track_index, clip_index)
        color_index = int(color_index)
        if color_index < 0 or color_index > 69:
            raise ValueError("color_index must be between 0 and 69, got {0}".format(color_index))
        clip.color_index = color_index
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "color_index": clip.color_index,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip color: " + str(e))
        raise


def crop_clip(song, track_index, clip_index, ctrl=None):
    """Trim clip to its loop region."""
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not hasattr(clip, 'crop'):
            raise Exception("clip.crop() not available in this Live version")
        clip.crop()
        return {
            "cropped": True,
            "new_length": clip.length,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error cropping clip: " + str(e))
        raise


def duplicate_clip_loop(song, track_index, clip_index, ctrl=None):
    """Double the loop content of a clip."""
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not hasattr(clip, 'duplicate_loop'):
            raise Exception("clip.duplicate_loop() not available in this Live version")
        old_length = clip.length
        clip.duplicate_loop()
        return {
            "old_length": old_length,
            "new_length": clip.length,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error duplicating clip loop: " + str(e))
        raise


def set_clip_start_end(song, track_index, clip_index, start_marker, end_marker, ctrl=None):
    """Set clip start_marker and end_marker."""
    try:
        _, clip = get_clip(song, track_index, clip_index)

        if start_marker is not None and end_marker is not None:
            sm = float(start_marker)
            em = float(end_marker)
            if sm >= em:
                raise ValueError(
                    "start_marker ({0}) must be less than end_marker ({1})".format(sm, em))
            # Safe order: set the "expanding" side first
            if em > clip.start_marker:
                clip.end_marker = em
                clip.start_marker = sm
            else:
                clip.start_marker = sm
                clip.end_marker = em
        elif start_marker is not None:
            sm = float(start_marker)
            if sm >= clip.end_marker:
                raise ValueError(
                    "start_marker ({0}) must be less than current end_marker ({1})".format(
                        sm, clip.end_marker))
            clip.start_marker = sm
        elif end_marker is not None:
            em = float(end_marker)
            if clip.start_marker >= em:
                raise ValueError(
                    "end_marker ({0}) must be greater than current start_marker ({1})".format(
                        em, clip.start_marker))
            clip.end_marker = em

        return {
            "start_marker": clip.start_marker,
            "end_marker": clip.end_marker,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip start/end: " + str(e))
        raise


def set_clip_pitch(song, track_index, clip_index, pitch_coarse=None, pitch_fine=None, ctrl=None):
    """Set pitch transposition for an audio clip.

    Args:
        pitch_coarse: Semitones (-48 to +48)
        pitch_fine: Cents (-50 to +50)
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not clip.is_audio_clip:
            raise ValueError("Clip is not an audio clip")
        if pitch_coarse is not None:
            pitch_coarse = int(pitch_coarse)
            if pitch_coarse < -48 or pitch_coarse > 48:
                raise ValueError(
                    "pitch_coarse must be between -48 and +48 semitones, got {0}".format(pitch_coarse))
            clip.pitch_coarse = pitch_coarse
        if pitch_fine is not None:
            pitch_fine = float(pitch_fine)
            if pitch_fine < -50 or pitch_fine > 50:
                raise ValueError(
                    "pitch_fine must be between -50 and +50 cents, got {0}".format(pitch_fine))
            clip.pitch_fine = pitch_fine
        return {
            "pitch_coarse": clip.pitch_coarse,
            "pitch_fine": clip.pitch_fine,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip pitch: " + str(e))
        raise


def set_clip_launch_mode(song, track_index, clip_index, launch_mode, ctrl=None):
    """Set the launch mode for a clip.

    Args:
        launch_mode: 0=trigger, 1=gate, 2=toggle, 3=repeat
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        launch_mode = int(launch_mode)
        if launch_mode < 0 or launch_mode > 3:
            raise ValueError(
                "launch_mode must be 0-3 (trigger/gate/toggle/repeat), got {0}".format(launch_mode))
        clip.launch_mode = launch_mode
        return {
            "launch_mode": clip.launch_mode,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip launch mode: " + str(e))
        raise


def set_clip_launch_quantization(song, track_index, clip_index, quantization, ctrl=None):
    """Set the launch quantization for a clip.

    Args:
        quantization: 0=none, 1=8bars, 2=4bars, 3=2bars, 4=bar, 5=half,
            6=half_triplet, 7=quarter, 8=quarter_triplet, 9=eighth,
            10=eighth_triplet, 11=sixteenth, 12=sixteenth_triplet,
            13=thirtysecond, 14=global
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        quantization = int(quantization)
        if quantization < 0 or quantization > 14:
            raise ValueError("Launch quantization must be 0-14")
        clip.launch_quantization = quantization
        return {
            "launch_quantization": clip.launch_quantization,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip launch quantization: " + str(e))
        raise


def set_clip_legato(song, track_index, clip_index, legato, ctrl=None):
    """Set the legato mode for a clip.

    Args:
        legato: True = clip plays from position of previously playing clip.
                False = clip always starts from its start position.
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        clip.legato = bool(int(legato))
        return {
            "legato": clip.legato,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip legato: " + str(e))
        raise


def audio_to_midi(song, track_index, clip_index, conversion_type, ctrl=None):
    """Convert an audio clip to a MIDI clip.

    Args:
        conversion_type: 'drums', 'harmony', or 'melody'
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not clip.is_audio_clip:
            raise ValueError("Clip is not an audio clip")
        conversion_type = str(conversion_type).lower()
        if conversion_type not in ("drums", "harmony", "melody"):
            raise ValueError("conversion_type must be 'drums', 'harmony', or 'melody'")
        try:
            from Live.Conversions import audio_to_midi_clip, AudioToMidiType
        except ImportError as imp_err:
            raise Exception(
                "Audio-to-MIDI conversion requires Live 12+ "
                "(failed to import Live.Conversions: {0})".format(imp_err)
            ) from imp_err
        type_map = {
            "drums": AudioToMidiType.drums_to_midi,
            "harmony": AudioToMidiType.harmony_to_midi,
            "melody": AudioToMidiType.melody_to_midi,
        }
        audio_to_midi_clip(song, clip, type_map[conversion_type])
        return {
            "converted": True,
            "source_clip": clip.name,
            "conversion_type": conversion_type,
            "track_index": track_index,
            "clip_index": clip_index,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error converting audio to MIDI: " + str(e))
        raise


def duplicate_clip_region(song, track_index, clip_index,
                          region_start, region_length, destination_time,
                          pitch=-1, transposition_amount=0, ctrl=None):
    """Duplicate notes in a region to another position, with optional transposition.

    MIDI clips only. If pitch is -1, all notes in the region are duplicated.

    Args:
        region_start: Start time of the region to duplicate.
        region_length: Length of the region.
        destination_time: Where to place the duplicated notes.
        pitch: Only duplicate notes at this pitch (-1 for all).
        transposition_amount: Semitones to transpose (0 for none).
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if clip.is_audio_clip:
            raise ValueError("duplicate_region is only available for MIDI clips")
        clip.duplicate_region(float(region_start), float(region_length),
                              float(destination_time), int(pitch), int(transposition_amount))
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "region_start": region_start,
            "region_length": region_length,
            "destination_time": destination_time,
            "pitch": pitch,
            "transposition_amount": transposition_amount,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error duplicating clip region: " + str(e))
        raise


def move_clip_playing_pos(song, track_index, clip_index, time, ctrl=None):
    """Jump to a position within a currently playing clip.

    Args:
        time: The time position to jump to within the clip.
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        clip.move_playing_pos(float(time))
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "position": float(time),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error moving clip playing position: " + str(e))
        raise


def set_clip_grid(song, track_index, clip_index,
                   grid_quantization=None, grid_is_triplet=None, ctrl=None):
    """Set the MIDI editor grid resolution for a clip.

    Args:
        grid_quantization: Grid resolution value (enum int from Clip.grid_quantization).
        grid_is_triplet: True to show grid in triplet mode, False for standard.
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        changes = {}
        if grid_quantization is not None:
            clip.view.grid_quantization = int(grid_quantization)
            changes["grid_quantization"] = int(grid_quantization)
        if grid_is_triplet is not None:
            grid_is_triplet = bool(int(grid_is_triplet))
            clip.view.grid_is_triplet = grid_is_triplet
            changes["grid_is_triplet"] = grid_is_triplet
        if not changes:
            raise ValueError("No parameters specified")
        changes["track_index"] = track_index
        changes["clip_index"] = clip_index
        return changes
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip grid: " + str(e))
        raise


# --- Warp Markers ---


def get_warp_markers(song, track_index, clip_index, ctrl=None):
    """Get the warp markers of an audio clip."""
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not clip.is_audio_clip:
            raise ValueError("Warp markers are only available on audio clips")
        markers = []
        try:
            wm = clip.warp_markers
            if isinstance(wm, dict):
                # LOM returns dict format
                wm_list = wm.get("warp_markers", [])
                for i, m in enumerate(wm_list):
                    if isinstance(m, dict):
                        markers.append({
                            "index": i,
                            "beat_time": m.get("beat_time", 0.0),
                            "sample_time": m.get("sample_time", 0.0),
                        })
                    else:
                        markers.append({
                            "index": i,
                            "beat_time": getattr(m, "beat_time", 0.0),
                            "sample_time": getattr(m, "sample_time", 0.0),
                        })
            elif isinstance(wm, collections.abc.Iterable) and not isinstance(wm, (str, bytes)):
                for i, m in enumerate(wm):
                    markers.append({
                        "index": i,
                        "beat_time": getattr(m, "beat_time", 0.0),
                        "sample_time": getattr(m, "sample_time", 0.0),
                    })
            else:
                if ctrl:
                    ctrl.log_message(
                        "Unexpected warp_markers type: {0}".format(type(wm).__name__))
        except Exception as e:
            if ctrl:
                ctrl.log_message("Error reading warp markers: " + str(e))
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "warping": clip.warping,
            "warp_markers": markers,
            "count": len(markers),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting warp markers: " + str(e))
        raise


def add_warp_marker(song, track_index, clip_index, beat_time, sample_time=None, ctrl=None):
    """Add a warp marker to an audio clip.

    Args:
        beat_time: The beat position for the warp marker.
        sample_time: The sample position (if None, auto-calculated by Live).
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not clip.is_audio_clip:
            raise ValueError("Warp markers are only available on audio clips")
        bt = float(beat_time)
        if sample_time is not None:
            clip.add_warp_marker(bt, float(sample_time))
        else:
            clip.add_warp_marker(bt)
        return {
            "added": True,
            "beat_time": bt,
            "sample_time": float(sample_time) if sample_time is not None else None,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error adding warp marker: " + str(e))
        raise


def move_warp_marker(song, track_index, clip_index, beat_time, beat_time_distance, ctrl=None):
    """Move a warp marker by a beat-time distance.

    Args:
        beat_time: Beat position of the warp marker to move.
        beat_time_distance: Amount (in beats) to shift the marker.
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not clip.is_audio_clip:
            raise ValueError("Warp markers are only available on audio clips")
        clip.move_warp_marker(float(beat_time), float(beat_time_distance))
        return {
            "moved": True,
            "beat_time": float(beat_time),
            "beat_time_distance": float(beat_time_distance),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error moving warp marker: " + str(e))
        raise


def remove_warp_marker(song, track_index, clip_index, beat_time, ctrl=None):
    """Remove a warp marker from an audio clip.

    Args:
        beat_time: Beat position of the warp marker to remove.
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not clip.is_audio_clip:
            raise ValueError("Warp markers are only available on audio clips")
        clip.remove_warp_marker(float(beat_time))
        return {
            "removed": True,
            "beat_time": float(beat_time),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error removing warp marker: " + str(e))
        raise
