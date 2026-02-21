"""Mixer: volume, pan, mute, solo, arm, sends, return tracks, master."""

from __future__ import absolute_import, print_function, unicode_literals
from ._helpers import get_track


def set_track_volume(song, track_index, volume, ctrl=None):
    """Set track volume."""
    try:
        track = get_track(song, track_index)
        volume_param = track.mixer_device.volume
        clamped = max(volume_param.min, min(volume_param.max, volume))
        volume_param.value = clamped
        return {"track_index": track_index, "volume": volume_param.value}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track volume: " + str(e))
        raise


def set_track_pan(song, track_index, pan, ctrl=None):
    """Set track panning."""
    try:
        track = get_track(song, track_index)
        pan_param = track.mixer_device.panning
        clamped = max(pan_param.min, min(pan_param.max, pan))
        pan_param.value = clamped
        return {"track_index": track_index, "pan": pan_param.value}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track pan: " + str(e))
        raise


def set_track_mute(song, track_index, mute, ctrl=None):
    """Set track mute state."""
    try:
        track = get_track(song, track_index)
        track.mute = bool(mute)
        return {"track_index": track_index, "mute": track.mute}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track mute: " + str(e))
        raise


def set_track_solo(song, track_index, solo, ctrl=None):
    """Set track solo state."""
    try:
        track = get_track(song, track_index)
        track.solo = bool(solo)
        return {"track_index": track_index, "solo": track.solo}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track solo: " + str(e))
        raise


def set_track_arm(song, track_index, arm, ctrl=None):
    """Set the arm (record enable) state of a track."""
    try:
        track = get_track(song, track_index)
        if not track.can_be_armed:
            raise Exception("Track cannot be armed (group track or no input)")
        track.arm = bool(arm)
        return {"track_index": track_index, "arm": track.arm}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track arm: " + str(e))
        raise


