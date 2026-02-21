"""Track creation, deletion, properties, arm, color, group."""

from __future__ import absolute_import, print_function, unicode_literals

from ._helpers import get_track, get_clip


def get_track_info(song, track_index, ctrl=None):
    """Get information about a track."""
    try:
        track = get_track(song, track_index)

        # Get clip slots
        clip_slots = []
        try:
            for slot_index, slot in enumerate(track.clip_slots):
                clip_info = None
                try:
                    if slot.has_clip:
                        clip = slot.clip
                        clip_info = {
                            "name": clip.name,
                            "length": clip.length if hasattr(clip, 'length') else 0,
                            "is_playing": clip.is_playing if hasattr(clip, 'is_playing') else False,
                            "is_recording": clip.is_recording if hasattr(clip, 'is_recording') else False,
                        }
                except Exception:
                    clip_info = None
                clip_slots.append({
                    "index": slot_index,
                    "has_clip": slot.has_clip,
                    "clip": clip_info,
                })
        except Exception:
            pass

        # Get devices
        from . import devices as dev_mod
        devices_list = []
        try:
            for device_index, device in enumerate(track.devices):
                devices_list.append({
                    "index": device_index,
                    "name": device.name,
                    "class_name": device.class_name,
                    "type": dev_mod.get_device_type(device, ctrl),
                })
        except Exception:
            pass

        # Safely read properties -- group tracks don't support all of these
        try:
            arm = track.arm if track.can_be_armed else False
        except Exception:
            arm = False

        try:
            is_group = track.is_foldable
        except Exception:
            is_group = False

        try:
            is_audio = track.has_audio_input
        except Exception:
            is_audio = False

        try:
            is_midi = track.has_midi_input
        except Exception:
            is_midi = False

        # Group relationships
        try:
            is_grouped = track.is_grouped
        except Exception:
            is_grouped = False

        group_track_index = None
        if is_grouped:
            try:
                gt = track.group_track
                if gt:
                    for i, t in enumerate(song.tracks):
                        if t == gt:
                            group_track_index = i
                            break
            except Exception:
                pass

        try:
            is_visible = track.is_visible
        except Exception:
            is_visible = True

        try:
            is_showing_chains = track.is_showing_chains
        except Exception:
            is_showing_chains = False

        try:
            can_show_chains = track.can_show_chains
        except Exception:
            can_show_chains = False

        try:
            playing_slot_index = track.playing_slot_index
        except Exception:
            playing_slot_index = -1

        try:
            fired_slot_index = track.fired_slot_index
        except Exception:
            fired_slot_index = -1

        result = {
            "index": track_index,
            "name": track.name,
            "is_group_track": is_group,
            "is_audio_track": is_audio,
            "is_midi_track": is_midi,
            "mute": track.mute,
            "solo": track.solo,
            "arm": arm,
            "volume": track.mixer_device.volume.value,
            "panning": track.mixer_device.panning.value,
            "is_grouped": is_grouped,
            "group_track_index": group_track_index,
            "is_visible": is_visible,
            "is_showing_chains": is_showing_chains,
            "can_show_chains": can_show_chains,
            "playing_slot_index": playing_slot_index,
            "fired_slot_index": fired_slot_index,
            "clip_slots": clip_slots,
            "devices": devices_list,
        }
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting track info: " + str(e))
        raise


