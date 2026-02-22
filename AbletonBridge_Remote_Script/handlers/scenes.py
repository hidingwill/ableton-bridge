"""Scene create/delete/duplicate, trigger, rename."""

from __future__ import absolute_import, print_function, unicode_literals

from ._helpers import get_scene


def create_scene(song, index, name="", ctrl=None):
    """Create a new scene."""
    try:
        if index < 0:
            index = len(song.scenes)
        song.create_scene(index)
        scene = song.scenes[index]
        if name:
            scene.name = name
        return {"index": index, "name": scene.name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error creating scene: " + str(e))
        raise


def delete_scene(song, scene_index, ctrl=None):
    """Delete a scene from the session."""
    try:
        scene = get_scene(song, scene_index)
        scene_name = scene.name
        song.delete_scene(scene_index)
        return {
            "deleted": True,
            "scene_name": scene_name,
            "scene_index": scene_index,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error deleting scene: " + str(e))
        raise


def duplicate_scene(song, scene_index, ctrl=None):
    """Duplicate a scene."""
    try:
        get_scene(song, scene_index)
        song.duplicate_scene(scene_index)
        new_index = scene_index + 1
        return {"new_index": new_index, "name": song.scenes[new_index].name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error duplicating scene: " + str(e))
        raise


def fire_scene(song, scene_index, ctrl=None):
    """Fire (launch) a scene."""
    try:
        scene = get_scene(song, scene_index)
        scene.fire()
        return {"triggered": True, "scene_index": scene_index}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error firing scene: " + str(e))
        raise


def set_scene_name(song, scene_index, name, ctrl=None):
    """Set a scene's name."""
    try:
        scene = get_scene(song, scene_index)
        scene.name = name
        return {"scene_index": scene_index, "name": name}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting scene name: " + str(e))
        raise


def get_scene_follow_actions(song, scene_index, ctrl=None):
    """Get follow action settings for a scene."""
    try:
        scene = get_scene(song, scene_index)
        result = {"scene_index": scene_index, "scene_name": scene.name}
        for prop in ("follow_action_0", "follow_action_1",
                      "follow_action_probability", "follow_action_time",
                      "follow_action_enabled", "follow_action_linked"):
            try:
                val = getattr(scene, prop)
                if hasattr(val, 'value'):
                    result[prop] = int(val)
                elif isinstance(val, bool):
                    result[prop] = val
                elif isinstance(val, float):
                    result[prop] = val
                else:
                    result[prop] = val
            except Exception:
                result[prop] = None
        return result
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error getting scene follow actions: " + str(e))
        raise


def set_scene_follow_actions(song, scene_index,
                              follow_action_0=None, follow_action_1=None,
                              follow_action_probability=None,
                              follow_action_time=None,
                              follow_action_enabled=None,
                              follow_action_linked=None, ctrl=None):
    """Set follow action settings for a scene."""
    try:
        scene = get_scene(song, scene_index)
        changes = {}
        if follow_action_0 is not None:
            scene.follow_action_0 = int(follow_action_0)
            changes["follow_action_0"] = int(follow_action_0)
        if follow_action_1 is not None:
            scene.follow_action_1 = int(follow_action_1)
            changes["follow_action_1"] = int(follow_action_1)
        if follow_action_probability is not None:
            val = float(follow_action_probability)
            scene.follow_action_probability = max(0.0, min(1.0, val))
            changes["follow_action_probability"] = scene.follow_action_probability
        if follow_action_time is not None:
            scene.follow_action_time = float(follow_action_time)
            changes["follow_action_time"] = float(follow_action_time)
        if follow_action_enabled is not None:
            scene.follow_action_enabled = bool(follow_action_enabled)
            changes["follow_action_enabled"] = bool(follow_action_enabled)
        if follow_action_linked is not None:
            scene.follow_action_linked = bool(follow_action_linked)
            changes["follow_action_linked"] = bool(follow_action_linked)
        if not changes:
            raise ValueError("No follow action parameters specified")
        changes["scene_index"] = scene_index
        changes["scene_name"] = scene.name
        return changes
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting scene follow actions: " + str(e))
        raise


def fire_scene_as_selected(song, scene_index, ctrl=None):
    """Fire a scene without moving the selection highlight."""
    try:
        scene = get_scene(song, scene_index)
        scene.fire_as_selected()
        return {"fired": True, "scene_index": scene_index}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error firing scene as selected: " + str(e))
        raise


def set_scene_color(song, scene_index, color_index, ctrl=None):
    """Set the color of a scene."""
    try:
        scene = get_scene(song, scene_index)
        color_index = int(color_index)
        if color_index < 0 or color_index > 69:
            raise ValueError("color_index must be 0-69, got {0}".format(color_index))
        scene.color_index = color_index
        return {"scene_index": scene_index, "color_index": scene.color_index}
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting scene color: " + str(e))
        raise


def set_scene_tempo(song, scene_index, tempo, ctrl=None):
    """Set or clear a scene's tempo override.

    Args:
        tempo: BPM value (20-999), or 0 to clear the scene tempo override.
    """
    try:
        scene = get_scene(song, scene_index)
        tempo = float(tempo)
        if tempo != 0 and (tempo < 20 or tempo > 999):
            raise ValueError(
                "Tempo must be 0 (to clear override) or between 20 and 999 BPM, got {0}".format(tempo))
        scene.tempo = tempo
        return {
            "scene_index": scene_index,
            "tempo": scene.tempo,
            "name": scene.name,
        }
    except Exception as e:
        if ctrl:
            ctrl.log_message("Error setting scene tempo: " + str(e))
        raise
