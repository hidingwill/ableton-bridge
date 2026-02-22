"""Shared validation helpers used by all handler modules."""

from __future__ import absolute_import, print_function, unicode_literals


def get_track(song, track_index, track_type="track"):
    """Get track by index with bounds validation.

    Args:
        song: Live song object.
        track_index: Zero-based index.
        track_type: "track" | "return" | "master".

    Returns:
        The track object.

    Raises:
        IndexError: If track_index is out of range.
    """
    if track_type == "return":
        tracks = song.return_tracks
        label = "Return track"
    elif track_type == "master":
        return song.master_track
    else:
        tracks = song.tracks
        label = "Track"
    if track_index < 0 or track_index >= len(tracks):
        raise IndexError("{0} index out of range".format(label))
    return tracks[track_index]


def get_clip_slot(song, track_index, clip_index, track_type="track"):
    """Get a clip slot with full track + slot bounds validation.

    Returns:
        (track, clip_slot) tuple.

    Raises:
        IndexError: If track or clip index is out of range.
    """
    track = get_track(song, track_index, track_type)
    if clip_index < 0 or clip_index >= len(track.clip_slots):
        raise IndexError("Clip index out of range")
    return track, track.clip_slots[clip_index]


def get_clip(song, track_index, clip_index, track_type="track"):
    """Get a clip with full validation chain (track + slot + has_clip).

    Returns:
        (track, clip) tuple.

    Raises:
        IndexError: If track or clip index is out of range.
        Exception: If the slot has no clip.
    """
    track, slot = get_clip_slot(song, track_index, clip_index, track_type)
    if not slot.has_clip:
        raise Exception("No clip in slot (track={0}, clip={1})".format(track_index, clip_index))
    return track, slot.clip


def get_scene(song, scene_index):
    """Get a scene by index with bounds validation.

    Returns:
        The scene object.

    Raises:
        IndexError: If scene_index is out of range.
    """
    if scene_index < 0 or scene_index >= len(song.scenes):
        raise IndexError("Scene index out of range")
    return song.scenes[scene_index]