def set_track_send(song, track_index, send_index, value, ctrl=None):
    """Set the send level from a track to a return track."""
    try:
        track = get_track(song, track_index)
        sends = track.mixer_device.sends
        if send_index < 0 or send_index >= len(sends):
            raise IndexError("Send index out of range")
        send_param = sends[send_index]
        clamped_value = max(send_param.min, min(send_param.max, value))
        send_param.value = clamped_value
        return {
            "track_index": track_index,
            "send_index": send_index,
            "value": send_param.value,
            "clamped": clamped_value != value,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track send: " + str(e))
        raise


# --- Return track mixer ---


def set_return_track_volume(song, return_track_index, volume, ctrl=None):
    """Set the volume of a return track."""
    try:
        return_track = get_track(song, return_track_index, "return")
        volume_param = return_track.mixer_device.volume
        clamped = max(volume_param.min, min(volume_param.max, volume))
        volume_param.value = clamped
        return {
            "return_track_index": return_track_index,
            "volume": volume_param.value,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting return track volume: " + str(e))
        raise


def set_return_track_pan(song, return_track_index, pan, ctrl=None):
    """Set the panning of a return track."""
    try:
        return_track = get_track(song, return_track_index, "return")
        pan_param = return_track.mixer_device.panning
        clamped = max(pan_param.min, min(pan_param.max, pan))
        pan_param.value = clamped
        return {
            "return_track_index": return_track_index,
            "pan": pan_param.value,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting return track pan: " + str(e))
        raise


def set_return_track_mute(song, return_track_index, mute, ctrl=None):
    """Set the mute state of a return track."""
    try:
        return_track = get_track(song, return_track_index, "return")
        return_track.mute = bool(mute)
        return {
            "return_track_index": return_track_index,
            "mute": return_track.mute,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting return track mute: " + str(e))
        raise


def set_return_track_solo(song, return_track_index, solo, ctrl=None):
    """Set the solo state of a return track."""
    try:
        return_track = get_track(song, return_track_index, "return")
        return_track.solo = bool(solo)
        return {
            "return_track_index": return_track_index,
            "solo": return_track.solo,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting return track solo: " + str(e))
        raise


# --- Crossfade ---


def set_crossfade_assign(song, track_index, assign, ctrl=None):
    """Set A/B crossfade assignment for a track.

    Args:
        assign: 0=NONE, 1=A, 2=B
    """
    try:
        track = get_track(song, track_index)
        assign = int(assign)
        if assign not in (0, 1, 2):
            raise ValueError("assign must be 0 (NONE), 1 (A), or 2 (B)")
        track.mixer_device.crossfade_assign = assign
        _labels = {0: "NONE", 1: "A", 2: "B"}
        return {
            "track_index": track_index,
            "track_name": track.name,
            "crossfade_assign": _labels.get(assign, str(assign)),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting crossfade assign: " + str(e))
        raise


# --- Master track ---


def get_master_track_info(song, ctrl=None):
    """Get detailed information about the master track."""
    try:
        from . import devices as dev_mod
        master = song.master_track
        devices = []
        for device_index, device in enumerate(master.devices):
            devices.append({
                "index": device_index,
                "name": device.name,
                "class_name": device.class_name,
                "type": dev_mod.get_device_type(device, ctrl),
            })
        return {
            "name": "Master",
            "volume": master.mixer_device.volume.value,
            "panning": master.mixer_device.panning.value,
            "devices": devices,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting master track info: " + str(e))
        raise


def set_master_volume(song, volume, ctrl=None):
    """Set the volume of the master track."""
    try:
        master = song.master_track
        volume_param = master.mixer_device.volume
        clamped_value = max(volume_param.min, min(volume_param.max, volume))
        volume_param.value = clamped_value
        return {
            "volume": volume_param.value,
            "clamped": clamped_value != volume,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting master volume: " + str(e))
        raise


# --- Read-only info ---


def get_scenes(song, ctrl=None):
    """Get information about all scenes."""
    try:
        scenes = []
        for i, scene in enumerate(song.scenes):
            scenes.append({
                "index": i,
                "name": scene.name,
                "tempo": scene.tempo if hasattr(scene, 'tempo') else None,
                "is_triggered": scene.is_triggered if hasattr(scene, 'is_triggered') else False,
                "color_index": scene.color_index if hasattr(scene, 'color_index') else 0,
            })
        return {"scenes": scenes, "count": len(scenes)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting scenes: " + str(e))
        raise


def get_return_tracks(song, ctrl=None):
    """Get information about all return tracks."""
    try:
        from . import devices as dev_mod
        return_tracks = []
        for i, track in enumerate(song.return_tracks):
            devices = []
            for device_index, device in enumerate(track.devices):
                devices.append({
                    "index": device_index,
                    "name": device.name,
                    "class_name": device.class_name,
                    "type": dev_mod.get_device_type(device, ctrl),
                })
            sends = []
            for send_index, send in enumerate(track.mixer_device.sends):
                sends.append({
                    "index": send_index,
                    "name": send.name if hasattr(send, 'name') else "Send " + chr(65 + send_index),
                    "value": send.value,
                })
            return_tracks.append({
                "index": i,
                "name": track.name,
                "volume": track.mixer_device.volume.value,
                "panning": track.mixer_device.panning.value,
                "mute": track.mute,
                "solo": track.solo,
                "devices": devices,
                "sends": sends,
            })
        return {"return_tracks": return_tracks, "count": len(return_tracks)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting return tracks: " + str(e))
        raise


def get_return_track_info(song, return_track_index, ctrl=None):
    """Get detailed information about a specific return track."""
    try:
        from . import devices as dev_mod
        track = get_track(song, return_track_index, "return")
        devices = []
        for device_index, device in enumerate(track.devices):
            devices.append({
                "index": device_index,
                "name": device.name,
                "class_name": device.class_name,
                "type": dev_mod.get_device_type(device, ctrl),
            })
        sends = []
        for send_index, send in enumerate(track.mixer_device.sends):
            sends.append({
                "index": send_index,
                "name": send.name if hasattr(send, 'name') else "Send " + chr(65 + send_index),
                "value": send.value,
            })
        return {
            "index": return_track_index,
            "name": track.name,
            "volume": track.mixer_device.volume.value,
            "panning": track.mixer_device.panning.value,
            "mute": track.mute,
            "solo": track.solo,
            "devices": devices,
            "sends": sends,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting return track info: " + str(e))
        raise
