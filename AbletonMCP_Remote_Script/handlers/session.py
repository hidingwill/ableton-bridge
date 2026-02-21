"""Session-level commands: tempo, playback, transport, loop, recording, metronome."""

from __future__ import absolute_import, print_function, unicode_literals

from ._helpers import get_track, get_clip


def get_session_info(song, ctrl=None):
    """Get information about the current session."""
    try:
        result = {
            "tempo": song.tempo,
            "signature_numerator": song.signature_numerator,
            "signature_denominator": song.signature_denominator,
            "track_count": len(song.tracks),
            "return_track_count": len(song.return_tracks),
            "master_track": {
                "name": "Master",
                "volume": song.master_track.mixer_device.volume.value,
                "panning": song.master_track.mixer_device.panning.value,
            },
        }
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting session info: " + str(e))
        raise


def set_tempo(song, tempo, ctrl=None):
    """Set the tempo of the session (20.0-999.0 BPM)."""
    try:
        tempo = float(tempo)
        if tempo < 20.0 or tempo > 999.0:
            raise ValueError(
                "Tempo must be between 20.0 and 999.0 BPM, got {0}".format(tempo))
        song.tempo = tempo
        return {"tempo": song.tempo}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting tempo: " + str(e))
        raise


def start_playback(song, ctrl=None):
    """Start playing the session."""
    try:
        song.start_playing()
        return {"playing": song.is_playing}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error starting playback: " + str(e))
        raise


def stop_playback(song, ctrl=None):
    """Stop playing the session."""
    try:
        song.stop_playing()
        return {"playing": song.is_playing}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error stopping playback: " + str(e))
        raise


def get_song_transport(song, ctrl=None):
    """Get transport/arrangement state."""
    try:
        result = {
            "current_time": song.current_song_time,
            "is_playing": song.is_playing,
            "tempo": song.tempo,
            "signature_numerator": song.signature_numerator,
            "signature_denominator": song.signature_denominator,
            "loop_enabled": song.loop,
            "loop_start": song.loop_start,
            "loop_length": song.loop_length,
            "song_length": song.song_length,
        }
        try:
            result["record_mode"] = song.record_mode
        except Exception:
            result["record_mode"] = False
        try:
            result["punch_in"] = song.punch_in
        except Exception:
            result["punch_in"] = None
        try:
            result["punch_out"] = song.punch_out
        except Exception:
            result["punch_out"] = None
        try:
            result["count_in_duration"] = int(song.count_in_duration)
        except Exception:
            result["count_in_duration"] = None
        try:
            result["is_counting_in"] = song.is_counting_in
        except Exception:
            result["is_counting_in"] = None
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting song transport: " + str(e))
        raise


def set_song_time(song, time, ctrl=None):
    """Set the arrangement playhead position."""
    try:
        target = max(0.0, float(time))
        song.current_song_time = target
        return {"current_time": target}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting song time: " + str(e))
        raise


