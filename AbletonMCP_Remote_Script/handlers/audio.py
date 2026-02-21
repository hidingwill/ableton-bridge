"""Audio: load samples, warp, crop, reverse, analyze, freeze, export."""

from __future__ import absolute_import, print_function, unicode_literals

import traceback

from ._helpers import get_track, get_clip


def _get_audio_clip(song, track_index, clip_index):
    """Validate indices and return the audio clip, or raise."""
    _, clip = get_clip(song, track_index, clip_index)
    if not hasattr(clip, 'is_audio_clip') or not clip.is_audio_clip:
        raise Exception("Clip is not an audio clip")
    return clip


def get_audio_clip_info(song, track_index, clip_index, ctrl=None):
    """Get information about an audio clip."""
    try:
        clip = _get_audio_clip(song, track_index, clip_index)

        warp_mode_map = {
            0: "beats", 1: "tones", 2: "texture",
            3: "re_pitch", 4: "complex", 5: "complex_pro",
        }
        warp_mode = "unknown"
        if hasattr(clip, "warp_mode"):
            warp_mode = warp_mode_map.get(clip.warp_mode, "unknown")

        raw_path = getattr(clip, "file_path", None)
        safe_name = str(raw_path).replace("\\", "/").rsplit("/", 1)[-1] if raw_path else None

        return {
            "name": clip.name,
            "length": clip.length,
            "is_audio_clip": clip.is_audio_clip,
            "warping": getattr(clip, "warping", None),
            "warp_mode": warp_mode,
            "start_marker": getattr(clip, "start_marker", None),
            "end_marker": getattr(clip, "end_marker", None),
            "loop_start": getattr(clip, "loop_start", None),
            "loop_end": getattr(clip, "loop_end", None),
            "gain": getattr(clip, "gain", None),
            "file_path": safe_name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting audio clip info: " + str(e))
        raise


def set_warp_mode(song, track_index, clip_index, warp_mode, ctrl=None):
    """Set the warp mode for an audio clip."""
    try:
        clip = _get_audio_clip(song, track_index, clip_index)

        warp_mode_map = {
            "beats": 0, "tones": 1, "texture": 2,
            "re_pitch": 3, "complex": 4, "complex_pro": 5,
        }
        if warp_mode.lower() not in warp_mode_map:
            raise ValueError(
                "Invalid warp mode. Must be one of: beats, tones, texture, "
                "re_pitch, complex, complex_pro"
            )
        clip.warp_mode = warp_mode_map[warp_mode.lower()]
        return {"warp_mode": warp_mode.lower(), "warping": clip.warping}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting warp mode: " + str(e))
        raise


def set_clip_warp(song, track_index, clip_index, warping_enabled, ctrl=None):
    """Enable or disable warping for an audio clip."""
    try:
        clip = _get_audio_clip(song, track_index, clip_index)
        clip.warping = warping_enabled
        return {"warping": clip.warping}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting clip warp: " + str(e))
        raise


def reverse_clip(song, track_index, clip_index, ctrl=None):
    """Reverse an audio clip.

    Audio clips don't expose a direct reverse API. If the track hosts a Simpler
    device, we delegate to device.reverse().  Otherwise we raise
    NotImplementedError.
    """
    try:
        _get_audio_clip(song, track_index, clip_index)  # validates indices
        track = get_track(song, track_index)

        # Look for a Simpler device on the track
        for device in track.devices:
            class_name = getattr(device, "class_name", "")
            if class_name == "OriginalSimpler" and hasattr(device, "reverse"):
                device.reverse()
                return {"reversed": True, "method": "simpler_device"}

        raise NotImplementedError(
            "Audio clip reversal requires a Simpler device on the track. "
            "Use Ableton's built-in Reverse (Ctrl+R / Cmd+R) for raw audio clips."
        )
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error reversing clip: " + str(e))
        raise


def analyze_audio_clip(song, track_index, clip_index, ctrl=None):
    """Analyze an audio clip comprehensively."""
    try:
        clip = _get_audio_clip(song, track_index, clip_index)

        warp_mode_map = {
            0: "beats", 1: "tones", 2: "texture",
            3: "re_pitch", 4: "complex", 5: "complex_pro",
        }

        raw_path = getattr(clip, "file_path", None)
        safe_name = str(raw_path).replace("\\", "/").rsplit("/", 1)[-1] if raw_path else None

        analysis = {
            "basic_info": {
                "name": clip.name,
                "length_beats": clip.length,
                "loop_start": getattr(clip, "loop_start", None),
                "loop_end": getattr(clip, "loop_end", None),
                "file_path": safe_name,
            },
            "tempo_rhythm": {
                "warping_enabled": getattr(clip, "warping", None),
                "warp_mode": (
                    warp_mode_map.get(clip.warp_mode, "unknown")
                    if hasattr(clip, "warp_mode") else None
                ),
            },
            "audio_properties": {},
            "frequency_analysis": {},
        }

        # Sample properties
        if hasattr(clip, "sample"):
            sample = clip.sample
            try:
                if hasattr(sample, "length"):
                    analysis["audio_properties"]["sample_length"] = sample.length
                    if hasattr(sample, "sample_rate") and sample.sample_rate > 0:
                        analysis["audio_properties"]["duration_seconds"] = sample.length / sample.sample_rate
                        analysis["audio_properties"]["sample_rate"] = sample.sample_rate
                if hasattr(sample, "bit_depth"):
                    analysis["audio_properties"]["bit_depth"] = sample.bit_depth
                if hasattr(sample, "channels"):
                    analysis["audio_properties"]["channels"] = sample.channels
                    analysis["audio_properties"]["is_stereo"] = sample.channels == 2
            except Exception as sample_err:
                if ctrl:
                    ctrl.log_message(
                        "Error reading sample properties for clip '{0}': {1}".format(
                            getattr(clip, 'name', '?'), sample_err))

        # Frequency hints from warp mode
        if hasattr(clip, "warp_mode"):
            character_map = {
                0: "percussive", 1: "tonal", 2: "textural",
                3: "pitched", 4: "full_spectrum", 5: "full_spectrum",
            }
            analysis["frequency_analysis"]["character"] = character_map.get(clip.warp_mode, "unknown")

        # Summary
        parts = []
        if getattr(clip, "warping", False):
            parts.append("warped audio")
        else:
            parts.append("unwarped audio")
        char = analysis["frequency_analysis"].get("character")
        if char and char != "unknown":
            parts.append(char + " character")
        analysis["summary"] = ", ".join(parts).capitalize()

        return analysis
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error analyzing audio clip: " + str(e))
            ctrl.log_message(traceback.format_exc())
        raise


def freeze_track(song, track_index, ctrl=None):
    """Freeze a track."""
    try:
        track = get_track(song, track_index)

        if getattr(track, "is_frozen", False):
            return {
                "success": True,
                "track_index": track_index,
                "frozen": True,
                "track_name": track.name,
                "message": "Track is already frozen",
            }

        if not getattr(track, "can_be_frozen", False):
            raise ValueError(
                "Track '{0}' cannot be frozen (may be a return/master track or have no devices)".format(track.name))

        return {
            "success": False,
            "requires_manual_action": True,
            "track_index": track_index,
            "frozen": False,
            "track_name": track.name,
            "action_required": "manual_freeze",
            "message": "Track freezing is not available via the Live Object Model API. "
                       "Use Ableton's Edit menu or right-click the track header to freeze.",
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error freezing track: " + str(e))
        raise


def unfreeze_track(song, track_index, ctrl=None):
    """Unfreeze a track."""
    try:
        track = get_track(song, track_index)

        if not getattr(track, "is_frozen", False):
            return {
                "success": True,
                "track_index": track_index,
                "frozen": False,
                "track_name": track.name,
                "message": "Track is not frozen",
            }

        return {
            "success": False,
            "requires_manual_action": True,
            "track_index": track_index,
            "frozen": True,
            "track_name": track.name,
            "action_required": "manual_unfreeze",
            "message": "Track unfreezing is not available via the Live Object Model API. "
                       "Use Ableton's Edit menu or right-click the track header to unfreeze.",
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error unfreezing track: " + str(e))
        raise
