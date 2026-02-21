"""Automation: clip automation, track-level automation, arrangement time editing."""

from __future__ import absolute_import, print_function, unicode_literals

import re
import traceback

from ._helpers import get_track, get_clip

_RE_SEND_NAME = re.compile(r'^send\s*([a-z])$')


def _find_parameter(song, track_index, parameter_name):
    """Find a track mixer or device parameter by name."""
    track = get_track(song, track_index)
    lower = parameter_name.lower()

    # Check mixer parameters
    if lower == "volume":
        return track.mixer_device.volume
    elif lower in ("pan", "panning"):
        return track.mixer_device.panning

    # Check send parameters — accept "send a", "send_a", "senda", etc.
    m = _RE_SEND_NAME.match(lower.replace("_", ""))
    if m:
        send_index = ord(m.group(1).upper()) - ord("A")
        if 0 <= send_index < len(track.mixer_device.sends):
            return track.mixer_device.sends[send_index]

    # Check device parameters
    for device in track.devices:
        for p in device.parameters:
            if p.name.lower() == lower:
                return p

    raise ValueError("Parameter '{0}' not found".format(parameter_name))


def create_clip_automation(song, track_index, clip_index, parameter_name, automation_points, ctrl=None):
    """Create automation for a parameter within a clip."""
    try:
        track, clip = get_clip(song, track_index, clip_index)

        # Find the parameter
        param = _find_parameter(song, track_index, parameter_name)

        if not hasattr(clip, 'automation_envelope'):
            if hasattr(clip, 'create_automation_envelope'):
                envelope = clip.create_automation_envelope(param)
            else:
                raise Exception("Clip does not support automation envelopes")
        else:
            envelope = clip.automation_envelope(param)

        if envelope is None:
            if hasattr(clip, 'create_automation_envelope'):
                envelope = clip.create_automation_envelope(param)
            if envelope is None:
                raise Exception("Could not get automation envelope for parameter '{0}'".format(parameter_name))

        # Clear existing automation so we start with a clean envelope
        if hasattr(envelope, 'clear'):
            try:
                envelope.clear()
            except Exception:
                pass

        # Insert breakpoints — Ableton linearly interpolates between them.
        # Use duration=0 to create simple breakpoints (not held steps).
        clip_length = clip.length
        for point in automation_points:
            time_val = float(point.get("time", 0.0))
            time_val = max(0.0, min(clip_length - 0.001, time_val))
            value = float(point.get("value", 0.0))
            clamped = max(param.min, min(param.max, value))
            envelope.insert_step(time_val, 0.0, clamped)

        return {
            "parameter": parameter_name,
            "track_index": track_index,
            "clip_index": clip_index,
            "points_added": len(automation_points),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating clip automation: " + str(e))
            ctrl.log_message(traceback.format_exc())
        raise


def get_clip_automation(song, track_index, clip_index, parameter_name, ctrl=None):
    """Read automation envelope from a clip."""
    try:
        track, clip = get_clip(song, track_index, clip_index)

        param = _find_parameter(song, track_index, parameter_name)

        if not hasattr(clip, 'automation_envelope'):
            return {"has_automation": False, "parameter": parameter_name, "reason": "Clip does not support automation envelopes"}

        envelope = clip.automation_envelope(param)
        if envelope is None:
            return {"has_automation": False, "parameter": parameter_name}

        # Sample the envelope at evenly-spaced points
        num_samples = 64
        clip_len = clip.length
        if clip_len <= 0:
            return {"has_automation": False, "parameter": parameter_name, "reason": "Clip has zero length"}

        points = []
        step = clip_len / num_samples
        for i in range(num_samples):
            t = i * step
            try:
                val = envelope.value_at_time(t)
                points.append({"time": round(t, 4), "value": round(val, 4)})
            except Exception:
                pass

        return {
            "has_automation": True,
            "parameter": parameter_name,
            "param_min": param.min,
            "param_max": param.max,
            "clip_length": clip_len,
            "point_count": len(points),
            "points": points,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting clip automation: " + str(e))
        raise


def clear_clip_automation(song, track_index, clip_index, parameter_name, ctrl=None):
    """Clear automation for a specific parameter in a clip."""
    try:
        track, clip = get_clip(song, track_index, clip_index)

        param = _find_parameter(song, track_index, parameter_name)

        if not hasattr(clip, 'automation_envelope'):
            raise Exception("Clip does not support automation envelopes")

        envelope = clip.automation_envelope(param)
        if envelope is None:
            return {"cleared": False, "parameter": parameter_name, "reason": "No automation envelope found"}

        if hasattr(envelope, 'clear'):
            envelope.clear()
            return {"cleared": True, "parameter": parameter_name}
        else:
            raise Exception("Envelope does not support clear()")
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error clearing clip automation: " + str(e))
        raise


def list_clip_automated_params(song, track_index, clip_index, ctrl=None):
    """List all parameters that have automation in a clip."""
    try:
        track, clip = get_clip(song, track_index, clip_index)

        if not hasattr(clip, 'automation_envelope'):
            return {"automated_parameters": [], "count": 0, "reason": "Clip does not support automation envelopes"}

        automated = []

        # Check mixer parameters
        for name, param in [("Volume", track.mixer_device.volume), ("Pan", track.mixer_device.panning)]:
            try:
                env = clip.automation_envelope(param)
                if env is not None:
                    automated.append({"name": name, "source": "Mixer"})
            except Exception:
                pass

        # Check send parameters
        for i, send in enumerate(track.mixer_device.sends):
            try:
                env = clip.automation_envelope(send)
                if env is not None:
                    automated.append({"name": "Send " + chr(65 + i), "source": "Mixer"})
            except Exception:
                pass

        # Check device parameters
        for dev_idx, device in enumerate(track.devices):
            for param in device.parameters:
                try:
                    env = clip.automation_envelope(param)
                    if env is not None:
                        automated.append({
                            "name": param.name,
                            "source": device.name,
                            "device_index": dev_idx,
                        })
                except Exception:
                    pass

        return {"automated_parameters": automated, "count": len(automated)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error listing automated params: " + str(e))
        raise


# --- New: Track-level automation and arrangement time editing (from MacWhite) ---


def create_track_automation(song, track_index, parameter_name, automation_points, ctrl=None):
    """Create automation for a track parameter (arrangement-level).

    Uses arrangement clips to access the automation envelope for the given
    parameter.  Raises ValueError if no arrangement clip covers the target time.
    """
    try:
        track = get_track(song, track_index)
        parameter = _find_parameter(song, track_index, parameter_name)

        # Find an arrangement clip that covers the automation time range.
        # arrangement_clips() is available on tracks in Live 11+.
        if not hasattr(track, "arrangement_clips"):
            raise Exception(
                "Arrangement automation requires Live 11+ (track.arrangement_clips not available)"
            )

        arr_clips = list(track.arrangement_clips)
        if not arr_clips:
            raise Exception(
                "No arrangement clips on track {0} — record or place a clip first".format(track_index)
            )

        # Determine the time span the caller wants to automate
        times = [float(p.get("time", 0.0)) for p in automation_points]
        if not times:
            return {
                "parameter": parameter_name,
                "track_index": track_index,
                "points_added": 0,
            }
        t_min = min(times)

        # Pick the first arrangement clip whose range covers t_min
        target_clip = None
        for ac in arr_clips:
            clip_start = ac.start_time if hasattr(ac, "start_time") else 0.0
            clip_end = ac.end_time if hasattr(ac, "end_time") else (clip_start + ac.length)
            if clip_start <= t_min < clip_end:
                target_clip = ac
                break

        if target_clip is None:
            ranges = ["{0}-{1}".format(
                ac.start_time if hasattr(ac, "start_time") else "?",
                ac.end_time if hasattr(ac, "end_time") else "?") for ac in arr_clips]
            raise ValueError(
                "No arrangement clip covers time {0}. Clip ranges: [{1}]".format(
                    t_min, ", ".join(ranges)))

        # Validate all points against clip bounds
        clip_start = target_clip.start_time if hasattr(target_clip, "start_time") else 0.0
        clip_end = target_clip.end_time if hasattr(target_clip, "end_time") else (clip_start + target_clip.length)
        t_max = max(times)
        if t_max >= clip_end:
            raise ValueError(
                "Automation point at time {0} exceeds clip end {1}. "
                "All points must fall within clip range [{2}, {3})".format(
                    t_max, clip_end, clip_start, clip_end))

        # Get or create the automation envelope on that clip
        envelope = None
        if hasattr(target_clip, "automation_envelope"):
            envelope = target_clip.automation_envelope(parameter)
        if envelope is None and hasattr(target_clip, "create_automation_envelope"):
            envelope = target_clip.create_automation_envelope(parameter)
        if envelope is None:
            raise Exception(
                "Could not get automation envelope for '{0}' on arrangement clip".format(parameter_name)
            )

        for point in automation_points:
            time_val = max(clip_start, min(clip_end - 0.001, float(point.get("time", 0.0))))
            value = max(parameter.min, min(parameter.max, float(point.get("value", 0.0))))
            envelope.insert_step(time_val, 0.0, value)

        return {
            "parameter": parameter_name,
            "track_index": track_index,
            "points_added": len(automation_points),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating track automation: " + str(e))
            ctrl.log_message(traceback.format_exc())
        raise


def clear_track_automation(song, track_index, parameter_name, start_time, end_time, ctrl=None):
    """Clear automation for a parameter in an arrangement time range.

    Finds the arrangement clip at the given time range and clears (flattens)
    the automation envelope for the parameter by inserting a constant step
    at the parameter's current value.
    """
    try:
        start_time = float(start_time)
        end_time = float(end_time)

        track = get_track(song, track_index)
        parameter = _find_parameter(song, track_index, parameter_name)

        if end_time <= start_time:
            msg = "End time must be greater than start time"
            if ctrl:
                ctrl.log_message("Invalid clear range: " + msg)
            raise ValueError(msg)

        if not hasattr(track, "arrangement_clips"):
            raise Exception(
                "Arrangement automation requires Live 11+ (track.arrangement_clips not available)"
            )

        arr_clips = list(track.arrangement_clips)
        if not arr_clips:
            raise Exception(
                "No arrangement clips on track {0}".format(track_index)
            )

        # Find the arrangement clip that covers start_time
        target_clip = None
        clip_end = None
        for ac in arr_clips:
            clip_start = ac.start_time if hasattr(ac, "start_time") else 0.0
            clip_end = ac.end_time if hasattr(ac, "end_time") else (clip_start + ac.length)
            if clip_start <= start_time < clip_end:
                target_clip = ac
                break
        if target_clip is None:
            ranges = ["{0}-{1}".format(
                ac.start_time if hasattr(ac, "start_time") else "?",
                ac.end_time if hasattr(ac, "end_time") else "?") for ac in arr_clips]
            raise ValueError(
                "No arrangement clip covers time {0}. Clip ranges: [{1}]".format(
                    start_time, ", ".join(ranges)))

        # Clamp end_time to clip boundary
        if end_time > clip_end:
            end_time = clip_end

        envelope = None
        if hasattr(target_clip, "automation_envelope"):
            envelope = target_clip.automation_envelope(parameter)
        if envelope is None:
            return {"cleared": False, "parameter": parameter_name, "reason": "No automation envelope found"}

        current_value = parameter.value
        envelope.insert_step(start_time, end_time - start_time, current_value)

        return {
            "parameter": parameter_name,
            "track_index": track_index,
            "cleared_from": start_time,
            "cleared_to": end_time,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error clearing track automation: " + str(e))
        raise


def delete_time(song, start_time, end_time, ctrl=None):
    """Delete a section of time from the arrangement."""
    try:
        start_time = float(start_time)
        end_time = float(end_time)
        if start_time >= end_time:
            raise ValueError("Start time must be less than end time")
        song.delete_time(start_time, end_time - start_time)
        return {
            "deleted_from": start_time,
            "deleted_to": end_time,
            "deleted_length": end_time - start_time,
        }
    except (TypeError, ValueError) as e:
        if ctrl:
            ctrl.log_message("Error deleting time: " + str(e))
        raise
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error deleting time: " + str(e))
        raise


def duplicate_time(song, start_time, end_time, ctrl=None):
    """Duplicate a section of time in the arrangement."""
    try:
        start_time = float(start_time)
        end_time = float(end_time)
        if start_time >= end_time:
            raise ValueError("Start time must be less than end time")
        song.duplicate_time(start_time, end_time - start_time)
        return {
            "duplicated_from": start_time,
            "duplicated_to": end_time,
            "duplicated_length": end_time - start_time,
            "pasted_at": end_time,
        }
    except (TypeError, ValueError) as e:
        if ctrl:
            ctrl.log_message("Error duplicating time: " + str(e))
        raise
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error duplicating time: " + str(e))
        raise


def insert_silence(song, position, length, ctrl=None):
    """Insert silence at a position in the arrangement."""
    try:
        position = float(position)
        length = float(length)
        if length <= 0:
            raise ValueError("Length must be greater than 0")
        song.insert_time(position, length)
        return {"inserted_at": position, "inserted_length": length}
    except (TypeError, ValueError) as e:
        if ctrl:
            ctrl.log_message("Error inserting silence: " + str(e))
        raise
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error inserting silence: " + str(e))
        raise