def set_song_loop(song, enabled, start, length, ctrl=None):
    """Control arrangement loop bracket."""
    try:
        # Validate all inputs before mutating
        v_enabled = None
        v_start = None
        v_length = None
        if enabled is not None:
            v_enabled = bool(enabled)
        if start is not None:
            v_start = max(0.0, float(start))
        if length is not None:
            v_length = float(length)
            if v_length <= 0:
                raise ValueError("Loop length must be positive, got {0}".format(v_length))

        # Apply validated values
        if v_enabled is not None:
            song.loop = v_enabled
        if v_start is not None:
            song.loop_start = v_start
        if v_length is not None:
            song.loop_length = v_length

        return {
            "loop_enabled": v_enabled if v_enabled is not None else song.loop,
            "loop_start": v_start if v_start is not None else song.loop_start,
            "loop_length": v_length if v_length is not None else song.loop_length,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting song loop: " + str(e))
        raise


# --- New commands from MacWhite ---


def get_loop_info(song, ctrl=None):
    """Get loop information."""
    try:
        return {
            "loop_start": song.loop_start,
            "loop_end": song.loop_start + song.loop_length,
            "loop_length": song.loop_length,
            "loop": song.loop,
            "current_song_time": song.current_song_time,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting loop info: " + str(e))
        raise


def set_loop_start(song, position, ctrl=None):
    """Set the loop start position."""
    try:
        position = max(0.0, float(position))
        song.loop_start = position
        return {"loop_start": song.loop_start, "loop_end": song.loop_start + song.loop_length}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting loop start: " + str(e))
        raise


def set_loop_end(song, position, ctrl=None):
    """Set the loop end position."""
    try:
        pos = float(position)
        if pos <= song.loop_start:
            raise ValueError("Loop end ({0}) must be greater than loop start ({1})".format(
                pos, song.loop_start))
        # loop_end isn't a direct property; compute via loop_length
        song.loop_length = pos - song.loop_start
        return {"loop_start": song.loop_start, "loop_end": song.loop_start + song.loop_length}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting loop end: " + str(e))
        raise


def set_loop_length(song, length, ctrl=None):
    """Set the loop length."""
    try:
        length_val = float(length)
        if length_val <= 0:
            raise ValueError("Loop length must be positive, got {0}".format(length_val))
        song.loop_length = length_val
        return {
            "loop_start": song.loop_start,
            "loop_end": song.loop_start + song.loop_length,
            "loop_length": song.loop_length,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting loop length: " + str(e))
        raise


def set_playback_position(song, position, ctrl=None):
    """Set the playback position."""
    try:
        song.current_song_time = max(0.0, float(position))
        return {"current_song_time": song.current_song_time}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting playback position: " + str(e))
        raise


def set_arrangement_overdub(song, enabled, ctrl=None):
    """Enable or disable arrangement overdub mode."""
    try:
        song.arrangement_overdub = bool(enabled)
        return {"arrangement_overdub": song.arrangement_overdub}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting arrangement overdub: " + str(e))
        raise


def start_arrangement_recording(song, ctrl=None):
    """Start recording into the arrangement view."""
    try:
        song.record_mode = True
        if not song.is_playing:
            song.start_playing()
        return {
            "recording": song.record_mode,
            "playing": song.is_playing,
            "arrangement_overdub": song.arrangement_overdub,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error starting arrangement recording: " + str(e))
        raise


def stop_arrangement_recording(song, stop_playback=True, ctrl=None):
    """Stop arrangement recording.

    Args:
        song: Live Song object.
        stop_playback: If True (default), also stops transport playback.
            Set to False to stop recording while keeping playback running
            (useful for punch-out workflows where you want to keep listening).
        ctrl: Optional controller for logging.
    """
    try:
        song.record_mode = False
        if stop_playback and song.is_playing:
            song.stop_playing()
        return {"recording": song.record_mode, "playing": song.is_playing}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error stopping arrangement recording: " + str(e))
        raise


def get_recording_status(song, ctrl=None):
    """Get the current recording status."""
    try:
        armed_tracks = []
        for i, track in enumerate(song.tracks):
            try:
                if track.can_be_armed and track.arm:
                    armed_tracks.append({
                        "index": i,
                        "name": track.name,
                        "is_midi": track.has_midi_input,
                        "is_audio": track.has_audio_input,
                    })
            except Exception:
                pass
        return {
            "record_mode": song.record_mode,
            "arrangement_overdub": song.arrangement_overdub,
            "session_record": song.session_record,
            "is_playing": song.is_playing,
            "armed_tracks": armed_tracks,
            "armed_track_count": len(armed_tracks),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting recording status: " + str(e))
        raise


def set_metronome(song, enabled, ctrl=None):
    """Enable or disable the metronome."""
    try:
        song.metronome = bool(enabled)
        return {"metronome": song.metronome}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting metronome: " + str(e))
        raise


def tap_tempo(song, ctrl=None):
    """Tap tempo to set BPM."""
    try:
        song.tap_tempo()
        return {"tempo": song.tempo}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error tapping tempo: " + str(e))
        raise


# --- Undo / Redo ---


def undo(song, ctrl=None):
    """Undo the last action."""
    try:
        if not song.can_undo:
            return {"undone": False, "reason": "Nothing to undo"}
        song.undo()
        return {"undone": True}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error performing undo: " + str(e))
        raise


def redo(song, ctrl=None):
    """Redo the last undone action."""
    try:
        if not song.can_redo:
            return {"redone": False, "reason": "Nothing to redo"}
        song.redo()
        return {"redone": True}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error performing redo: " + str(e))
        raise


# --- Additional transport ---


def continue_playing(song, ctrl=None):
    """Continue playback from the current position (does not jump to start)."""
    try:
        song.continue_playing()
        return {"playing": song.is_playing, "position": song.current_song_time}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error continuing playback: " + str(e))
        raise


def re_enable_automation(song, ctrl=None):
    """Re-enable all automation that has been manually overridden."""
    try:
        song.re_enable_automation()
        return {"re_enabled": True}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error re-enabling automation: " + str(e))
        raise


# --- Cue points ---


def get_cue_points(song, ctrl=None):
    """Get all cue points (markers) in the arrangement."""
    try:
        cues = []
        for cue in song.cue_points:
            cues.append({
                "name": cue.name,
                "time": cue.time,
            })
        cues.sort(key=lambda c: c["time"])
        return {"cue_points": cues, "count": len(cues)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting cue points: " + str(e))
        raise


def set_or_delete_cue(song, ctrl=None):
    """Toggle a cue point at the current playback position.

    If a cue point exists at the current position, it is deleted.
    Otherwise, a new cue point is created.
    """
    try:
        song.set_or_delete_cue()
        return {"position": song.current_song_time}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error toggling cue point: " + str(e))
        raise


def jump_to_cue(song, direction, ctrl=None):
    """Jump to the next or previous cue point.

    Args:
        direction: 'next' or 'prev'
    """
    try:
        if direction == "next":
            if not song.can_jump_to_next_cue:
                return {"jumped": False, "reason": "No next cue point"}
            song.jump_to_next_cue()
        elif direction == "prev":
            if not song.can_jump_to_prev_cue:
                return {"jumped": False, "reason": "No previous cue point"}
            song.jump_to_prev_cue()
        else:
            raise ValueError("direction must be 'next' or 'prev', got '{0}'".format(direction))
        return {"jumped": True, "position": song.current_song_time}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error jumping to cue: " + str(e))
        raise


def get_groove_pool(song, ctrl=None):
    """Read the groove pool: global groove amount and list of grooves with their params."""
    try:
        result = {
            "groove_amount": getattr(song, "groove_amount", 1.0),
            "grooves": [],
        }
        pool = getattr(song, "groove_pool", None)
        if pool is not None and hasattr(pool, "grooves"):
            for i, groove in enumerate(pool.grooves):
                groove_info = {
                    "index": i,
                    "name": getattr(groove, "name", "Groove {0}".format(i)),
                    "timing_amount": getattr(groove, "timing_amount", 0.0),
                    "quantization_amount": getattr(groove, "quantization_amount", 0.0),
                    "random_amount": getattr(groove, "random_amount", 0.0),
                    "velocity_amount": getattr(groove, "velocity_amount", 0.0),
                }
                result["grooves"].append(groove_info)
        result["groove_count"] = len(result["grooves"])
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting groove pool: " + str(e))
        raise


# --- Song Settings ---


def get_song_settings(song, ctrl=None):
    """Get global song settings: time signature, swing, quantization, overdub, etc."""
    try:
        result = {
            "signature_numerator": song.signature_numerator,
            "signature_denominator": song.signature_denominator,
            "swing_amount": song.swing_amount,
            "arrangement_overdub": song.arrangement_overdub,
            "back_to_arranger": song.back_to_arranger,
        }
        try:
            result["clip_trigger_quantization"] = int(song.clip_trigger_quantization)
        except Exception:
            result["clip_trigger_quantization"] = None
        try:
            result["midi_recording_quantization"] = int(song.midi_recording_quantization)
        except Exception:
            result["midi_recording_quantization"] = None
        try:
            result["follow_song"] = song.view.follow_song
        except Exception:
            result["follow_song"] = None
        try:
            result["draw_mode"] = song.view.draw_mode
        except Exception:
            result["draw_mode"] = None
        try:
            result["tempo_follower_enabled"] = song.tempo_follower_enabled
        except Exception:
            result["tempo_follower_enabled"] = None
        try:
            result["exclusive_arm"] = song.exclusive_arm
        except Exception:
            result["exclusive_arm"] = None
        try:
            result["exclusive_solo"] = song.exclusive_solo
        except Exception:
            result["exclusive_solo"] = None
        try:
            result["session_automation_record"] = song.session_automation_record
        except Exception:
            result["session_automation_record"] = None
        try:
            result["song_length"] = song.song_length
        except Exception:
            result["song_length"] = None
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting song settings: " + str(e))
        raise


def set_song_settings(song, signature_numerator=None, signature_denominator=None,
                       swing_amount=None, clip_trigger_quantization=None,
                       midi_recording_quantization=None, back_to_arranger=None,
                       follow_song=None, draw_mode=None,
                       session_automation_record=None, ctrl=None):
    """Set global song settings."""
    try:
        # Phase 1: validate all inputs into local vars before mutating song
        validated = {}
        if signature_numerator is not None:
            val = int(signature_numerator)
            if val < 1 or val > 99:
                raise ValueError("signature_numerator must be 1-99, got {0}".format(val))
            validated["signature_numerator"] = val
        if signature_denominator is not None:
            val = int(signature_denominator)
            if val not in (1, 2, 4, 8, 16):
                raise ValueError("signature_denominator must be 1, 2, 4, 8, or 16, got {0}".format(val))
            validated["signature_denominator"] = val
        if swing_amount is not None:
            val = float(swing_amount)
            if val < 0.0 or val > 1.0:
                raise ValueError("swing_amount must be 0.0-1.0, got {0}".format(val))
            validated["swing_amount"] = val
        if clip_trigger_quantization is not None:
            val = int(clip_trigger_quantization)
            if val < 0 or val > 13:
                raise ValueError("clip_trigger_quantization must be 0-13 (Live RecordingQuantization enum), got {0}".format(val))
            validated["clip_trigger_quantization"] = val
        if midi_recording_quantization is not None:
            val = int(midi_recording_quantization)
            if val < 0 or val > 13:
                raise ValueError("midi_recording_quantization must be 0-13 (Live RecordingQuantization enum), got {0}".format(val))
            validated["midi_recording_quantization"] = val
        if back_to_arranger is not None:
            validated["back_to_arranger"] = bool(back_to_arranger)
        if follow_song is not None:
            validated["follow_song"] = bool(follow_song)
        if draw_mode is not None:
            validated["draw_mode"] = bool(draw_mode)
        if session_automation_record is not None:
            validated["session_automation_record"] = bool(session_automation_record)
        if not validated:
            raise ValueError("No parameters specified")

        # Phase 2: apply all validated values
        changes = {}
        if "signature_numerator" in validated:
            song.signature_numerator = validated["signature_numerator"]
            changes["signature_numerator"] = validated["signature_numerator"]
        if "signature_denominator" in validated:
            song.signature_denominator = validated["signature_denominator"]
            changes["signature_denominator"] = validated["signature_denominator"]
        if "swing_amount" in validated:
            song.swing_amount = validated["swing_amount"]
            changes["swing_amount"] = validated["swing_amount"]
        if "clip_trigger_quantization" in validated:
            song.clip_trigger_quantization = validated["clip_trigger_quantization"]
            changes["clip_trigger_quantization"] = validated["clip_trigger_quantization"]
        if "midi_recording_quantization" in validated:
            song.midi_recording_quantization = validated["midi_recording_quantization"]
            changes["midi_recording_quantization"] = validated["midi_recording_quantization"]
        if "back_to_arranger" in validated:
            song.back_to_arranger = validated["back_to_arranger"]
            changes["back_to_arranger"] = validated["back_to_arranger"]
        if "follow_song" in validated:
            song.view.follow_song = validated["follow_song"]
            changes["follow_song"] = validated["follow_song"]
        if "draw_mode" in validated:
            song.view.draw_mode = validated["draw_mode"]
            changes["draw_mode"] = validated["draw_mode"]
        if "session_automation_record" in validated:
            song.session_automation_record = validated["session_automation_record"]
            changes["session_automation_record"] = validated["session_automation_record"]
        return changes
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting song settings: " + str(e))
        raise


# --- Navigation / Transport actions ---


def trigger_session_record(song, record_length=None, ctrl=None):
    """Trigger a new session recording, optionally with a fixed bar length."""
    try:
        if record_length is not None:
            song.trigger_session_record(float(record_length))
        else:
            song.trigger_session_record()
        return {"triggered": True, "record_length": record_length}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error triggering session record: " + str(e))
        raise


def navigate_playback(song, action, beats=None, ctrl=None):
    """Navigate playback position: jump_by, scrub_by, or play_selection.

    Args:
        action: 'jump_by', 'scrub_by', or 'play_selection'
        beats: Number of beats to jump/scrub (required for jump_by and scrub_by)
    """
    try:
        if action == "jump_by":
            if beats is None:
                raise ValueError("beats is required for jump_by")
            song.jump_by(float(beats))
            return {"action": "jump_by", "beats": float(beats), "position": song.current_song_time}
        elif action == "scrub_by":
            if beats is None:
                raise ValueError("beats is required for scrub_by")
            song.scrub_by(float(beats))
            return {"action": "scrub_by", "beats": float(beats), "position": song.current_song_time}
        elif action == "play_selection":
            song.play_selection()
            return {"action": "play_selection", "position": song.current_song_time}
        else:
            raise ValueError("action must be 'jump_by', 'scrub_by', or 'play_selection', got '{0}'".format(action))
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error navigating playback: " + str(e))
        raise


# --- View / Selection ---


def select_scene(song, scene_index, ctrl=None):
    """Select a scene by index in Live's Session view."""
    try:
        scenes = list(song.scenes)
        if scene_index < 0 or scene_index >= len(scenes):
            raise IndexError("Scene index {0} out of range (have {1} scenes)".format(
                scene_index, len(scenes)))
        song.view.selected_scene = scenes[scene_index]
        return {"selected_scene_index": scene_index, "scene_name": scenes[scene_index].name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error selecting scene: " + str(e))
        raise


def select_track(song, track_index, track_type="track", ctrl=None):
    """Select a track by index in Live's Session or Arrangement view.

    Args:
        track_index: The index of the track.
        track_type: 'track', 'return', or 'master'.
    """
    try:
        target = get_track(song, track_index, track_type)
        song.view.selected_track = target
        return {"selected_track": target.name, "track_type": track_type}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error selecting track: " + str(e))
        raise


def set_detail_clip(song, track_index, clip_index, ctrl=None):
    """Show a clip in Live's Detail view.

    Args:
        track_index: The track containing the clip.
        clip_index: The clip slot index.
    """
    try:
        _, clip = get_clip(song, track_index, clip_index)
        song.view.detail_clip = clip
        return {
            "track_index": track_index,
            "clip_index": clip_index,
            "clip_name": clip.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting detail clip: " + str(e))
        raise


def set_groove_settings(song, groove_amount=None, groove_index=None,
                         timing_amount=None, quantization_amount=None,
                         random_amount=None, velocity_amount=None, ctrl=None):
    """Set global groove amount or individual groove parameters."""
    try:
        result = {}
        if groove_amount is not None:
            groove_amount = float(groove_amount)
            if groove_amount < 0.0 or groove_amount > 1.0:
                raise ValueError(
                    "groove_amount must be between 0.0 and 1.0, got {0}".format(groove_amount))
            song.groove_amount = groove_amount
            result["groove_amount"] = song.groove_amount
        if groove_index is not None:
            pool = getattr(song, "groove_pool", None)
            if pool is None or not hasattr(pool, "grooves"):
                raise Exception("Groove pool not available")
            grooves = list(pool.grooves)
            groove_index = int(groove_index)
            if groove_index < 0 or groove_index >= len(grooves):
                raise IndexError("Groove index {0} out of range (have {1} grooves)".format(
                    groove_index, len(grooves)))
            groove = grooves[groove_index]
            if timing_amount is not None:
                val = float(timing_amount)
                if val < 0.0 or val > 1.0:
                    raise ValueError("timing_amount must be 0.0-1.0, got {0}".format(val))
                groove.timing_amount = val
            if quantization_amount is not None:
                val = float(quantization_amount)
                if val < 0.0 or val > 1.0:
                    raise ValueError("quantization_amount must be 0.0-1.0, got {0}".format(val))
                groove.quantization_amount = val
            if random_amount is not None:
                val = float(random_amount)
                if val < 0.0 or val > 1.0:
                    raise ValueError("random_amount must be 0.0-1.0, got {0}".format(val))
                groove.random_amount = val
            if velocity_amount is not None:
                val = float(velocity_amount)
                if val < -1.0 or val > 1.0:
                    raise ValueError("velocity_amount must be -1.0-1.0, got {0}".format(val))
                groove.velocity_amount = val
            result["groove_index"] = groove_index
            result["groove_name"] = getattr(groove, "name", "")
            result["timing_amount"] = groove.timing_amount
            result["quantization_amount"] = groove.quantization_amount
            result["random_amount"] = groove.random_amount
            result["velocity_amount"] = groove.velocity_amount
        if not result:
            raise ValueError("No parameters specified")
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting groove settings: " + str(e))
        raise


# --- Scale & Root Note ---


def get_song_scale(song, ctrl=None):
    """Get the song's current scale settings (root note, scale name, mode, intervals)."""
    try:
        result = {
            "root_note": song.root_note,
            "scale_name": song.scale_name,
            "scale_mode": song.scale_mode,
        }
        try:
            result["scale_intervals"] = list(song.scale_intervals)
        except Exception:
            result["scale_intervals"] = None
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting song scale: " + str(e))
        raise


def set_song_scale(song, root_note=None, scale_name=None, scale_mode=None, ctrl=None):
    """Set the song's scale settings.

    Args:
        root_note: 0-11 (C=0, C#=1, ..., B=11)
        scale_name: Scale name as shown in Live (e.g. 'Major', 'Minor', 'Dorian')
        scale_mode: True to enable Scale Mode highlighting
    """
    try:
        changes = {}
        if root_note is not None:
            val = int(root_note)
            if val < 0 or val > 11:
                raise ValueError("root_note must be 0-11, got {0}".format(val))
            song.root_note = val
            changes["root_note"] = val
        if scale_name is not None:
            song.scale_name = str(scale_name)
            changes["scale_name"] = song.scale_name
        if scale_mode is not None:
            song.scale_mode = bool(scale_mode)
            changes["scale_mode"] = bool(scale_mode)
        if not changes:
            raise ValueError("No parameters specified")
        return changes
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting song scale: " + str(e))
        raise


# --- Punch In/Out ---


def set_punch(song, punch_in=None, punch_out=None, count_in_duration=None, ctrl=None):
    """Set punch in/out and count-in settings.

    Args:
        punch_in: Enable/disable punch-in
        punch_out: Enable/disable punch-out
        count_in_duration: 0=None, 1=1 Bar, 2=2 Bars, 3=4 Bars
    """
    try:
        changes = {}
        if punch_in is not None:
            song.punch_in = bool(punch_in)
            changes["punch_in"] = bool(punch_in)
        if punch_out is not None:
            song.punch_out = bool(punch_out)
            changes["punch_out"] = bool(punch_out)
        if count_in_duration is not None:
            val = int(count_in_duration)
            if val < 0 or val > 3:
                raise ValueError("count_in_duration must be 0-3, got {0}".format(val))
            try:
                song.count_in_duration = val
                changes["count_in_duration"] = val
            except Exception:
                changes["count_in_duration_error"] = "read-only in this Live version"
        if not changes:
            raise ValueError("No parameters specified")
        return changes
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting punch: " + str(e))
        raise


# --- Selection State ---


def get_selection_state(song, ctrl=None):
    """Get what is currently selected in Live's UI."""
    try:
        result = {}

        # Selected track
        try:
            sel_track = song.view.selected_track
            if sel_track:
                # Find track index
                for i, t in enumerate(song.tracks):
                    if t == sel_track:
                        result["selected_track"] = {"index": i, "name": t.name, "type": "track"}
                        break
                else:
                    for i, t in enumerate(song.return_tracks):
                        if t == sel_track:
                            result["selected_track"] = {"index": i, "name": t.name, "type": "return"}
                            break
                    else:
                        if sel_track == song.master_track:
                            result["selected_track"] = {"index": 0, "name": "Master", "type": "master"}
        except Exception:
            result["selected_track"] = None

        # Selected scene
        try:
            sel_scene = song.view.selected_scene
            if sel_scene:
                for i, s in enumerate(song.scenes):
                    if s == sel_scene:
                        result["selected_scene"] = {"index": i, "name": s.name}
                        break
        except Exception:
            result["selected_scene"] = None

        # Detail clip
        try:
            detail_clip = song.view.detail_clip
            if detail_clip:
                result["detail_clip"] = {
                    "name": detail_clip.name,
                    "is_midi": detail_clip.is_midi_clip,
                    "is_audio": detail_clip.is_audio_clip,
                    "length": detail_clip.length,
                }
        except Exception:
            result["detail_clip"] = None

        # Draw mode and follow song
        try:
            result["draw_mode"] = song.view.draw_mode
        except Exception:
            result["draw_mode"] = None
        try:
            result["follow_song"] = song.view.follow_song
        except Exception:
            result["follow_song"] = None

        # Highlighted clip slot
        try:
            hcs = song.view.highlighted_clip_slot
            if hcs:
                result["highlighted_clip_slot_has_clip"] = hcs.has_clip
        except Exception:
            pass

        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting selection state: " + str(e))
        raise


# --- Link Sync ---


def get_link_status(song, ctrl=None):
    """Get Ableton Link sync status."""
    try:
        result = {
            "link_enabled": song.is_ableton_link_enabled,
        }
        try:
            result["start_stop_sync_enabled"] = song.is_ableton_link_start_stop_sync_enabled
        except Exception:
            result["start_stop_sync_enabled"] = None
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting link status: " + str(e))
        raise


def set_link_enabled(song, enabled=None, start_stop_sync=None, ctrl=None):
    """Enable/disable Ableton Link and start/stop sync."""
    try:
        changes = {}
        if enabled is not None:
            song.is_ableton_link_enabled = bool(enabled)
            changes["link_enabled"] = bool(enabled)
        if start_stop_sync is not None:
            song.is_ableton_link_start_stop_sync_enabled = bool(start_stop_sync)
            changes["start_stop_sync_enabled"] = bool(start_stop_sync)
        if not changes:
            raise ValueError("No parameters specified")
        return changes
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting link: " + str(e))
        raise


# --- Tuning System ---


def get_tuning_system(song, ctrl=None):
    """Get the current tuning system settings."""
    try:
        ts = song.tuning_system
        result = {}
        try:
            result["name"] = ts.name
        except Exception:
            result["name"] = "Equal Temperament"
        try:
            result["pseudo_octave_in_cents"] = ts.pseudo_octave_in_cents
        except Exception:
            result["pseudo_octave_in_cents"] = 1200.0
        try:
            result["lowest_note"] = ts.lowest_note
        except Exception:
            result["lowest_note"] = None
        try:
            result["highest_note"] = ts.highest_note
        except Exception:
            result["highest_note"] = None
        try:
            result["reference_pitch"] = ts.reference_pitch
        except Exception:
            result["reference_pitch"] = None
        try:
            result["note_tunings"] = ts.note_tunings
        except Exception:
            result["note_tunings"] = None
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("get_tuning_system failed: " + str(e))
        return {
            "name": "Equal Temperament",
            "pseudo_octave_in_cents": 1200.0,
            "lowest_note": None,
            "highest_note": None,
            "reference_pitch": None,
            "note_tunings": None,
            "note": "tuning_system not available in this Live version"
        }


# --- Application View ---


def get_view_state(song, ctrl=None):
    """Get the current state of Live's application views."""
    try:
        import Live
        app = Live.Application.get_application()
        view = app.view
        views = ["Browser", "Arranger", "Session", "Detail", "Detail/Clip", "Detail/DeviceChain"]
        result = {
            "focused_view": view.focused_document_view,
            "browse_mode": view.browse_mode,
            "views": {},
        }
        for v in views:
            try:
                result["views"][v] = view.is_view_visible(v)
            except Exception:
                result["views"][v] = None
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting view state: " + str(e))
        raise


def set_view(song, action, view_name, ctrl=None):
    """Show, hide, or focus a view in Live's UI.

    Args:
        action: 'show', 'hide', 'focus', or 'toggle_browse'
        view_name: 'Browser', 'Arranger', 'Session', 'Detail', 'Detail/Clip', 'Detail/DeviceChain'
    """
    try:
        import Live
        app = Live.Application.get_application()
        view = app.view

        if action == "show":
            view.show_view(view_name)
        elif action == "hide":
            view.hide_view(view_name)
        elif action == "focus":
            view.focus_view(view_name)
        elif action == "toggle_browse":
            view.toggle_browse()
        else:
            raise ValueError("action must be 'show', 'hide', 'focus', or 'toggle_browse', got '{0}'".format(action))

        return {"action": action, "view_name": view_name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting view: " + str(e))
        raise


def zoom_scroll_view(song, action, direction, view_name, modifier_pressed=False, ctrl=None):
    """Zoom or scroll a view in Live's UI.

    Args:
        action: 'zoom' or 'scroll'
        direction: 0=up, 1=down, 2=left, 3=right
        view_name: 'Arranger', 'Session', 'Browser', 'Detail/DeviceChain'
        modifier_pressed: Modifies behavior (e.g. zoom only selected track height)
    """
    try:
        import Live
        app = Live.Application.get_application()
        view = app.view

        direction = int(direction)
        if direction < 0 or direction > 3:
            raise ValueError("direction must be 0-3, got {0}".format(direction))

        if action == "zoom":
            view.zoom_view(direction, view_name, bool(modifier_pressed))
        elif action == "scroll":
            view.scroll_view(direction, view_name, bool(modifier_pressed))
        else:
            raise ValueError("action must be 'zoom' or 'scroll', got '{0}'".format(action))

        return {"action": action, "direction": direction, "view_name": view_name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error zoom/scroll view: " + str(e))
        raise


# --- Playing Clips ---


def get_playing_clips(song, ctrl=None):
    """Get all currently playing/triggered clips across all tracks."""
    try:
        playing = []
        for track_idx, track in enumerate(song.tracks):
            try:
                slot_idx = track.playing_slot_index
                fired_idx = track.fired_slot_index
                if slot_idx >= 0:
                    try:
                        clip = track.clip_slots[slot_idx].clip
                        playing.append({
                            "track_index": track_idx,
                            "track_name": track.name,
                            "clip_index": slot_idx,
                            "clip_name": clip.name if clip else "",
                            "status": "playing",
                        })
                    except Exception:
                        playing.append({
                            "track_index": track_idx,
                            "track_name": track.name,
                            "clip_index": slot_idx,
                            "clip_name": "",
                            "status": "playing",
                        })
                if fired_idx >= 0 and fired_idx != slot_idx:
                    try:
                        clip = track.clip_slots[fired_idx].clip
                        playing.append({
                            "track_index": track_idx,
                            "track_name": track.name,
                            "clip_index": fired_idx,
                            "clip_name": clip.name if clip else "",
                            "status": "triggered",
                        })
                    except Exception:
                        playing.append({
                            "track_index": track_idx,
                            "track_name": track.name,
                            "clip_index": fired_idx,
                            "clip_name": "",
                            "status": "triggered",
                        })
            except Exception:
                pass
        return {"playing_clips": playing, "count": len(playing)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting playing clips: " + str(e))
        raise