def create_midi_track(song, index, ctrl=None):
    """Create a new MIDI track at the specified index."""
    try:
        song.create_midi_track(index)
        new_track_index = len(song.tracks) - 1 if index == -1 else index
        new_track = song.tracks[new_track_index]
        return {"index": new_track_index, "name": new_track.name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating MIDI track: " + str(e))
        raise


def create_audio_track(song, index, ctrl=None):
    """Create a new audio track at the specified index."""
    try:
        song.create_audio_track(index)
        new_track_index = len(song.tracks) - 1 if index == -1 else index
        new_track = song.tracks[new_track_index]
        return {"index": new_track_index, "name": new_track.name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating audio track: " + str(e))
        raise


def set_track_name(song, track_index, name, ctrl=None):
    """Set the name of a track."""
    try:
        track = get_track(song, track_index)
        track.name = name
        return {"name": track.name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track name: " + str(e))
        raise


def delete_track(song, track_index, ctrl=None):
    """Delete a track from the session."""
    try:
        track = get_track(song, track_index)
        track_name = track.name
        song.delete_track(track_index)
        return {
            "deleted": True,
            "track_name": track_name,
            "track_index": track_index,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error deleting track: " + str(e))
        raise


def duplicate_track(song, track_index, ctrl=None):
    """Duplicate a track with all its devices and clips."""
    try:
        track = get_track(song, track_index)
        source_name = track.name
        song.duplicate_track(track_index)
        new_track_index = track_index + 1
        new_track = song.tracks[new_track_index]
        return {
            "duplicated": True,
            "source_index": track_index,
            "source_name": source_name,
            "new_index": new_track_index,
            "new_name": new_track.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error duplicating track: " + str(e))
        raise


# --- New commands from MacWhite ---


def create_return_track(song, ctrl=None):
    """Create a new return track."""
    try:
        song.create_return_track()
        new_index = len(song.return_tracks) - 1
        new_track = song.return_tracks[new_index]
        return {"index": new_index, "name": new_track.name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating return track: " + str(e))
        raise


def set_track_color(song, track_index, color_index, ctrl=None):
    """Set track color."""
    try:
        track = get_track(song, track_index)
        track.color_index = color_index
        return {"track_index": track_index, "color_index": track.color_index}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track color: " + str(e))
        raise


def arm_track(song, track_index, ctrl=None):
    """Arm a track for recording."""
    try:
        track = get_track(song, track_index)
        if not track.can_be_armed:
            raise Exception("Track cannot be armed (may be a group track or lack input)")
        track.arm = True
        return {
            "track_index": track_index,
            "track_name": track.name,
            "armed": track.arm,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error arming track: " + str(e))
        raise


def disarm_track(song, track_index, ctrl=None):
    """Disarm a track from recording."""
    try:
        track = get_track(song, track_index)
        if not track.can_be_armed:
            return {
                "track_index": track_index,
                "track_name": track.name,
                "armed": False,
            }
        track.arm = False
        return {
            "track_index": track_index,
            "track_name": track.name,
            "armed": track.arm,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error disarming track: " + str(e))
        raise


def group_tracks(song, track_indices, name, ctrl=None):
    """Group tracks — not supported by Remote Script API. Selects first track and returns guidance."""
    if not track_indices or len(track_indices) == 0:
        raise ValueError("No tracks specified")
    for i in track_indices:
        if i < 0 or i >= len(song.tracks):
            raise IndexError("Track index {0} out of range".format(i))
    song.view.selected_track = song.tracks[track_indices[0]]
    msg = ("Track grouping is not available via the Remote Script API. "
           "Select the tracks in Ableton and use Edit > Group Tracks (Ctrl+G / Cmd+G).")
    if ctrl:
        ctrl.log_message(
            "group_tracks: '{0}' — selected track {1}. {2}".format(
                name, track_indices[0], msg))
    raise NotImplementedError(msg)


def get_all_tracks_info(song, ctrl=None):
    """Get summary info for all tracks at once."""
    try:
        tracks_list = []
        for i, track in enumerate(song.tracks):
            devices_list = []
            for d in track.devices:
                devices_list.append({"name": d.name, "class_name": d.class_name})
            track_info = {
                "index": i,
                "name": track.name,
                "is_audio": track.has_audio_input if hasattr(track, 'has_audio_input') else False,
                "is_midi": track.has_midi_input if hasattr(track, 'has_midi_input') else False,
                "mute": track.mute,
                "solo": track.solo,
                "volume": track.mixer_device.volume.value,
                "panning": track.mixer_device.panning.value,
                "color_index": track.color_index if hasattr(track, 'color_index') else 0,
                "devices": devices_list,
            }
            try:
                track_info["arm"] = track.arm if track.can_be_armed else False
            except Exception:
                track_info["arm"] = False
            try:
                track_info["is_group_track"] = track.is_foldable
            except Exception:
                track_info["is_group_track"] = False
            tracks_list.append(track_info)
        return {"tracks": tracks_list, "count": len(tracks_list)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting all tracks info: " + str(e))
        raise


def get_return_tracks_info(song, ctrl=None):
    """Get info for all return tracks."""
    try:
        returns = []
        for i, track in enumerate(song.return_tracks):
            devices_list = []
            for d in track.devices:
                devices_list.append({"name": d.name, "class_name": d.class_name})
            returns.append({
                "index": i,
                "name": track.name,
                "volume": track.mixer_device.volume.value,
                "panning": track.mixer_device.panning.value,
                "color_index": track.color_index if hasattr(track, 'color_index') else 0,
                "devices": devices_list,
            })
        return {"return_tracks": returns, "count": len(returns)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting return tracks info: " + str(e))
        raise


def get_track_routing(song, track_index, ctrl=None):
    """Get current input/output routing and available options for a track."""
    try:
        track = get_track(song, track_index)
        result = {
            "track_index": track_index,
            "track_name": track.name,
        }
        # Current routing
        try:
            result["input_routing_type"] = str(track.input_routing_type.display_name)
        except Exception:
            result["input_routing_type"] = None
        try:
            result["input_routing_channel"] = str(track.input_routing_channel.display_name)
        except Exception:
            result["input_routing_channel"] = None
        try:
            result["output_routing_type"] = str(track.output_routing_type.display_name)
        except Exception:
            result["output_routing_type"] = None
        try:
            result["output_routing_channel"] = str(track.output_routing_channel.display_name)
        except Exception:
            result["output_routing_channel"] = None
        # Available input types
        try:
            result["available_input_types"] = [
                str(r.display_name) for r in track.available_input_routing_types
            ]
        except Exception:
            result["available_input_types"] = []
        # Available output types
        try:
            result["available_output_types"] = [
                str(r.display_name) for r in track.available_output_routing_types
            ]
        except Exception:
            result["available_output_types"] = []
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting track routing: " + str(e))
        raise


def set_track_monitoring(song, track_index, state, ctrl=None):
    """Set the monitoring state of a track.

    Args:
        state: 0=IN (always monitor), 1=AUTO (monitor when armed), 2=OFF (never monitor)
    """
    try:
        track = get_track(song, track_index)
        state = int(state)
        if state < 0 or state > 2:
            raise ValueError("Monitoring state must be 0 (IN), 1 (AUTO), or 2 (OFF)")
        track.current_monitoring_state = state
        return {
            "track_index": track_index,
            "track_name": track.name,
            "monitoring_state": track.current_monitoring_state,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track monitoring: " + str(e))
        raise


def create_midi_track_with_simpler(song, track_index, clip_index, ctrl=None):
    """Create a new MIDI track with a Simpler containing an audio clip's sample."""
    try:
        _, clip = get_clip(song, track_index, clip_index)
        if not clip.is_audio_clip:
            raise ValueError("Clip is not an audio clip")
        try:
            from Live.Conversions import create_midi_track_with_simpler as _create
        except ImportError as e:
            raise Exception("create_midi_track_with_simpler requires Live 12+") from e
        _create(song, clip)
        return {
            "created": True,
            "source_clip": clip.name,
            "source_track_index": track_index,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating MIDI track with Simpler: " + str(e))
        raise


def get_track_meters(song, track_index=None, ctrl=None):
    """Get live output meter levels and playing slot info for one or all tracks."""
    try:
        tracks_data = []
        if track_index is not None:
            get_track(song, track_index)  # validate bounds
            indices = [track_index]
        else:
            indices = range(len(song.tracks))
        for i in indices:
            track = song.tracks[i]
            info = {
                "index": i,
                "name": track.name,
            }
            try:
                info["output_meter_left"] = round(track.output_meter_left, 4)
                info["output_meter_right"] = round(track.output_meter_right, 4)
            except Exception:
                try:
                    info["output_meter_level"] = round(track.output_meter_level, 4)
                except Exception:
                    info["output_meter_level"] = None
            try:
                info["playing_slot_index"] = track.playing_slot_index
            except Exception:
                info["playing_slot_index"] = -1
            try:
                info["fired_slot_index"] = track.fired_slot_index
            except Exception:
                info["fired_slot_index"] = -1
            tracks_data.append(info)
        if track_index is not None:
            return tracks_data[0]
        return {"tracks": tracks_data, "count": len(tracks_data)}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting track meters: " + str(e))
        raise


def set_track_fold(song, track_index, fold_state, ctrl=None):
    """Collapse or expand a group track.

    Args:
        fold_state: True to fold (collapse), False to unfold (expand).
    """
    try:
        track = get_track(song, track_index)
        if not track.is_foldable:
            raise Exception("Track '{0}' is not a group track (not foldable)".format(track.name))
        track.fold_state = bool(fold_state)
        return {
            "track_index": track_index,
            "track_name": track.name,
            "fold_state": track.fold_state,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track fold: " + str(e))
        raise


def set_track_routing(song, track_index, input_type=None, input_channel=None,
                      output_type=None, output_channel=None, ctrl=None):
    """Set track input/output routing by display name.

    Args:
        input_type: Display name of input routing type (e.g. 'Ext. In', 'No Input')
        input_channel: Display name of input channel (e.g. '1/2', 'All Channels')
        output_type: Display name of output routing type (e.g. 'Master', 'Sends Only')
        output_channel: Display name of output channel
    """
    try:
        track = get_track(song, track_index)
        changes = {}

        # Phase 1: resolve and apply routing *types* first, since
        # available channels depend on the currently active type.
        if input_type is not None:
            for rt in track.available_input_routing_types:
                if str(rt.display_name) == input_type:
                    track.input_routing_type = rt
                    changes["input_routing_type"] = input_type
                    break
            else:
                raise ValueError("Input type '{0}' not found".format(input_type))
        if output_type is not None:
            for rt in track.available_output_routing_types:
                if str(rt.display_name) == output_type:
                    track.output_routing_type = rt
                    changes["output_routing_type"] = output_type
                    break
            else:
                raise ValueError("Output type '{0}' not found".format(output_type))

        # Phase 2: resolve and apply channels against the (now-refreshed)
        # available channel lists.
        if input_channel is not None:
            for ch in track.available_input_routing_channels:
                if str(ch.display_name) == input_channel:
                    track.input_routing_channel = ch
                    changes["input_routing_channel"] = input_channel
                    break
            else:
                raise ValueError("Input channel '{0}' not found".format(input_channel))
        if output_channel is not None:
            for ch in track.available_output_routing_channels:
                if str(ch.display_name) == output_channel:
                    track.output_routing_channel = ch
                    changes["output_routing_channel"] = output_channel
                    break
            else:
                raise ValueError("Output channel '{0}' not found".format(output_channel))

        changes["track_index"] = track_index
        changes["track_name"] = track.name
        return changes
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting track routing: " + str(e))
        raise


# --- Take Lanes ---


def get_take_lanes(song, track_index, ctrl=None):
    """Get take lanes for a track (used for comping in Arrangement)."""
    try:
        track = get_track(song, track_index)
        lanes = []
        try:
            for i, lane in enumerate(track.take_lanes):
                clips = []
                try:
                    for clip in lane.arrangement_clips:
                        clips.append({
                            "name": clip.name,
                            "start_time": clip.start_time,
                            "length": clip.length,
                        })
                except Exception:
                    pass
                lanes.append({
                    "index": i,
                    "name": lane.name,
                    "clip_count": len(clips),
                    "clips": clips,
                })
        except Exception:
            pass
        return {
            "track_index": track_index,
            "track_name": track.name,
            "take_lanes": lanes,
            "count": len(lanes),
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting take lanes: " + str(e))
        raise


def create_take_lane(song, track_index, ctrl=None):
    """Create a new take lane for a track."""
    try:
        track = get_track(song, track_index)
        track.create_take_lane()
        lane_count = len(list(track.take_lanes))
        return {
            "created": True,
            "track_index": track_index,
            "take_lane_count": lane_count,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating take lane: " + str(e))
        raise


# --- Insert Device by Name (Live 12.3+) ---


def insert_device(song, track_index, device_name, target_index=None, ctrl=None):
    """Insert a native Live device by name into a track's device chain.

    Args:
        track_index: Track to insert device into.
        device_name: Name of the device as shown in Live's UI.
        target_index: Position in the device chain (None = end of chain).
    Note: Only native Live devices are supported. M4L and plugins are not.
    """
    try:
        track = get_track(song, track_index)
        if not hasattr(track, "insert_device"):
            msg = "insert_device not supported (requires Live 12.3+)"
            if ctrl:
                ctrl.log_message(msg)
            return {
                "inserted": False,
                "reason": msg,
                "track_index": track_index,
            }
        if target_index is not None:
            track.insert_device(str(device_name), int(target_index))
        else:
            track.insert_device(str(device_name))
        return {
            "inserted": True,
            "device_name": device_name,
            "track_index": track_index,
            "track_name": track.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error inserting device: " + str(e))
        raise
