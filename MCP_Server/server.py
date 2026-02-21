# ableton_mcp_server.py — AbletonMCP Beta
from mcp.server.fastmcp import FastMCP, Context
import socket
import json
import logging
import time
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List, Optional, Union
import uuid
import base64
import struct
import math
import os
import gzip
import threading
import functools
from collections import deque
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AbletonMCP-Beta")

@dataclass
class AbletonConnection:
    host: str
    port: int
    sock: socket.socket = None
    _udp_sock: socket.socket = None
    _udp_port: int = 9882
    
    def connect(self) -> bool:
        """Connect to the Ableton Remote Script socket server"""
        if self.sock:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self._recv_buffer = ""  # Clear buffer on new connection
            logger.info("Connected to Ableton at %s:%s", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to connect to Ableton: %s", e)
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = None
            return False
    
    def disconnect(self):
        """Disconnect from the Ableton Remote Script"""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error("Error disconnecting from Ableton: %s", e)
            finally:
                self.sock = None
        if self._udp_sock:
            try:
                self._udp_sock.close()
            except Exception:
                pass
            finally:
                self._udp_sock = None

    def __post_init__(self):
        self._recv_buffer = ""

    def _ensure_udp_socket(self):
        """Create a UDP socket for real-time parameter sending if not already open."""
        if self._udp_sock is None:
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._udp_sock

    def send_udp_command(self, command_type: str, params: Dict[str, Any] = None):
        """Send a fire-and-forget UDP command to the Remote Script.

        No response is expected or waited for.
        """
        sock = self._ensure_udp_socket()
        command = {
            "type": command_type,
            "params": params or {}
        }
        payload = json.dumps(command).encode("utf-8")
        sock.sendto(payload, (self.host, self._udp_port))
        logger.debug("Sent UDP command: %s", command_type)

    def receive_full_response(self, sock, buffer_size=8192, timeout=15.0):
        """Receive a complete newline-delimited JSON response and return the parsed object"""
        sock.settimeout(timeout)

        try:
            while True:
                # Check if we already have a complete line in the buffer
                if '\n' in self._recv_buffer:
                    line, self._recv_buffer = self._recv_buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        result = json.loads(line)
                        logger.debug("Received complete response (%d chars)", len(line))
                        return result

                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        raise Exception("Connection closed before receiving any data")

                    self._recv_buffer += chunk.decode('utf-8')
                except socket.timeout:
                    logger.warning("Socket timeout during receive")
                    raise
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error("Socket connection error during receive: %s", e)
                    raise
        except (socket.timeout, json.JSONDecodeError):
            raise
        except Exception as e:
            logger.error("Error during receive: %s", e)
            raise

    def _reconnect(self) -> bool:
        """Force a fresh reconnection, clearing all state."""
        logger.info("Forcing reconnection to Ableton...")
        self.disconnect()
        self._recv_buffer = ""
        return self.connect()

    # Commands that modify Ableton state (need extra delays for stability)
    _MODIFYING_COMMANDS = frozenset([
        "create_midi_track", "create_audio_track", "set_track_name",
        "create_clip", "add_notes_to_clip", "set_clip_name",
        "set_tempo", "fire_clip", "stop_clip", "set_device_parameter",
        "start_playback", "stop_playback", "load_instrument_or_effect",
        "load_sample", "load_drum_kit",
        "arm_track", "disarm_track", "set_arrangement_overdub",
        "start_arrangement_recording", "stop_arrangement_recording",
        "set_loop_start", "set_loop_end", "set_loop_length", "set_playback_position",
        "create_scene", "delete_scene", "fire_scene", "set_scene_name",
        "set_track_color", "set_clip_color",
        "quantize_clip_notes", "transpose_clip_notes", "duplicate_clip",
        "group_tracks", "set_track_volume", "set_track_pan", "set_track_mute",
        "set_track_solo", "set_track_arm", "set_track_send",
        "set_warp_mode", "set_clip_warp", "crop_clip", "reverse_clip",
        "set_clip_loop_points", "set_clip_start_end", "set_clip_looping",
        "duplicate_clip_to_arrangement", "create_clip_automation", "clear_clip_automation",
        "create_track_automation", "clear_track_automation",
        "delete_time", "duplicate_time", "insert_silence",
        "delete_clip", "set_metronome", "tap_tempo", "capture_midi", "apply_groove",
        "freeze_track", "unfreeze_track",
        "create_return_track", "delete_track", "duplicate_track",
        "delete_device", "set_return_track_volume", "set_return_track_pan",
        "set_return_track_mute", "set_return_track_solo", "set_master_volume",
        "clear_clip_notes", "add_notes_extended", "remove_notes_range",
        "duplicate_clip_loop", "set_song_loop", "set_song_time",
        "set_track_monitoring", "set_clip_launch_quantization", "set_clip_legato",
        "set_drum_pad", "copy_drum_pad", "rack_variation_action",
        "set_groove_settings", "audio_to_midi", "create_midi_track_with_simpler",
        "sliced_simpler_to_drum_rack", "set_scene_tempo",
        "undo", "redo", "set_track_routing", "set_clip_pitch", "set_clip_launch_mode",
        "set_or_delete_cue", "jump_to_cue",
        "set_compressor_sidechain", "set_eq8_properties", "set_hybrid_reverb_ir",
        "set_song_settings", "trigger_session_record", "navigate_playback",
        "select_scene", "select_track", "set_detail_clip",
        "set_transmute_properties",
        "set_track_fold", "set_crossfade_assign",
        "duplicate_clip_region", "move_clip_playing_pos", "set_clip_grid",
        "set_simpler_properties", "simpler_sample_action", "manage_sample_slices",
        "preview_browser_item",
    ])

    def send_command(self, command_type: str, params: Dict[str, Any] = None, timeout: float = None) -> Dict[str, Any]:
        """Send a command to Ableton and return the response.

        Includes automatic retry: if the first attempt fails due to a
        socket error, the connection is reset and the command is retried once.
        Adds small delays around modifying commands for stability.
        """
        max_attempts = 2
        is_modifying = command_type in self._MODIFYING_COMMANDS

        for attempt in range(1, max_attempts + 1):
            if not self.sock and not self.connect():
                raise ConnectionError("Not connected to Ableton")

            command = {
                "type": command_type,
                "params": params or {}
            }

            try:
                logger.debug("Sending command: %s (attempt %d)", command_type, attempt)

                # Send the command as newline-delimited JSON
                self.sock.sendall((json.dumps(command) + '\n').encode('utf-8'))

                # Add a small delay after sending modifying commands
                # to give Ableton time to process before we read the response
                if is_modifying:
                    time.sleep(0.1)

                # Set timeout based on command type (caller override takes priority)
                if timeout is None:
                    timeout = 15.0 if is_modifying else 10.0
                # Receive the response (already parsed by receive_full_response)
                response = self.receive_full_response(self.sock, timeout=timeout)
                logger.debug("Response status: %s", response.get('status', 'unknown'))

                if response.get("status") == "error":
                    logger.error("Ableton error: %s", response.get('message'))
                    raise Exception(response.get("message", "Unknown error from Ableton"))

                # Add a small delay after modifying commands complete
                # to let Ableton settle before the next command
                if is_modifying:
                    time.sleep(0.1)

                return response.get("result", {})

            except Exception as e:
                logger.error("Command '%s' attempt %d failed: %s", command_type, attempt, e)
                # Close the broken socket and clear buffer
                self.disconnect()
                self._recv_buffer = ""

                if attempt < max_attempts:
                    # Wait briefly then retry with a fresh connection
                    time.sleep(0.3)
                    if not self.connect():
                        raise ConnectionError("Failed to reconnect to Ableton")
                    logger.info("Reconnected, retrying command...")
                else:
                    raise Exception(f"Command '{command_type}' failed after {max_attempts} attempts: {e}")


@dataclass
class M4LConnection:
    """UDP connection to the Max for Live bridge device.

    The M4L bridge provides deep LOM access for hidden device parameters.
    Communication uses two UDP ports:
      - send_port (9878): MCP server → M4L device (commands)
      - recv_port (9879): M4L device → MCP server (responses)
    """
    send_host: str = "127.0.0.1"
    send_port: int = 9878
    recv_port: int = 9879
    send_sock: socket.socket = None
    recv_sock: socket.socket = None
    _connected: bool = False

    def connect(self) -> bool:
        """Set up UDP sockets for M4L communication."""
        try:
            self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Use exclusive binding — prevents a second instance from sharing this port
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.recv_sock.bind(("127.0.0.1", self.recv_port))
            self.recv_sock.settimeout(5.0)
            self._connected = True
            logger.info("M4L UDP sockets ready (send→:%d, recv←:%d)", self.send_port, self.recv_port)
            return True
        except Exception as e:
            logger.error("Failed to set up M4L UDP connection: %s", e)
            self.disconnect()
            return False

    def disconnect(self):
        """Close UDP sockets."""
        for s in (self.send_sock, self.recv_sock):
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        self.send_sock = None
        self.recv_sock = None
        self._connected = False

    @staticmethod
    def _build_osc_message(address: str, osc_args: list = None) -> bytes:
        """Build an OSC message with typed arguments.

        Each arg is a tuple of (type, value):
          ('i', 42)  — 32-bit int
          ('f', 3.14) — 32-bit float
          ('s', 'hi') — null-terminated padded string
        """
        def _osc_string(s: str) -> bytes:
            b = s.encode("utf-8") + b"\x00"
            b += b"\x00" * ((4 - len(b) % 4) % 4)
            return b

        osc_args = osc_args or []
        msg = _osc_string(address)
        type_tag = "," + "".join(t for t, _ in osc_args)
        msg += _osc_string(type_tag)
        for t, v in osc_args:
            if t == "s":
                msg += _osc_string(str(v))
            elif t == "i":
                msg += struct.pack(">i", int(v))
            elif t == "f":
                msg += struct.pack(">f", float(v))
        return msg

    def _build_osc_packet(self, command_type: str, params: Dict[str, Any], request_id: str) -> bytes:
        """Build the OSC packet for a given command type."""
        if command_type == "ping":
            return self._build_osc_message("/ping", [("s", request_id)])
        elif command_type == "discover_params":
            return self._build_osc_message("/discover_params", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("s", request_id),
            ])
        elif command_type == "get_hidden_params":
            return self._build_osc_message("/get_hidden_params", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("s", request_id),
            ])
        elif command_type == "set_hidden_param":
            return self._build_osc_message("/set_hidden_param", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("i", params["parameter_index"]),
                ("f", params["value"]),
                ("s", request_id),
            ])
        elif command_type == "get_device_property":
            return self._build_osc_message("/get_device_property", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("s", params["property_name"]),
                ("s", request_id),
            ])
        elif command_type == "set_device_property":
            return self._build_osc_message("/set_device_property", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("s", params["property_name"]),
                ("f", params["value"]),
                ("s", request_id),
            ])
        elif command_type == "batch_set_hidden_params":
            # Use compact JSON (no spaces) + URL-safe base64 without padding.
            # Max's OSC/symbol handling mangles +, /, and = characters.
            params_json = json.dumps(params["parameters"], separators=(",", ":"))
            params_b64 = base64.urlsafe_b64encode(params_json.encode("utf-8")).decode("ascii").rstrip("=")
            return self._build_osc_message("/batch_set_hidden_params", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("s", params_b64),
                ("s", request_id),
            ])
        # --- Phase 7: Cue Points ---
        elif command_type == "get_cue_points":
            return self._build_osc_message("/get_cue_points", [
                ("s", request_id),
            ])
        elif command_type == "jump_to_cue_point":
            return self._build_osc_message("/jump_to_cue_point", [
                ("i", params["cue_point_index"]),
                ("s", request_id),
            ])
        # --- Phase 8: Groove Pool ---
        elif command_type == "get_groove_pool":
            return self._build_osc_message("/get_groove_pool", [
                ("s", request_id),
            ])
        elif command_type == "set_groove_properties":
            props_json = json.dumps(params["properties"], separators=(",", ":"))
            props_b64 = base64.urlsafe_b64encode(props_json.encode("utf-8")).decode("ascii").rstrip("=")
            return self._build_osc_message("/set_groove_properties", [
                ("i", params["groove_index"]),
                ("s", props_b64),
                ("s", request_id),
            ])
        # --- Phase 6: Event Monitoring ---
        elif command_type == "observe_property":
            return self._build_osc_message("/observe_property", [
                ("s", params["lom_path"]),
                ("s", params["property_name"]),
                ("s", request_id),
            ])
        elif command_type == "stop_observing":
            return self._build_osc_message("/stop_observing", [
                ("s", params["lom_path"]),
                ("s", params["property_name"]),
                ("s", request_id),
            ])
        elif command_type == "get_observed_changes":
            return self._build_osc_message("/get_observed_changes", [
                ("s", request_id),
            ])
        # --- Phase 9: Clean Params ---
        elif command_type == "set_param_clean":
            return self._build_osc_message("/set_param_clean", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("i", params["parameter_index"]),
                ("f", params["value"]),
                ("s", request_id),
            ])
        # --- Phase 5: Audio Analysis ---
        elif command_type == "analyze_audio":
            track_index = params.get("track_index", -1) if params else -1
            return self._build_osc_message("/analyze_audio", [
                ("i", track_index),
                ("s", request_id),
            ])
        elif command_type == "analyze_spectrum":
            return self._build_osc_message("/analyze_spectrum", [
                ("s", request_id),
            ])
        # --- Cross-Track MSP Analysis ---
        elif command_type == "analyze_cross_track":
            return self._build_osc_message("/analyze_cross_track", [
                ("i", params.get("track_index", 0)),
                ("i", params.get("wait_ms", 500)),
                ("s", request_id),
            ])
        # --- Phase 10: App Version Detection ---
        elif command_type == "get_app_version":
            return self._build_osc_message("/get_app_version", [("s", request_id)])
        # --- Phase 11: Automation State Introspection ---
        elif command_type == "get_automation_states":
            return self._build_osc_message("/get_automation_states", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("s", request_id),
            ])
        # --- Phase F1: Wire orphaned chain OSC builders ---
        elif command_type == "discover_chains":
            extra = params.get("extra_path", "")
            osc_args = [("i", params["track_index"]), ("i", params["device_index"])]
            if extra:
                osc_args.append(("s", extra))
            osc_args.append(("s", request_id))
            return self._build_osc_message("/discover_chains", osc_args)
        elif command_type == "get_chain_device_params":
            return self._build_osc_message("/get_chain_device_params", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("i", params["chain_index"]),
                ("i", params["chain_device_index"]),
                ("s", request_id),
            ])
        elif command_type == "set_chain_device_param":
            return self._build_osc_message("/set_chain_device_param", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("i", params["chain_index"]),
                ("i", params["chain_device_index"]),
                ("i", params["parameter_index"]),
                ("f", params["value"]),
                ("s", request_id),
            ])
        # --- Phase 12: Note Surgery by ID ---
        elif command_type == "get_clip_notes_by_id":
            return self._build_osc_message("/get_clip_notes_by_id", [
                ("i", params["track_index"]),
                ("i", params["clip_index"]),
                ("s", request_id),
            ])
        elif command_type == "modify_clip_notes":
            mods_json = json.dumps(params["modifications"], separators=(",", ":"))
            mods_b64 = base64.urlsafe_b64encode(mods_json.encode("utf-8")).decode("ascii").rstrip("=")
            return self._build_osc_message("/modify_clip_notes", [
                ("i", params["track_index"]),
                ("i", params["clip_index"]),
                ("s", mods_b64),
                ("s", request_id),
            ])
        elif command_type == "remove_clip_notes_by_id":
            ids_json = json.dumps(params["note_ids"], separators=(",", ":"))
            ids_b64 = base64.urlsafe_b64encode(ids_json.encode("utf-8")).decode("ascii").rstrip("=")
            return self._build_osc_message("/remove_clip_notes_by_id", [
                ("i", params["track_index"]),
                ("i", params["clip_index"]),
                ("s", ids_b64),
                ("s", request_id),
            ])
        # --- Phase 13: Chain-Level Mixing ---
        elif command_type == "get_chain_mixing":
            return self._build_osc_message("/get_chain_mixing", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("i", params["chain_index"]),
                ("s", request_id),
            ])
        elif command_type == "set_chain_mixing":
            props_json = json.dumps(params["properties"], separators=(",", ":"))
            props_b64 = base64.urlsafe_b64encode(props_json.encode("utf-8")).decode("ascii").rstrip("=")
            return self._build_osc_message("/set_chain_mixing", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("i", params["chain_index"]),
                ("s", props_b64),
                ("s", request_id),
            ])
        # --- Phase 14: Device AB Comparison ---
        elif command_type == "device_ab_compare":
            return self._build_osc_message("/device_ab_compare", [
                ("i", params["track_index"]),
                ("i", params["device_index"]),
                ("s", params["action"]),
                ("s", request_id),
            ])
        # --- Phase 15: Clip Scrubbing ---
        elif command_type == "clip_scrub":
            return self._build_osc_message("/clip_scrub", [
                ("i", params["track_index"]),
                ("i", params["clip_index"]),
                ("s", params["action"]),
                ("f", params.get("beat_time", 0.0)),
                ("s", request_id),
            ])
        # --- Phase 16: Split Stereo Panning ---
        elif command_type == "get_split_stereo":
            return self._build_osc_message("/get_split_stereo", [
                ("i", params["track_index"]),
                ("s", request_id),
            ])
        elif command_type == "set_split_stereo":
            return self._build_osc_message("/set_split_stereo", [
                ("i", params["track_index"]),
                ("f", params["left"]),
                ("f", params["right"]),
                ("s", request_id),
            ])
        else:
            raise ValueError(f"Unknown M4L command: {command_type}")

    def _drain_recv_socket(self):
        """Drain any stale data from the receive socket."""
        self.recv_sock.setblocking(False)
        try:
            for _ in range(100):
                self.recv_sock.recvfrom(65535)
        except (BlockingIOError, OSError):
            pass
        self.recv_sock.setblocking(True)

    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a command to the M4L bridge using native OSC messages.

        Includes automatic reconnect: if the send or receive fails, the
        UDP sockets are recreated and the command is retried once.
        """
        params = params or {}
        request_id = str(uuid.uuid4())[:8]
        osc = self._build_osc_packet(command_type, params, request_id)

        # Commands that use chunked async processing in the M4L bridge
        # need longer timeouts to account for discovery + response delays.
        if command_type == "batch_set_hidden_params":
            param_count = len(params.get("parameters", []))
            # ~150ms per param (chunk delay + LOM overhead), minimum 10s
            timeout = max(10.0, param_count * 0.15)
        elif command_type in ("discover_params", "get_hidden_params"):
            # Chunked discovery: ~50ms per 4 params + chunked response sending
            timeout = 15.0
        elif command_type == "analyze_cross_track":
            # Cross-track: wait_ms + overhead for send routing + restore + response
            wait_ms = params.get("wait_ms", 500)
            timeout = max(3.0, (wait_ms / 1000.0) + 1.5)
        else:
            timeout = 5.0

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            if not self._connected:
                if not self.connect():
                    raise ConnectionError("Could not establish M4L UDP connection.")

            # Drain any stale data in the recv socket before sending
            self._drain_recv_socket()
            self.recv_sock.settimeout(timeout)

            try:
                self.send_sock.sendto(osc, (self.send_host, self.send_port))
            except Exception as e:
                logger.error("Failed to send UDP command to M4L (attempt %d): %s", attempt, e)
                if attempt < max_attempts:
                    self.disconnect()
                    time.sleep(0.2)
                    continue
                raise ConnectionError("Failed to send command to M4L bridge.")

            try:
                data, _addr = self.recv_sock.recvfrom(65535)
                result = self._parse_m4l_response(data)

                # Handle chunked responses from the M4L bridge.
                # Large responses (>1500 chars JSON) are split into multiple
                # UDP packets, each wrapped in an envelope: {"_c":idx,"_t":total,"_d":"base64piece"}
                if "_c" in result and "_t" in result:
                    result = self._reassemble_chunked_response(result)

                # Verify request_id matches — drain stale responses if mismatch
                resp_id = result.get("id", "")
                if resp_id and resp_id != request_id:
                    for _drain in range(5):
                        logger.warning("M4L response id mismatch: expected %s, got %s — draining", request_id, resp_id)
                        try:
                            data, _addr = self.recv_sock.recvfrom(65535)
                            result = self._parse_m4l_response(data)
                            if "_c" in result and "_t" in result:
                                result = self._reassemble_chunked_response(result)
                            resp_id = result.get("id", "")
                            if not resp_id or resp_id == request_id:
                                break
                        except socket.timeout:
                            raise Exception(f"Timeout waiting for correct M4L response (expected {request_id})")
                    else:
                        logger.error("Could not find matching M4L response after 5 drains (expected %s)", request_id)
                return result
            except socket.timeout:
                logger.warning("M4L response timeout (attempt %d)", attempt)
                if attempt < max_attempts:
                    self.disconnect()
                    time.sleep(0.2)
                    continue
                raise Exception("Timeout waiting for M4L bridge response. Is the M4L device loaded?")

    @staticmethod
    def _parse_m4l_response(data: bytes) -> Dict[str, Any]:
        """Parse the response from the M4L bridge.

        Max's udpsend wraps the base64 string as an OSC message:
          [base64_string\\0...padding][,\\0\\0\\0]
        The OSC address (first null-terminated string) contains our
        base64-encoded JSON response.  The bridge uses URL-safe base64
        (- instead of +, _ instead of /, no = padding).
        """
        # Extract the OSC address = first null-terminated string in the packet
        null_pos = data.find(b"\x00")
        if null_pos > 0:
            osc_address = data[:null_pos].decode("utf-8", errors="replace").strip()
        else:
            osc_address = data.decode("utf-8", errors="replace").strip()

        # The OSC address is our base64-encoded JSON response
        # (udpsend uses the outlet symbol as the OSC address)
        # URL-safe base64 is the common path (v2.0.0+ bridge)
        try:
            padded = osc_address + "=" * (-len(osc_address) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
            return json.loads(decoded)
        except (ValueError, base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Fallback: try standard base64
        try:
            decoded = base64.b64decode(osc_address).decode("utf-8")
            return json.loads(decoded)
        except (ValueError, base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Fallback: try raw JSON (in case response wasn't base64-encoded)
        try:
            return json.loads(osc_address)
        except (json.JSONDecodeError, ValueError):
            pass

        # Last resort: strip all nulls and try
        cleaned = data.replace(b"\x00", b"").strip()
        text = cleaned.decode("utf-8", errors="replace").strip()
        # Remove trailing comma from OSC type tag
        text = text.rstrip(",").strip()
        try:
            padded = text + "=" * (-len(text) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
            return json.loads(decoded)
        except (ValueError, base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
            pass
        try:
            decoded = base64.b64decode(text).decode("utf-8")
            return json.loads(decoded)
        except (ValueError, base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
            pass

        raise json.JSONDecodeError("Could not parse M4L response", text, 0)

    def _reassemble_chunked_response(self, first_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Reassemble a chunked response from the M4L bridge.

        Large responses are split into multiple UDP packets, each containing:
          {"_c": chunk_index, "_t": total_chunks, "_d": "url_safe_base64_piece"}
        Each _d piece decodes to a fragment of the original JSON string.
        We collect all chunks, decode each _d, concatenate, and parse.
        """
        total = first_chunk["_t"]
        logger.info("M4L chunked response: %d total chunks", total)

        # Store chunks by index
        chunks: Dict[int, str] = {first_chunk["_c"]: first_chunk["_d"]}

        # Collect remaining chunks
        # Give extra time: 100ms per chunk + 5s base
        chunk_timeout = max(5.0, total * 0.1 + 5.0)
        self.recv_sock.settimeout(chunk_timeout)

        while len(chunks) < total:
            try:
                data, _ = self.recv_sock.recvfrom(65535)
                parsed = self._parse_m4l_response(data)
                if "_c" in parsed and "_t" in parsed:
                    chunks[parsed["_c"]] = parsed["_d"]
                else:
                    # Got a non-chunk response (maybe from another command?)
                    logger.warning("M4L chunk reassembly: got non-chunk packet, ignoring")
            except socket.timeout:
                logger.error("M4L chunk reassembly: timeout after %d/%d chunks", len(chunks), total)
                raise Exception(f"Timeout receiving chunked M4L response ({len(chunks)}/{total} chunks received)")

        # Reassemble: decode each piece and concatenate
        json_parts = []
        for i in range(total):
            piece_b64 = chunks[i]
            padded = piece_b64 + "=" * (-len(piece_b64) % 4)
            piece_json = base64.urlsafe_b64decode(padded).decode("utf-8")
            json_parts.append(piece_json)

        full_json = "".join(json_parts)
        logger.info("M4L chunked response reassembled: %d chars from %d chunks", len(full_json), total)
        return json.loads(full_json)

    def ping(self) -> bool:
        """Check if the M4L bridge device is responding."""
        try:
            result = self.send_command("ping")
            return result.get("status") == "success"
        except Exception:
            return False


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    global _server_start_time, _singleton_lock_sock
    try:
        # Singleton guard — prevent duplicate server instances
        try:
            _singleton_lock_sock = _acquire_singleton_lock()
        except RuntimeError as e:
            logger.error(str(e))
            logger.error("Exiting to avoid conflicts.")
            import sys
            sys.exit(1)

        logger.info("AbletonMCP Beta server starting up")
        _server_start_time = time.time()

        try:
            ableton = get_ableton_connection()
            logger.info("Successfully connected to Ableton on startup")
        except Exception as e:
            logger.warning("Could not connect to Ableton on startup: %s", e)
            logger.warning("Make sure the Ableton Remote Script is running")

        # Auto-connect M4L bridge in background (device may need time to init)
        def _m4l_auto_connect():
            """Background thread: create UDP sockets once, retry ping until M4L responds."""
            global _m4l_connection

            # Create sockets once — don't tear them down between retries
            conn = M4LConnection()
            if not conn.connect():
                logger.warning("M4L auto-connect: could not bind UDP sockets")
                return

            _m4l_connection = conn

            # Build a raw OSC ping packet
            ping_id = "autocon"
            ping_osc = M4LConnection._build_osc_message("/ping", [("s", ping_id)])

            for attempt in range(1, 16):  # 15 attempts, ~2s apart
                try:
                    # Drain stale data
                    conn._drain_recv_socket()
                    conn.recv_sock.settimeout(2.0)

                    # Send ping
                    conn.send_sock.sendto(ping_osc, (conn.send_host, conn.send_port))

                    # Wait for response
                    data, _addr = conn.recv_sock.recvfrom(65535)
                    result = conn._parse_m4l_response(data)
                    if result.get("status") == "success":
                        logger.info("M4L bridge auto-connected on attempt %d", attempt)
                        _m4l_ping_cache["result"] = True
                        _m4l_ping_cache["timestamp"] = time.time()
                        return
                except socket.timeout:
                    logger.info("M4L auto-connect %d/15: no response (timeout), retrying...", attempt)
                except Exception as e:
                    logger.info("M4L auto-connect %d/15: %s", attempt, e)
                time.sleep(2)
            logger.warning("M4L bridge not available after 15 attempts — will retry when needed")

        threading.Thread(target=_m4l_auto_connect, daemon=True, name="m4l-auto-connect").start()

        # Start web dashboard on background thread
        try:
            _start_dashboard_server()
        except Exception as e:
            logger.warning("Dashboard failed to start: %s", e)

        # Pre-populate browser cache in background (so search_browser is instant)
        def _browser_cache_warmup():
            """Background thread: load disk cache instantly, then refresh from Ableton."""
            # Step 1: Load from disk (instant, works even before Ableton connects)
            disk_loaded = _load_browser_cache_from_disk()
            if disk_loaded:
                # Skip live rescan if disk cache is fresh enough
                age = time.time() - _browser_cache_timestamp
                if age < _BROWSER_DISK_CACHE_MAX_AGE:
                    logger.info("Browser cache ready from disk (%.0fs old, skipping rescan)", age)
                    return
                logger.info("Browser cache loaded from disk (%.0fs old, will refresh)", age)

            # Step 2: Wait for Ableton, then do a live scan to refresh
            time.sleep(5)  # let Ableton & Remote Script fully settle
            for _ in range(20):  # poll up to 10s more for Ableton connection
                if _ableton_connection and _ableton_connection.sock:
                    break
                time.sleep(0.5)
            try:
                _populate_browser_cache()
            except Exception as e:
                logger.warning("Browser cache warmup failed: %s", e)

        threading.Thread(target=_browser_cache_warmup, daemon=True, name="browser-cache-warmup").start()

        yield {}
    finally:
        _stop_dashboard_server()
        global _ableton_connection, _m4l_connection
        if _ableton_connection:
            logger.info("Disconnecting from Ableton on shutdown")
            _ableton_connection.disconnect()
            _ableton_connection = None
        if _m4l_connection:
            logger.info("Disconnecting M4L bridge on shutdown")
            _m4l_connection.disconnect()
            _m4l_connection = None
        _release_singleton_lock(_singleton_lock_sock)
        _singleton_lock_sock = None
        logger.info("AbletonMCP Beta server shut down")

# Create the MCP server with lifespan support
mcp = FastMCP(
    "AbletonMCP-Beta",
    lifespan=server_lifespan
)

# Global connections
_ableton_connection = None
_m4l_connection = None

# v1.6.0 feature stores (in-memory, lost on restart)
_snapshot_store: Dict[str, Dict[str, Any]] = {}
_macro_store: Dict[str, Dict[str, Any]] = {}
_param_map_store: Dict[str, Dict[str, Any]] = {}

# Web dashboard state
_server_start_time: float = 0.0
_tool_call_log: deque = deque(maxlen=50)
_tool_call_counts: Dict[str, int] = {}
_tool_call_lock = threading.Lock()
_dashboard_server = None
DASHBOARD_PORT = int(os.environ.get("ABLETON_MCP_DASHBOARD_PORT", "9880"))
SINGLETON_LOCK_PORT = int(os.environ.get("ABLETON_MCP_LOCK_PORT", "9881"))
_singleton_lock_sock: socket.socket = None
_server_log_buffer: deque = deque(maxlen=200)
_server_log_lock = threading.Lock()

def _resolve_device_uri(uri_or_name: str) -> str:
    """Resolve a device name or URI to a loadable URI.

    If the input already looks like a URI (contains ':' or '#'), return as-is.
    Otherwise, look up the name in the dynamic device URI map built from
    the browser cache.  Waits for the warmup thread if the map is empty.
    """
    if ":" in uri_or_name or "#" in uri_or_name:
        return uri_or_name

    name_lower = uri_or_name.strip().lower()

    # Fast O(1) lookup in the dynamic device URI map
    with _browser_cache_lock:
        resolved = _device_uri_map.get(name_lower)
    if resolved:
        logger.info("Resolved device name '%s' to URI '%s'", uri_or_name, resolved)
        return resolved

    # Map is empty — wait for warmup thread to populate it (don't trigger a second scan)
    logger.info("Device map empty, waiting for browser cache warmup...")
    for _ in range(120):  # 120 * 0.5s = 60s max
        time.sleep(0.5)
        with _browser_cache_lock:
            resolved = _device_uri_map.get(name_lower)
        if resolved:
            logger.info("Resolved device name '%s' to URI '%s'", uri_or_name, resolved)
            return resolved
        # Stop waiting if cache is populated but name wasn't found
        with _browser_cache_lock:
            if _browser_cache_flat and not _browser_cache_populating:
                break

    # Fallback: linear scan for exact name match (take snapshot under lock)
    with _browser_cache_lock:
        cache_snapshot = _browser_cache_flat
    if cache_snapshot:
        logger.warning("Device '%s' not in URI map, falling back to O(n) scan of %d items", uri_or_name, len(cache_snapshot))
    for item in cache_snapshot:
        if item.get("search_name") == name_lower and item.get("is_loadable") and item.get("uri"):
            resolved = item["uri"]
            logger.info("Resolved device name '%s' via cache scan to URI '%s'", uri_or_name, resolved)
            return resolved

    logger.warning("Could not resolve '%s' to a known URI, passing through as-is", uri_or_name)
    return uri_or_name


def _acquire_singleton_lock() -> socket.socket:
    """Acquire an exclusive TCP port lock to prevent duplicate server instances.

    Returns the bound socket (caller must keep it alive for the server's lifetime).
    Raises RuntimeError if another instance already holds the lock.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", SINGLETON_LOCK_PORT))
        sock.listen(1)
        logger.info("Singleton lock acquired on port %d", SINGLETON_LOCK_PORT)
        return sock
    except OSError as e:
        sock.close()
        raise RuntimeError(
            f"Another AbletonMCP server instance is already running "
            f"(port {SINGLETON_LOCK_PORT} is in use). "
            f"Stop the other instance first."
        ) from e


def _release_singleton_lock(sock: socket.socket):
    """Release the singleton lock by closing the lock socket."""
    if sock:
        try:
            sock.close()
            logger.info("Singleton lock released")
        except Exception:
            pass


class _DashboardLogHandler(logging.Handler):
    """Captures log records into the dashboard ring buffer.

    Stores lightweight tuples (created_float, level_str, message_str) to
    avoid formatting timestamps on every log message.  Timestamps are
    formatted only when the dashboard is actually viewed.
    """

    def emit(self, record):
        try:
            with _server_log_lock:
                _server_log_buffer.append(
                    (record.created, record.levelname, record.getMessage())
                )
        except Exception:
            pass


_dashboard_log_handler = _DashboardLogHandler()
logging.getLogger().addHandler(_dashboard_log_handler)

# M4L ping cache (avoids 5s UDP timeout on every dashboard refresh)
_m4l_ping_cache = {"result": False, "timestamp": 0.0}
_M4L_PING_CACHE_TTL = 5.0

# Browser cache — scans Ableton's browser tree and caches all items for instant search
_browser_cache_flat: List[Dict[str, Any]] = []  # flat list for fast substring search
_browser_cache_by_category: Dict[str, List[Dict[str, Any]]] = {}  # display_name -> items (index for filtered search)
_browser_cache_timestamp: float = 0.0
_BROWSER_CACHE_TTL = 604800.0  # 7 days — only refresh_browser_cache forces a rescan
_browser_cache_lock = threading.Lock()
_browser_cache_populating = False  # prevents duplicate scans
_BROWSER_DISK_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".ableton-mcp")
_BROWSER_DISK_CACHE_PATH = os.path.join(_BROWSER_DISK_CACHE_DIR, "browser_cache.json.gz")
_BROWSER_DISK_CACHE_PATH_LEGACY = os.path.join(_BROWSER_DISK_CACHE_DIR, "browser_cache.json")
_BROWSER_DISK_CACHE_MAX_AGE = 604800.0  # 7 days — disk cache ignored if older

# Dynamic device URI map — built from browser cache after each scan.
# Maps lowercase device name -> correct URI from Ableton's LOM.
_device_uri_map: Dict[str, str] = {}

# Category priority for resolving name collisions in _device_uri_map.
# Lower number = higher priority (stock devices beat preset folders).
_CATEGORY_PRIORITY: Dict[str, int] = {
    "Instruments": 0,
    "Audio Effects": 1,
    "MIDI Effects": 2,
    "Max for Live": 3,
    "Plug-ins": 4,
    "Sounds": 5,
    "Drums": 6,
    "Clips": 7,
    "Samples": 8,
    "Packs": 9,
    "User Library": 10,
}

# Root browser categories: (path_root, display_name)
# path_root uses the lowercase attribute name so paths work directly with
# get_browser_items_at_path (which lowercases the first component).
_BROWSER_CATEGORIES = [
    ("instruments", "Instruments"),
    ("drums", "Drums"),
    ("audio_effects", "Audio Effects"),
    ("midi_effects", "MIDI Effects"),
    ("max_for_live", "Max for Live"),
    ("plugins", "Plug-ins"),
    ("user_library", "User Library"),
]

_BROWSER_CACHE_MAX_DEPTH = 3   # category/device/subcategory (skip preset files)
_BROWSER_CACHE_MAX_ITEMS = 1500

# Maps category keys to display names (used by search_browser and get_browser_tree)
_CATEGORY_DISPLAY = {
    "instruments": "Instruments",
    "sounds": "Sounds",
    "drums": "Drums",
    "audio_effects": "Audio Effects",
    "midi_effects": "MIDI Effects",
    "max_for_live": "Max for Live",
    "plugins": "Plug-ins",
    "clips": "Clips",
    "samples": "Samples",
    "packs": "Packs",
    "user_library": "User Library",
}


def _build_device_uri_map(flat_items: List[Dict[str, Any]]) -> Dict[str, str]:
    """Build a lowercase-name -> URI lookup from the flat browser cache.

    Only includes loadable items with a non-empty URI.
    For duplicate names, prefers is_device=True items, then higher-priority
    categories (Instruments > Audio Effects > MIDI Effects > Sounds > Drums).
    """
    uri_map: Dict[str, str] = {}
    quality_map: Dict[str, tuple] = {}

    for item in flat_items:
        if not item.get("is_loadable") or not item.get("uri"):
            continue

        name_lower = item.get("search_name", item.get("name", "").lower())
        if not name_lower:
            continue

        is_device = item.get("is_device", False)
        cat_priority = _CATEGORY_PRIORITY.get(item.get("category", ""), 99)
        new_quality = (is_device, -cat_priority)

        if name_lower not in uri_map or new_quality > quality_map[name_lower]:
            uri_map[name_lower] = item["uri"]
            quality_map[name_lower] = new_quality

    return uri_map


def _save_browser_cache_to_disk() -> bool:
    """Persist the in-memory browser cache to a JSON file on disk."""
    try:
        with _browser_cache_lock:
            if not _browser_cache_flat:
                return False
            data = {
                "version": 1,
                "timestamp": _browser_cache_timestamp,
                "flat": _browser_cache_flat,
                "by_category": _browser_cache_by_category,
                "device_uri_map": _device_uri_map,
            }

        os.makedirs(_BROWSER_DISK_CACHE_DIR, exist_ok=True)
        tmp_path = _BROWSER_DISK_CACHE_PATH + ".tmp"
        with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp_path, _BROWSER_DISK_CACHE_PATH)
        # Remove legacy uncompressed cache if it exists
        if os.path.exists(_BROWSER_DISK_CACHE_PATH_LEGACY):
            try:
                os.remove(_BROWSER_DISK_CACHE_PATH_LEGACY)
            except OSError:
                pass
        logger.info("Browser cache saved to disk (%d items, gzip)", len(data["flat"]))
        return True
    except Exception as e:
        logger.warning("Failed to save browser cache to disk: %s", e)
        return False


def _load_browser_cache_from_disk() -> bool:
    """Load browser cache from disk into the in-memory globals.

    Returns True if a valid, non-stale disk cache was loaded.
    """
    global _browser_cache_flat, _browser_cache_by_category, _browser_cache_timestamp, _device_uri_map

    try:
        cache_path = None
        if os.path.exists(_BROWSER_DISK_CACHE_PATH):
            cache_path = _BROWSER_DISK_CACHE_PATH
        elif os.path.exists(_BROWSER_DISK_CACHE_PATH_LEGACY):
            cache_path = _BROWSER_DISK_CACHE_PATH_LEGACY
        if cache_path is None:
            logger.info("No disk cache found")
            return False

        opener = gzip.open if cache_path.endswith(".gz") else open
        with opener(cache_path, "rt", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict) or data.get("version") != 1:
            logger.warning("Disk cache has unknown format, ignoring")
            return False

        flat = data.get("flat", [])
        by_cat = data.get("by_category", {})
        uri_map = data.get("device_uri_map", {})
        disk_timestamp = data.get("timestamp", 0.0)

        if not flat:
            logger.info("Disk cache is empty, ignoring")
            return False

        age = time.time() - disk_timestamp
        if age > _BROWSER_DISK_CACHE_MAX_AGE:
            logger.info("Disk cache is %.1f hours old (max %.1f), ignoring",
                        age / 3600, _BROWSER_DISK_CACHE_MAX_AGE / 3600)
            return False

        with _browser_cache_lock:
            _browser_cache_flat = flat
            _browser_cache_by_category = by_cat
            _device_uri_map = uri_map
            _browser_cache_timestamp = disk_timestamp

        logger.info("Loaded browser cache from disk: %d items, %d categories, %d device URIs (%.1f min old)",
                    len(flat), len(by_cat), len(uri_map), age / 60)
        return True

    except Exception as e:
        logger.warning("Failed to load browser cache from disk: %s", e)
        return False


def _populate_browser_cache(force: bool = False) -> bool:
    """Scan Ableton's browser tree and cache all items for instant search.

    Uses a breadth-first walk up to depth 3 across 11 browser categories.
    Each command is rate-limited (50ms gap) to avoid overwhelming Ableton's
    socket handler.  Items are capped at 1500 per category.

    Uses a **dedicated TCP connection** to avoid corrupting the shared global
    connection when the BFS scan sends many rapid commands.
    """
    global _browser_cache_flat, _browser_cache_by_category, _browser_cache_timestamp, _device_uri_map, _browser_cache_populating

    now = time.time()
    with _browser_cache_lock:
        if not force and _browser_cache_flat and (now - _browser_cache_timestamp) < _BROWSER_CACHE_TTL:
            return True  # cache is still fresh
        if _browser_cache_populating:
            return True  # another thread is already scanning
        _browser_cache_populating = True

    # Use a dedicated connection so rapid BFS commands don't corrupt the
    # shared global socket (which other tools need concurrently).
    ableton = AbletonConnection(host="localhost", port=9877)

    try:
        try:
            if not ableton.connect():
                logger.warning("Browser cache: cannot connect to Ableton")
                return False
        except Exception as e:
            logger.warning("Browser cache: cannot connect to Ableton: %s", e)
            return False

        logger.info("Browser cache: starting scan...")
        flat_items: List[Dict[str, Any]] = []
        by_display: Dict[str, List[Dict[str, Any]]] = {}
        total = 0

        for path_root, display_name in _BROWSER_CATEGORIES:
            category_items: List[Dict[str, Any]] = []
            cat_count = 0

            # BFS queue: (browser_path, depth)
            queue = deque([(path_root, 0)])

            while queue and cat_count < _BROWSER_CACHE_MAX_ITEMS:
                current_path, depth = queue.popleft()

                try:
                    result = ableton.send_command("get_browser_items_at_path", {"path": current_path}, timeout=60.0)
                except Exception as e:
                    logger.warning("Browser cache: failed to read '%s': %s", current_path, e)
                    # Try to re-establish connection before continuing
                    time.sleep(2)
                    try:
                        ableton.disconnect()
                        if not ableton.connect():
                            logger.warning("Browser cache: lost connection, skipping '%s'", display_name)
                            break
                    except Exception:
                        logger.warning("Browser cache: lost connection, skipping '%s'", display_name)
                        break
                    continue

                if "error" in result:
                    continue

                for item in result.get("items", []):
                    if cat_count >= _BROWSER_CACHE_MAX_ITEMS:
                        break

                    name = item.get("name", "")
                    if not name:
                        continue

                    item_path = f"{current_path}/{name}"
                    entry = {
                        "name": name,
                        "search_name": name.lower(),
                        "uri": item.get("uri", ""),
                        "is_loadable": item.get("is_loadable", False),
                        "is_folder": item.get("is_folder", False),
                        "is_device": item.get("is_device", False),
                        "category": display_name,
                        "path": item_path,
                    }
                    category_items.append(entry)
                    flat_items.append(entry)
                    cat_count += 1
                    total += 1

                    # Enqueue folders for deeper scanning
                    if item.get("is_folder", False) and depth < _BROWSER_CACHE_MAX_DEPTH:
                        queue.append((item_path, depth + 1))

                # Rate-limit to avoid overwhelming Ableton's socket handler
                time.sleep(0.05)

            by_display[display_name] = category_items
            logger.info("Browser cache: '%s' — %d items", display_name, len(category_items))

        device_map = _build_device_uri_map(flat_items)

        with _browser_cache_lock:
            _browser_cache_flat = flat_items
            _browser_cache_by_category = by_display
            _device_uri_map = device_map
            _browser_cache_timestamp = time.time()

        logger.info("Browser cache: %d items, %d categories, %d device names mapped", total, len(by_display), len(device_map))
        _save_browser_cache_to_disk()
        return True

    finally:
        with _browser_cache_lock:
            _browser_cache_populating = False
        # Always close the dedicated connection when done
        try:
            ableton.disconnect()
        except Exception:
            pass


def _get_browser_cache() -> List[Dict[str, Any]]:
    """Get the flat browser cache. Use refresh_browser_cache to force a rescan."""
    with _browser_cache_lock:
        return _browser_cache_flat


# ---------------------------------------------------------------------------
# Tool call instrumentation — captures all 131 tool calls for the dashboard
# ---------------------------------------------------------------------------
_original_call_tool = mcp.call_tool


async def _instrumented_call_tool(name: str, arguments: dict) -> Any:
    """Wrap every tool call to record metrics for the dashboard."""
    start = time.time()
    error_msg = None
    try:
        result = await _original_call_tool(name, arguments)
        return result
    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration = time.time() - start
        entry = {
            "tool": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round(duration * 1000, 1),
            "error": error_msg,
            "args_summary": _summarize_args(arguments),
        }
        with _tool_call_lock:
            _tool_call_log.append(entry)
            _tool_call_counts[name] = _tool_call_counts.get(name, 0) + 1


mcp.call_tool = _instrumented_call_tool


def _summarize_args(args: dict) -> str:
    """Create a short summary of tool arguments for the dashboard log."""
    if not args:
        return ""
    parts = []
    for k, v in list(args.items())[:3]:
        sv = str(v)
        if len(sv) > 40:
            sv = sv[:37] + "..."
        parts.append(f"{k}={sv}")
    suffix = f" +{len(args)-3} more" if len(args) > 3 else ""
    return ", ".join(parts) + suffix


# ---------------------------------------------------------------------------
# Web Status Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AbletonMCP Beta — Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: #0d1117; color: #c9d1d9; line-height: 1.5;
  }
  .container { max-width: 960px; margin: 0 auto; padding: 24px; }
  h1 { color: #58a6ff; font-size: 1.6rem; margin-bottom: 4px; }
  .subtitle { color: #8b949e; font-size: 0.85rem; margin-bottom: 24px; }
  .grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px; margin-bottom: 24px;
  }
  .card {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;
  }
  .card-label {
    font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em;
  }
  .card-value { font-size: 1.5rem; font-weight: 600; margin-top: 4px; }
  .status-ok  { color: #3fb950; }
  .status-err { color: #f85149; }
  .status-warn { color: #d29922; }
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; color: #8b949e; font-size: 0.75rem; text-transform: uppercase;
    padding: 8px 12px; border-bottom: 1px solid #30363d;
  }
  td { padding: 6px 12px; border-bottom: 1px solid #21262d; font-size: 0.85rem; }
  tr:hover { background: #161b22; }
  .error-cell { color: #f85149; }
  .section {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 16px; margin-bottom: 24px;
  }
  .section h2 { font-size: 1rem; color: #58a6ff; margin-bottom: 12px; }
  .refresh-bar {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;
  }
  .refresh-bar span { font-size: 0.75rem; color: #8b949e; }
  #countdown { color: #58a6ff; }
  .bar-row {
    display: flex; align-items: center; margin-bottom: 6px; font-size: 0.8rem;
  }
  .bar-name { width: 240px; color: #8b949e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bar-track { flex: 1; background: #21262d; border-radius: 4px; height: 20px; position: relative; }
  .bar-fill { background: #1f6feb; border-radius: 4px; height: 100%; min-width: 2px; }
  .bar-count { position: absolute; top: 0; left: 8px; line-height: 20px; font-size: 0.7rem; color: #c9d1d9; }
  .empty-msg { color: #484f58; font-style: italic; font-size: 0.85rem; }
  .status-banner {
    padding: 10px 16px; border-radius: 8px; margin-bottom: 16px;
    font-size: 0.85rem; font-weight: 500; display: flex; align-items: center; gap: 8px;
  }
  .status-banner .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .banner-ok { background: #0d2818; border: 1px solid #238636; color: #3fb950; }
  .banner-ok .dot { background: #3fb950; }
  .banner-warn { background: #2a1f00; border: 1px solid #9e6a03; color: #d29922; }
  .banner-warn .dot { background: #d29922; }
  .banner-err { background: #2d0a0a; border: 1px solid #da3633; color: #f85149; }
  .banner-err .dot { background: #f85149; }
</style>
</head>
<body>
<div class="container">
  <div class="refresh-bar">
    <div><h1>AbletonMCP Beta</h1><div class="subtitle">Status Dashboard</div></div>
    <span>Refresh in <span id="countdown">3</span>s</span>
  </div>
  <div id="status-banner"></div>
  <div class="grid" id="cards"></div>
  <div class="section" id="top-tools-section"></div>
  <div class="section">
    <h2>Recent Tool Calls</h2>
    <div id="log-area"></div>
  </div>
  <div class="section">
    <h2>Server Log</h2>
    <div id="server-log" style="
      background:#0d1117; border:1px solid #30363d; border-radius:6px;
      padding:12px; max-height:400px; overflow-y:auto; font-family:'Cascadia Code','Fira Code','Consolas',monospace;
      font-size:0.78rem; line-height:1.6;
    "></div>
  </div>
</div>
<script>
const REFRESH_MS = 3000;
let countdown = 3;
function fmtUp(s) {
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = Math.floor(s%60);
  return (h>0?h+'h ':'')+(m>0?m+'m ':'')+sec+'s';
}
async function refresh() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    // Status banner
    const sb = document.getElementById('status-banner');
    if (d.ableton_connected && d.m4l_connected) {
      sb.innerHTML = '<div class="status-banner banner-ok"><span class="dot"></span>All systems operational — Ableton + M4L Bridge connected and ready</div>';
    } else if (d.ableton_connected && !d.m4l_connected) {
      sb.innerHTML = '<div class="status-banner banner-warn"><span class="dot"></span>Ableton connected — M4L Bridge '+(d.m4l_sockets_ready?'waiting for device response':'not connected')+'</div>';
    } else {
      sb.innerHTML = '<div class="status-banner banner-err"><span class="dot"></span>Ableton not connected — make sure the Remote Script is loaded</div>';
    }
    document.getElementById('cards').innerHTML = [
      card('Server Version', d.version, ''),
      card('Uptime', fmtUp(d.uptime_seconds), ''),
      card('Ableton', d.ableton_connected?'Connected':'Disconnected',
           d.ableton_connected?'status-ok':'status-err'),
      card('M4L Bridge',
           d.m4l_connected?'Connected':d.m4l_sockets_ready?'Sockets Ready':'Disconnected',
           d.m4l_connected?'status-ok':d.m4l_sockets_ready?'status-warn':'status-err'),
      card('Snapshots', d.store_counts.snapshots, ''),
      card('Macros', d.store_counts.macros, ''),
      card('Param Maps', d.store_counts.param_maps, ''),
      card('Total Tool Calls', d.total_tool_calls, ''),
    ].join('');
    // Top tools
    const tt = document.getElementById('top-tools-section');
    if (d.top_tools.length) {
      const max = d.top_tools[0][1];
      tt.innerHTML = '<h2>Most Used Tools</h2>' + d.top_tools.map(([n,c])=>
        '<div class="bar-row"><span class="bar-name">'+n+'</span>'+
        '<div class="bar-track"><div class="bar-fill" style="width:'+(c/max*100).toFixed(1)+'%"></div>'+
        '<span class="bar-count">'+c+'</span></div></div>'
      ).join('');
    } else { tt.innerHTML = '<h2>Most Used Tools</h2><p class="empty-msg">No tool calls yet</p>'; }
    // Log
    const la = document.getElementById('log-area');
    if (d.recent_calls.length) {
      la.innerHTML = '<table><thead><tr><th>Time</th><th>Tool</th><th>Duration</th><th>Args</th><th>Status</th></tr></thead><tbody>'+
        d.recent_calls.slice().reverse().map(e=>
          '<tr><td>'+(e.timestamp.split('T')[1]||'').slice(0,8)+'</td>'+
          '<td>'+e.tool+'</td><td>'+e.duration_ms+'ms</td>'+
          '<td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+(e.args_summary||'')+'</td>'+
          '<td class="'+(e.error?'error-cell':'')+'">'+(e.error||'OK')+'</td></tr>'
        ).join('')+'</tbody></table>';
    } else { la.innerHTML = '<p class="empty-msg">No tool calls yet</p>'; }
    // Server log
    const sl = document.getElementById('server-log');
    if (d.server_logs && d.server_logs.length) {
      const colors = {INFO:'#8b949e',WARNING:'#d29922',ERROR:'#f85149',DEBUG:'#484f58',CRITICAL:'#f85149'};
      sl.innerHTML = d.server_logs.map(e=>{
        const c = colors[e.level]||'#8b949e';
        const lvl = e.level.padEnd(7);
        return '<div><span style="color:#484f58">'+e.ts+'</span> <span style="color:'+c+'">'+
               lvl+'</span> '+escHtml(e.msg)+'</div>';
      }).join('');
      sl.scrollTop = sl.scrollHeight;
    } else { sl.innerHTML = '<div style="color:#484f58;font-style:italic">No log entries yet</div>'; }
  } catch(err) { console.error('Dashboard refresh failed:', err); }
  countdown = REFRESH_MS/1000;
}
function card(label, value, cls) {
  return '<div class="card"><div class="card-label">'+label+'</div>'+
         '<div class="card-value '+(cls||'')+'">'+value+'</div></div>';
}
function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
refresh();
setInterval(refresh, REFRESH_MS);
setInterval(()=>{countdown=Math.max(0,countdown-1);
  document.getElementById('countdown').textContent=countdown;},1000);
</script>
</body>
</html>"""


def _get_server_version() -> str:
    """Get server version from package metadata, with fallback."""
    try:
        from importlib.metadata import version as _pkg_version
        return _pkg_version("ableton-mcp-stable")
    except Exception:
        return "1.9.0"


def _get_m4l_status() -> tuple:
    """Return (sockets_ready, bridge_responding) with cached ping."""
    sockets_ready = bool(_m4l_connection and _m4l_connection._connected)
    if not sockets_ready:
        return False, False

    now = time.time()
    if now - _m4l_ping_cache["timestamp"] < _M4L_PING_CACHE_TTL:
        return sockets_ready, _m4l_ping_cache["result"]

    try:
        result = _m4l_connection.ping()
    except Exception:
        result = False

    _m4l_ping_cache["result"] = result
    _m4l_ping_cache["timestamp"] = now
    return sockets_ready, result


def _build_status_json() -> dict:
    """Collect all dashboard status data into a JSON-serializable dict."""
    ableton_connected = False
    if _ableton_connection and _ableton_connection.sock:
        try:
            _ableton_connection.sock.getpeername()
            ableton_connected = True
        except Exception:
            pass

    m4l_sockets_ready, m4l_connected = _get_m4l_status()

    with _tool_call_lock:
        recent = list(_tool_call_log)
        total = sum(_tool_call_counts.values())
        top_tools = sorted(_tool_call_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    with _server_log_lock:
        # Format timestamps from stored tuples (created_float, level, msg)
        server_logs = [
            {"ts": datetime.fromtimestamp(ts).strftime("%H:%M:%S"), "level": lvl, "msg": msg}
            for ts, lvl, msg in _server_log_buffer
        ]

    return {
        "version": _get_server_version(),
        "uptime_seconds": round(time.time() - _server_start_time, 1) if _server_start_time else 0,
        "ableton_connected": ableton_connected,
        "m4l_connected": m4l_connected,
        "m4l_sockets_ready": m4l_sockets_ready,
        "store_counts": {
            "snapshots": len(_snapshot_store),
            "macros": len(_macro_store),
            "param_maps": len(_param_map_store),
        },
        "total_tool_calls": total,
        "top_tools": top_tools,
        "recent_calls": recent,
        "server_logs": server_logs,
        "tool_count": 131,
    }


def _start_dashboard_server():
    """Start the dashboard HTTP server on a background thread."""
    global _dashboard_server
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, JSONResponse
    from starlette.routing import Route
    import uvicorn

    async def dashboard_page(request):
        return HTMLResponse(DASHBOARD_HTML)

    async def api_status(request):
        return JSONResponse(_build_status_json())

    app = Starlette(routes=[
        Route("/", dashboard_page),
        Route("/api/status", api_status),
    ])

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=DASHBOARD_PORT,
        log_level="warning",
        access_log=False,
    )
    _dashboard_server = uvicorn.Server(config)

    def _run():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_dashboard_server.serve())

    thread = threading.Thread(target=_run, daemon=True, name="dashboard-http")
    thread.start()
    logger.info("Dashboard started at http://127.0.0.1:%d", DASHBOARD_PORT)


def _stop_dashboard_server():
    """Signal the dashboard server to shut down."""
    global _dashboard_server
    if _dashboard_server:
        _dashboard_server.should_exit = True
        _dashboard_server = None
        logger.info("Dashboard server stopped")


def get_ableton_connection():
    """Get or create a persistent Ableton connection"""
    global _ableton_connection
    
    if _ableton_connection is not None:
        try:
            # Test if the socket is still connected
            if _ableton_connection.sock is None:
                raise ConnectionError("Socket is None")
            _ableton_connection.sock.settimeout(1.0)
            _ableton_connection.sock.getpeername()  # raises if disconnected
            return _ableton_connection
        except Exception as e:
            logger.warning("Existing connection is no longer valid: %s", e)
            try:
                _ableton_connection.disconnect()
            except Exception:
                pass
            _ableton_connection = None
    
    # Connection doesn't exist or is invalid, create a new one
    if _ableton_connection is None:
        # Try to connect up to 3 times with a short delay between attempts
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info("Connecting to Ableton (attempt %d/%d)...", attempt, max_attempts)
                _ableton_connection = AbletonConnection(host="localhost", port=9877)
                if _ableton_connection.connect():
                    logger.info("Created new persistent connection to Ableton")
                    
                    # Validate connection with a simple command
                    try:
                        # Get session info as a test
                        _ableton_connection.send_command("get_session_info")
                        logger.info("Connection validated successfully")
                        return _ableton_connection
                    except Exception as e:
                        logger.error("Connection validation failed: %s", e)
                        _ableton_connection.disconnect()
                        _ableton_connection = None
                        # Continue to next attempt
                else:
                    _ableton_connection = None
            except Exception as e:
                logger.error("Connection attempt %d failed: %s", attempt, e)
                if _ableton_connection:
                    _ableton_connection.disconnect()
                    _ableton_connection = None
            
            # Wait before trying again, but only if we have more attempts left
            if attempt < max_attempts:
                time.sleep(1.0)
        
        # If we get here, all connection attempts failed
        if _ableton_connection is None:
            logger.error("Failed to connect to Ableton after multiple attempts")
            raise Exception("Could not connect to Ableton. Make sure the Remote Script is running.")
    
    return _ableton_connection


def get_m4l_connection() -> M4LConnection:
    """Get or create a connection to the M4L bridge device.

    Always attempts a fresh connection if the existing one is dead.
    Includes a ping to verify the M4L device is actually responding.
    """
    global _m4l_connection

    # If we have a connected instance, verify it still works with a ping
    if _m4l_connection is not None and _m4l_connection._connected:
        if _m4l_connection.ping():
            return _m4l_connection
        # Ping failed — tear down and try fresh
        logger.warning("M4L bridge ping failed on existing connection, reconnecting...")
        _m4l_connection.disconnect()
        _m4l_connection = None

    # Create a fresh connection
    _m4l_connection = M4LConnection()
    if not _m4l_connection.connect():
        _m4l_connection = None
        raise ConnectionError(
            "Could not initialise M4L bridge UDP sockets. "
            "Check that port 9879 is not already in use."
        )

    # Quick ping to verify the device is actually responding
    if not _m4l_connection.ping():
        logger.warning("M4L UDP sockets ready but bridge device is not responding.")
        # Keep the sockets open — the device might be loaded later
        # Don't tear down, so the next call can retry the ping
        raise ConnectionError(
            "M4L bridge device is not responding. "
            "Make sure the AbletonMCP_Bridge M4L device is loaded on a track in Ableton."
        )

    logger.info("M4L bridge connection established and verified.")
    return _m4l_connection


def _m4l_batch_set_params(
    m4l: M4LConnection,
    track_index: int,
    device_index: int,
    parameters: List[Dict],
) -> Dict[str, Any]:
    """Set multiple hidden parameters by sending individual set_hidden_param
    commands sequentially.  More reliable than the base64-encoded batch OSC
    approach which can fail with longer payloads in Max.

    Returns a dict with keys: params_set, params_failed, total_requested, errors.
    """
    ok = 0
    failed = 0
    errors: List[str] = []
    for p in parameters:
        try:
            result = m4l.send_command("set_hidden_param", {
                "track_index": track_index,
                "device_index": device_index,
                "parameter_index": int(p["index"]),
                "value": float(p["value"]),
            })
            if result.get("status") == "success":
                ok += 1
            else:
                failed += 1
                errors.append(f"[{p['index']}]: {result.get('message', '?')}")
        except Exception as e:
            failed += 1
            errors.append(f"[{p['index']}]: {str(e)}")
        # Small delay to let Ableton breathe when setting many params
        if len(parameters) > 6:
            time.sleep(0.05)
    return {
        "params_set": ok,
        "params_failed": failed,
        "total_requested": ok + failed,
        "errors": errors,
    }


# --- Input validation helpers ---

def _validate_index(value: int, name: str) -> None:
    """Validate that an index is a non-negative integer."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value}.")


def _validate_index_allow_negative(value: int, name: str, min_value: int = -1) -> None:
    """Validate an index that allows a specific negative sentinel (e.g. -1 for 'end')."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    if value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}.")


def _validate_range(value: float, name: str, min_val: float, max_val: float) -> None:
    """Validate that a numeric value falls within [min_val, max_val]."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number.")
    if value < min_val or value > max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {value}.")


def _validate_notes(notes: list) -> None:
    """Validate the structure of a MIDI notes list."""
    if not isinstance(notes, list):
        raise ValueError("notes must be a list.")
    if len(notes) == 0:
        raise ValueError("notes list must not be empty.")
    required_keys = {"pitch", "start_time", "duration", "velocity"}
    for i, note in enumerate(notes):
        if not isinstance(note, dict):
            raise ValueError(f"Each note must be a dictionary (note at index {i} is not).")
        missing = required_keys - note.keys()
        if missing:
            raise ValueError(
                f"Note at index {i} is missing required keys: {', '.join(sorted(missing))}."
            )
        pitch = note["pitch"]
        if not isinstance(pitch, int) or isinstance(pitch, bool) or pitch < 0 or pitch > 127:
            raise ValueError(
                f"Note at index {i}: pitch must be an integer between 0 and 127, got {pitch}."
            )
        velocity = note["velocity"]
        if not isinstance(velocity, (int, float)) or isinstance(velocity, bool) or velocity < 0 or velocity > 127:
            raise ValueError(
                f"Note at index {i}: velocity must be a number between 0 and 127, got {velocity}."
            )
        duration = note["duration"]
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
            raise ValueError(
                f"Note at index {i}: duration must be a positive number, got {duration}."
            )
        start_time = note["start_time"]
        if not isinstance(start_time, (int, float)) or isinstance(start_time, bool) or start_time < 0:
            raise ValueError(
                f"Note at index {i}: start_time must be a non-negative number, got {start_time}."
            )


def _validate_automation_points(points: list) -> None:
    """Validate the structure of automation points."""
    if not isinstance(points, list):
        raise ValueError("automation_points must be a list.")
    if len(points) == 0:
        raise ValueError("automation_points list must not be empty.")
    for i, point in enumerate(points):
        if not isinstance(point, dict):
            raise ValueError(
                f"Each automation point must be a dictionary (point at index {i} is not)."
            )
        if "time" not in point or "value" not in point:
            raise ValueError(
                f"Automation point at index {i} must have 'time' and 'value' keys."
            )
        time_val = point["time"]
        if not isinstance(time_val, (int, float)) or isinstance(time_val, bool) or time_val < 0:
            raise ValueError(
                f"Automation point at index {i}: time must be a non-negative number, got {time_val}."
            )
        val = point["value"]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise ValueError(
                f"Automation point at index {i}: value must be a number, got {val}."
            )


def _perpendicular_distance(at, av, bt, bv, ct, cv):
    """Perpendicular distance of point B from line A→C (pre-normalized coords)."""
    dt = ct - at
    dv = cv - av
    length_sq = dt * dt + dv * dv
    if length_sq == 0.0:
        return math.sqrt((bt - at) ** 2 + (bv - av) ** 2)
    return abs(dv * (bt - at) - dt * (bv - av)) / math.sqrt(length_sq)


def _rdp_recursive(norm_points, epsilon):
    """Ramer-Douglas-Peucker on list of (norm_t, norm_v, original_dict)."""
    if len(norm_points) <= 2:
        return [p[2] for p in norm_points]
    first = norm_points[0]
    last = norm_points[-1]
    max_dist = 0.0
    max_idx = 1
    for i in range(1, len(norm_points) - 1):
        p = norm_points[i]
        d = _perpendicular_distance(first[0], first[1], p[0], p[1], last[0], last[1])
        if d > max_dist:
            max_dist = d
            max_idx = i
    if max_dist > epsilon:
        left = _rdp_recursive(norm_points[:max_idx + 1], epsilon)
        right = _rdp_recursive(norm_points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [first[2], last[2]]


def _reduce_automation_points(points, max_points=20, time_epsilon=0.001,
                               collinear_epsilon=0.005):
    """Reduce automation point density while preserving shape.

    Three-stage pipeline:
    1. Sort by time, deduplicate points at same/close times (keep last)
    2. Remove collinear points (redundant under linear interpolation)
    3. If still over max_points, apply RDP simplification
    """
    if len(points) <= 2:
        return points

    original_count = len(points)

    # Stage 1: sort by time, deduplicate clustered times
    sorted_pts = sorted(points, key=lambda p: (p["time"], p.get("value", 0)))
    deduped = [sorted_pts[0]]
    for pt in sorted_pts[1:]:
        if pt["time"] - deduped[-1]["time"] < time_epsilon:
            deduped[-1] = pt  # last value at this time wins
        else:
            deduped.append(pt)

    if len(deduped) <= 2:
        if len(deduped) != original_count:
            logger.info("Automation point reduction: %d -> %d points", original_count, len(deduped))
        return deduped

    # Normalization spans for stages 2 and 3
    times = [p["time"] for p in deduped]
    values = [p["value"] for p in deduped]
    t_min, t_max = min(times), max(times)
    v_min, v_max = min(values), max(values)
    t_span = (t_max - t_min) or 1.0
    v_span = (v_max - v_min) or 1.0

    def nt(t):
        return (t - t_min) / t_span

    def nv(v):
        return (v - v_min) / v_span

    # Stage 2: remove collinear points
    result = [deduped[0]]
    for i in range(1, len(deduped) - 1):
        A = result[-1]
        B = deduped[i]
        C = deduped[i + 1]
        dist = _perpendicular_distance(
            nt(A["time"]), nv(A["value"]),
            nt(B["time"]), nv(B["value"]),
            nt(C["time"]), nv(C["value"]),
        )
        if dist > collinear_epsilon:
            result.append(B)
    result.append(deduped[-1])

    # Stage 3: RDP cap if still over max_points
    if len(result) > max_points:
        norm_pts = [(nt(p["time"]), nv(p["value"]), p) for p in result]
        eps = 0.005
        for _ in range(20):
            reduced = _rdp_recursive(norm_pts, eps)
            if len(reduced) <= max_points:
                result = reduced
                break
            eps *= 2.0
        else:
            # Fallback: uniform sampling
            indices = [0, len(result) - 1]
            for j in range(1, max_points - 1):
                idx = round(j * (len(result) - 1) / (max_points - 1))
                if idx not in indices:
                    indices.append(idx)
            indices.sort()
            result = [result[i] for i in indices[:max_points]]

    if len(result) != original_count:
        logger.info("Automation point reduction: %d -> %d points", original_count, len(result))

    return result


# ---------------------------------------------------------------------------
# Shared tool helpers
# ---------------------------------------------------------------------------

def _tool_handler(error_prefix: str):
    """Decorator that wraps tool functions with standard error handling.

    Catches ValueError -> "Invalid input: ...",
    ConnectionError -> "M4L bridge not available: ...",
    Exception -> "Error {prefix}: ..."
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                return f"Invalid input: {e}"
            except ConnectionError as e:
                return f"M4L bridge not available: {e}"
            except Exception as e:
                logger.error("Error %s: %s", error_prefix, e)
                return f"Error {error_prefix}: {e}"
        return wrapper
    return decorator


def _m4l_result(result: dict) -> dict:
    """Extract result data from M4L response, or raise on error."""
    if result.get("status") == "success":
        return result.get("result", {})
    msg = result.get("message", "Unknown error")
    raise Exception(f"M4L bridge error: {msg}")


# Core Tool endpoints

@mcp.tool()
@_tool_handler("getting session info")
def get_session_info(ctx: Context) -> str:
    """Get detailed information about the current Ableton session"""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_session_info")
    return json.dumps(result)

@mcp.tool()
@_tool_handler("getting track info")
def get_track_info(ctx: Context, track_index: int) -> str:
    """
    Get detailed information about a specific track in Ableton.

    Parameters:
    - track_index: The index of the track to get information about
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_track_info", {"track_index": track_index})
    return json.dumps(result)

@mcp.tool()
@_tool_handler("creating MIDI track")
def create_midi_track(ctx: Context, index: int = -1) -> str:
    """
    Create a new MIDI track in the Ableton session.

    Parameters:
    - index: The index to insert the track at (-1 = end of list)
    """
    _validate_index_allow_negative(index, "index", min_value=-1)
    ableton = get_ableton_connection()
    result = ableton.send_command("create_midi_track", {"index": index})
    return f"Created new MIDI track: {result.get('name', 'unknown')}"

@mcp.tool()
@_tool_handler("creating audio track")
def create_audio_track(ctx: Context, index: int = -1) -> str:
    """
    Create a new audio track in the Ableton session.

    Parameters:
    - index: The index to insert the track at (-1 = end of list)
    """
    _validate_index_allow_negative(index, "index", min_value=-1)
    ableton = get_ableton_connection()
    result = ableton.send_command("create_audio_track", {"index": index})
    return f"Created new audio track: {result.get('name', 'unknown')}"


@mcp.tool()
@_tool_handler("setting track name")
def set_track_name(ctx: Context, track_index: int, name: str) -> str:
    """
    Set the name of a track.

    Parameters:
    - track_index: The index of the track to rename
    - name: The new name for the track
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_name", {"track_index": track_index, "name": name})
    return f"Renamed track to: {result.get('name', name)}"

@mcp.tool()
@_tool_handler("creating clip")
def create_clip(ctx: Context, track_index: int, clip_index: int, length: float = 4.0) -> str:
    """
    Create a new MIDI clip in the specified track and clip slot.

    Parameters:
    - track_index: The index of the track to create the clip in
    - clip_index: The index of the clip slot to create the clip in
    - length: The length of the clip in beats (default: 4.0)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    if not isinstance(length, (int, float)) or isinstance(length, bool) or length <= 0:
        raise ValueError(f"length must be a positive number, got {length}.")
    ableton = get_ableton_connection()
    result = ableton.send_command("create_clip", {
        "track_index": track_index, 
        "clip_index": clip_index, 
        "length": length
    })
    return f"Created new clip at track {track_index}, slot {clip_index} with length {length} beats"

@mcp.tool()
@_tool_handler("adding notes to clip")
def add_notes_to_clip(
    ctx: Context, 
    track_index: int, 
    clip_index: int, 
    notes: List[Dict[str, Union[int, float, bool]]]
) -> str:
    """
    Add MIDI notes to a clip.

    Standard note adding. Use add_notes_extended when you need to set
    probability or velocity deviation (Live 11+).

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - notes: List of note dictionaries, each with pitch, start_time, duration, velocity, and mute
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    _validate_notes(notes)
    ableton = get_ableton_connection()
    result = ableton.send_command("add_notes_to_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes": notes
    })
    return f"Added {len(notes)} notes to clip at track {track_index}, slot {clip_index}"
@mcp.tool()
@_tool_handler("setting clip name")
def set_clip_name(ctx: Context, track_index: int, clip_index: int, name: str) -> str:
    """
    Set the name of a clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - name: The new name for the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_name", {
        "track_index": track_index,
        "clip_index": clip_index,
        "name": name
    })
    return f"Renamed clip at track {track_index}, slot {clip_index} to '{name}'"

@mcp.tool()
@_tool_handler("deleting clip")
def delete_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Delete a clip from a clip slot.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("delete_clip", {
        "track_index": track_index,
        "clip_index": clip_index
    })
    return f"Deleted clip at track {track_index}, slot {clip_index}"

@mcp.tool()
@_tool_handler("getting clip notes")
def get_clip_notes(ctx: Context, track_index: int, clip_index: int,
                   start_time: float = 0.0, time_span: float = 0.0,
                   start_pitch: int = 0, pitch_span: int = 128) -> str:
    """
    Get MIDI notes from a clip.

    Basic note reading without note IDs. For probability/velocity deviation
    data, use get_notes_extended. For in-place editing with stable note IDs,
    use get_clip_notes_with_ids (requires M4L bridge).

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - start_time: Start time in beats (default: 0.0)
    - time_span: Duration in beats to retrieve (default: 0.0 = entire clip)
    - start_pitch: Lowest MIDI pitch to retrieve (default: 0)
    - pitch_span: Range of pitches to retrieve (default: 128 = all pitches)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    _validate_range(start_pitch, "start_pitch", 0, 127)
    _validate_range(pitch_span, "pitch_span", 1, 128)
    if start_time < 0:
        raise ValueError(f"start_time must be non-negative, got {start_time}.")
    if time_span < 0:
        raise ValueError(f"time_span must be non-negative, got {time_span}.")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_clip_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "start_time": start_time,
        "time_span": time_span,
        "start_pitch": start_pitch,
        "pitch_span": pitch_span
    })
    return json.dumps(result)
@mcp.tool()
@_tool_handler("setting tempo")
def set_tempo(ctx: Context, tempo: float) -> str:
    """
    Set the tempo of the Ableton session.
    
    Parameters:
    - tempo: The new tempo in BPM
    """
    _validate_range(tempo, "tempo", 20.0, 999.0)
    ableton = get_ableton_connection()
    result = ableton.send_command("set_tempo", {"tempo": tempo})
    return f"Set tempo to {tempo} BPM"


@mcp.tool()
@_tool_handler("loading instrument")
def load_instrument_or_effect(ctx: Context, track_index: int, uri: str) -> str:
    """
    Load an instrument or effect onto a track using its URI or device name.

    General-purpose device loader. Works for instruments, audio effects, MIDI
    effects, and presets. For native-only devices on Live 12.3+,
    insert_device_by_name is faster.

    Parameters:
    - track_index: The index of the track to load the instrument on
    - uri: The URI of the instrument/effect, OR a device name (resolved automatically).

    You can pass any Ableton instrument, audio effect, or MIDI effect name
    directly — no need to call search_browser first.  The server resolves the
    name to the correct URI using the browser cache.

    Common examples:
      Instruments: Analog, Drift, Operator, Sampler, Simpler, Wavetable
      Audio Effects: Reverb, Compressor, EQ Eight, Delay, Auto Filter, Limiter
      MIDI Effects: Arpeggiator, Chord, Scale, Velocity

    Examples:
      load_instrument_or_effect(track_index=0, uri="Analog")
      load_instrument_or_effect(track_index=2, uri="Reverb")
      load_instrument_or_effect(track_index=1, uri="Compressor")

    For presets or third-party items, use search_browser() to find the full URI.
    """
    _validate_index(track_index, "track_index")
    uri = _resolve_device_uri(uri)
    ableton = get_ableton_connection()
    result = ableton.send_command("load_browser_item", {
        "track_index": track_index,
        "item_uri": uri
    })

    # Check if the instrument was loaded successfully
    if result.get("loaded", False):
        new_devices = result.get("new_devices", [])
        if new_devices:
            return f"Loaded instrument with URI '{uri}' on track {track_index}. New devices: {', '.join(new_devices)}"
        else:
            devices = result.get("devices_after", [])
            return f"Loaded instrument with URI '{uri}' on track {track_index}. Devices on track: {', '.join(devices)}"
    else:
        return f"Failed to load instrument with URI '{uri}'"

@mcp.tool()
@_tool_handler("firing clip")
def fire_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Launch a clip in Session View. The clip starts from its beginning (or loop
    start). For arrangement playback, use start_playback instead.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("fire_clip", {
        "track_index": track_index,
        "clip_index": clip_index
    })
    return f"Started playing clip at track {track_index}, slot {clip_index}"

@mcp.tool()
@_tool_handler("stopping clip")
def stop_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Stop a clip in Session View. For stopping all playback, use stop_playback
    instead.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("stop_clip", {
        "track_index": track_index,
        "clip_index": clip_index
    })
    return f"Stopped clip at track {track_index}, slot {clip_index}"

@mcp.tool()
@_tool_handler("starting playback")
def start_playback(ctx: Context) -> str:
    """Start playing from the play position marker (like pressing Play). To resume
    from the current playhead without jumping, use continue_playing instead."""
    ableton = get_ableton_connection()
    result = ableton.send_command("start_playback")
    return "Started playback"

@mcp.tool()
@_tool_handler("stopping playback")
def stop_playback(ctx: Context) -> str:
    """Stop playing the Ableton session."""
    ableton = get_ableton_connection()
    result = ableton.send_command("stop_playback")
    return "Stopped playback"

@mcp.tool()
@_tool_handler("setting track volume")
def set_track_volume(ctx: Context, track_index: int, volume: float) -> str:
    """
    Set the volume of a track.

    Parameters:
    - track_index: The index of the track
    - volume: The new volume value (0.0 to 1.0, where 0.85 is approximately 0dB)
    """
    _validate_index(track_index, "track_index")
    _validate_range(volume, "volume", 0.0, 1.0)
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_volume", {
        "track_index": track_index,
        "volume": volume
    })
    return f"Set track {track_index} volume to {result.get('volume', volume)}"

@mcp.tool()
@_tool_handler("setting track pan")
def set_track_pan(ctx: Context, track_index: int, pan: float) -> str:
    """
    Set the panning of a track.

    Parameters:
    - track_index: The index of the track
    - pan: The new pan value (-1.0 = full left, 0.0 = center, 1.0 = full right)
    """
    _validate_index(track_index, "track_index")
    _validate_range(pan, "pan", -1.0, 1.0)
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_pan", {
        "track_index": track_index,
        "pan": pan
    })
    return f"Set track {track_index} pan to {result.get('pan', pan)}"

@mcp.tool()
@_tool_handler("setting track mute")
def set_track_mute(ctx: Context, track_index: int, mute: bool) -> str:
    """
    Set the mute state of a track.

    Parameters:
    - track_index: The index of the track
    - mute: True to mute, False to unmute
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_mute", {
        "track_index": track_index,
        "mute": mute
    })
    state = "muted" if result.get('mute', mute) else "unmuted"
    return f"Track {track_index} is now {state}"

@mcp.tool()
@_tool_handler("setting track solo")
def set_track_solo(ctx: Context, track_index: int, solo: bool) -> str:
    """
    Set the solo state of a track.

    Parameters:
    - track_index: The index of the track
    - solo: True to solo, False to unsolo
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_solo", {
        "track_index": track_index,
        "solo": solo
    })
    state = "soloed" if result.get('solo', solo) else "unsoloed"
    return f"Track {track_index} is now {state}"

@mcp.tool()
@_tool_handler("setting track arm")
def set_track_arm(ctx: Context, track_index: int, arm: bool) -> str:
    """
    Set the arm (record enable) state of a track.

    Parameters:
    - track_index: The index of the track
    - arm: True to arm, False to disarm
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_arm", {
        "track_index": track_index,
        "arm": arm
    })
    state = "armed" if result.get('arm', arm) else "disarmed"
    return f"Track {track_index} is now {state}"

@mcp.tool()
@_tool_handler("deleting device")
def delete_device(ctx: Context, track_index: int, device_index: int) -> str:
    """
    Delete a device from a track.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device to delete
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("delete_device", {
        "track_index": track_index,
        "device_index": device_index
    })
    return f"Deleted device '{result.get('device_name', 'unknown')}' from track {track_index}"

@mcp.tool()
@_tool_handler("deleting track")
def delete_track(ctx: Context, track_index: int) -> str:
    """
    Delete a track from the session.

    Parameters:
    - track_index: The index of the track to delete
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("delete_track", {"track_index": track_index})
    return f"Deleted track '{result.get('track_name', 'unknown')}' at index {track_index}"

@mcp.tool()
@_tool_handler("deleting scene")
def delete_scene(ctx: Context, scene_index: int) -> str:
    """
    Delete a scene from the session.

    Parameters:
    - scene_index: The index of the scene to delete
    """
    _validate_index(scene_index, "scene_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("delete_scene", {"scene_index": scene_index})
    return f"Deleted scene '{result.get('scene_name', 'unknown')}' at index {scene_index}"

@mcp.tool()
@_tool_handler("getting clip info")
def get_clip_info(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Get detailed information about a clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_clip_info", {
        "track_index": track_index,
        "clip_index": clip_index
    })
    return json.dumps(result)

@mcp.tool()
@_tool_handler("clearing clip notes")
def clear_clip_notes(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Remove all MIDI notes from a clip without deleting the clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("clear_clip_notes", {
        "track_index": track_index,
        "clip_index": clip_index
    })
    return f"Cleared {result.get('notes_removed', 0)} notes from clip at track {track_index}, slot {clip_index}"

@mcp.tool()
@_tool_handler("duplicating clip")
def duplicate_clip(ctx: Context, track_index: int, clip_index: int, target_clip_index: int) -> str:
    """
    Duplicate a clip to another clip slot on the same track.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the source clip slot
    - target_clip_index: The index of the target clip slot
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    _validate_index(target_clip_index, "target_clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("duplicate_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
        "target_clip_index": target_clip_index
    })
    return f"Duplicated clip from slot {clip_index} to slot {target_clip_index} on track {track_index}"

@mcp.tool()
@_tool_handler("duplicating track")
def duplicate_track(ctx: Context, track_index: int) -> str:
    """
    Duplicate a track with all its devices and clips.

    Parameters:
    - track_index: The index of the track to duplicate
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("duplicate_track", {"track_index": track_index})
    return f"Duplicated track '{result.get('source_name', 'unknown')}' to new track '{result.get('new_name', 'unknown')}' at index {result.get('new_index', 'unknown')}"

@mcp.tool()
@_tool_handler("quantizing clip notes")
def quantize_clip_notes(ctx: Context, track_index: int, clip_index: int, grid_size: float = 0.25) -> str:
    """
    Quantize MIDI notes in a clip to snap to a grid.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - grid_size: The grid size in beats (0.25 = 16th notes, 0.5 = 8th notes, 1.0 = quarter notes)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    if not isinstance(grid_size, (int, float)) or isinstance(grid_size, bool) or grid_size <= 0:
        raise ValueError(f"grid_size must be a positive number, got {grid_size}.")
    ableton = get_ableton_connection()
    result = ableton.send_command("quantize_clip_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "grid_size": grid_size
    })
    return f"Quantized {result.get('notes_quantized', 0)} notes to {grid_size} beat grid in clip at track {track_index}, slot {clip_index}"

@mcp.tool()
@_tool_handler("transposing clip notes")
def transpose_clip_notes(ctx: Context, track_index: int, clip_index: int, semitones: int) -> str:
    """
    Transpose all MIDI notes in a clip by a number of semitones.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - semitones: The number of semitones to transpose (positive = up, negative = down)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    _validate_range(semitones, "semitones", -127, 127)
    ableton = get_ableton_connection()
    result = ableton.send_command("transpose_clip_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "semitones": semitones
    })
    direction = "up" if semitones > 0 else "down"
    return f"Transposed {result.get('notes_transposed', 0)} notes {direction} by {abs(semitones)} semitones in clip at track {track_index}, slot {clip_index}"

@mcp.tool()
@_tool_handler("setting clip looping")
def set_clip_looping(ctx: Context, track_index: int, clip_index: int, looping: bool) -> str:
    """
    Set the looping state of a clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - looping: True to enable looping, False to disable
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_looping", {
        "track_index": track_index,
        "clip_index": clip_index,
        "looping": looping
    })
    state = "enabled" if result.get('looping', looping) else "disabled"
    return f"Looping {state} for clip at track {track_index}, slot {clip_index}"

@mcp.tool()
@_tool_handler("setting clip loop points")
def set_clip_loop_points(ctx: Context, track_index: int, clip_index: int,
                          loop_start: float, loop_end: float) -> str:
    """
    Set the LOOP region start and end points of a clip.

    Sets the loop boundaries (the region that repeats when looping is enabled).
    Different from set_clip_start_end which sets playback start/end markers.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - loop_start: The loop start position in beats
    - loop_end: The loop end position in beats
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    if loop_start < 0:
        raise ValueError(f"loop_start must be non-negative, got {loop_start}.")
    if loop_end < 0:
        raise ValueError(f"loop_end must be non-negative, got {loop_end}.")
    if loop_end <= loop_start:
        raise ValueError(f"loop_end ({loop_end}) must be greater than loop_start ({loop_start}).")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_loop_points", {
        "track_index": track_index,
        "clip_index": clip_index,
        "loop_start": loop_start,
        "loop_end": loop_end
    })
    return f"Set loop points for clip at track {track_index}, slot {clip_index}: start={result.get('loop_start', loop_start)}, end={result.get('loop_end', loop_end)}"
@mcp.tool()
@_tool_handler("setting clip color")
def set_clip_color(ctx: Context, track_index: int, clip_index: int, color_index: int) -> str:
    """
    Set the color of a clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - color_index: The color index (0-69, Ableton's color palette)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    _validate_range(color_index, "color_index", 0, 69)
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_color", {
        "track_index": track_index,
        "clip_index": clip_index,
        "color_index": color_index
    })
    return f"Set color index to {result.get('color_index', color_index)} for clip at track {track_index}, slot {clip_index}"

@mcp.tool()
@_tool_handler("getting scenes")
def get_scenes(ctx: Context) -> str:
    """Get information about all scenes in the session."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_scenes")
    return json.dumps(result)

@mcp.tool()
@_tool_handler("firing scene")
def fire_scene(ctx: Context, scene_index: int) -> str:
    """
    Fire (launch) a scene to start all clips in that row.

    Parameters:
    - scene_index: The index of the scene to fire
    """
    _validate_index(scene_index, "scene_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("fire_scene", {"scene_index": scene_index})
    return f"Fired scene {scene_index}: {result.get('scene_name', 'unknown')}"

@mcp.tool()
@_tool_handler("creating scene")
def create_scene(ctx: Context, index: int = -1) -> str:
    """
    Create a new scene in the session.

    Parameters:
    - index: The index to insert the scene at (-1 = end of list)
    """
    _validate_index_allow_negative(index, "index", min_value=-1)
    ableton = get_ableton_connection()
    result = ableton.send_command("create_scene", {"index": index})
    return f"Created new scene: {result.get('name', 'unknown')}"

@mcp.tool()
@_tool_handler("setting scene name")
def set_scene_name(ctx: Context, scene_index: int, name: str) -> str:
    """
    Set the name of a scene.

    Parameters:
    - scene_index: The index of the scene to rename
    - name: The new name for the scene
    """
    _validate_index(scene_index, "scene_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_scene_name", {
        "scene_index": scene_index,
        "name": name
    })
    return f"Renamed scene to: {result.get('name', name)}"

@mcp.tool()
@_tool_handler("getting return tracks")
def get_return_tracks(ctx: Context) -> str:
    """Get information about all return tracks."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_return_tracks")
    return json.dumps(result)

@mcp.tool()
@_tool_handler("getting return track info")
def get_return_track_info(ctx: Context, return_track_index: int) -> str:
    """
    Get detailed information about a specific return track.

    Parameters:
    - return_track_index: The index of the return track (0 = A, 1 = B, etc.)
    """
    _validate_index(return_track_index, "return_track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_return_track_info", {
        "return_track_index": return_track_index
    })
    return json.dumps(result)

@mcp.tool()
@_tool_handler("setting return track volume")
def set_return_track_volume(ctx: Context, return_track_index: int, volume: float) -> str:
    """
    Set the volume of a return track.

    Parameters:
    - return_track_index: The index of the return track (0 = A, 1 = B, etc.)
    - volume: The new volume value (0.0 to 1.0)
    """
    _validate_index(return_track_index, "return_track_index")
    _validate_range(volume, "volume", 0.0, 1.0)
    ableton = get_ableton_connection()
    result = ableton.send_command("set_return_track_volume", {
        "return_track_index": return_track_index,
        "volume": volume
    })
    return f"Set return track {return_track_index} volume to {result.get('volume', volume)}"

@mcp.tool()
@_tool_handler("setting return track pan")
def set_return_track_pan(ctx: Context, return_track_index: int, pan: float) -> str:
    """
    Set the panning of a return track.

    Parameters:
    - return_track_index: The index of the return track (0 = A, 1 = B, etc.)
    - pan: The new pan value (-1.0 = full left, 0.0 = center, 1.0 = full right)
    """
    _validate_index(return_track_index, "return_track_index")
    _validate_range(pan, "pan", -1.0, 1.0)
    ableton = get_ableton_connection()
    result = ableton.send_command("set_return_track_pan", {
        "return_track_index": return_track_index,
        "pan": pan
    })
    return f"Set return track {return_track_index} pan to {result.get('pan', pan)}"

@mcp.tool()
@_tool_handler("setting return track mute")
def set_return_track_mute(ctx: Context, return_track_index: int, mute: bool) -> str:
    """
    Set the mute state of a return track.

    Parameters:
    - return_track_index: The index of the return track (0 = A, 1 = B, etc.)
    - mute: True to mute, False to unmute
    """
    _validate_index(return_track_index, "return_track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_return_track_mute", {
        "return_track_index": return_track_index,
        "mute": mute
    })
    state = "muted" if result.get('mute', mute) else "unmuted"
    return f"Return track {return_track_index} is now {state}"

@mcp.tool()
@_tool_handler("setting return track solo")
def set_return_track_solo(ctx: Context, return_track_index: int, solo: bool) -> str:
    """
    Set the solo state of a return track.

    Parameters:
    - return_track_index: The index of the return track (0 = A, 1 = B, etc.)
    - solo: True to solo, False to unsolo
    """
    _validate_index(return_track_index, "return_track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_return_track_solo", {
        "return_track_index": return_track_index,
        "solo": solo
    })
    state = "soloed" if result.get('solo', solo) else "unsoloed"
    return f"Return track {return_track_index} is now {state}"

@mcp.tool()
@_tool_handler("setting track send")
def set_track_send(ctx: Context, track_index: int, send_index: int, value: float) -> str:
    """
    Set the send level from a track to a return track.

    Parameters:
    - track_index: The index of the source track
    - send_index: The index of the send (0 = Send A, 1 = Send B, etc.)
    - value: The send level (0.0 to 1.0)
    """
    _validate_index(track_index, "track_index")
    _validate_index(send_index, "send_index")
    _validate_range(value, "value", 0.0, 1.0)
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_send", {
        "track_index": track_index,
        "send_index": send_index,
        "value": value
    })
    return f"Set track {track_index} send {send_index} to {result.get('value', value)}"

@mcp.tool()
@_tool_handler("getting master track info")
def get_master_track_info(ctx: Context) -> str:
    """Get detailed information about the master track, including volume, panning, and devices."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_master_track_info")
    return json.dumps(result)

@mcp.tool()
@_tool_handler("setting master volume")
def set_master_volume(ctx: Context, volume: float) -> str:
    """
    Set the volume of the master track.

    Parameters:
    - volume: The new volume value (0.0 to 1.0, where 0.85 is approximately 0dB)
    """
    _validate_range(volume, "volume", 0.0, 1.0)
    ableton = get_ableton_connection()
    result = ableton.send_command("set_master_volume", {"volume": volume})
    return f"Set master volume to {result.get('volume', volume)}"

@mcp.tool()
@_tool_handler("getting browser tree")
def get_browser_tree(ctx: Context, category_type: str = "all") -> str:
    """
    Get a hierarchical tree of browser categories from Ableton.

    Uses cached browser data when available for richer results with URIs.

    Parameters:
    - category_type: Type of categories to get ('all', 'instruments', 'sounds', 'drums', 'audio_effects', 'midi_effects')
    """
    # Try to serve from cache first (richer data with URIs)
    cache = _get_browser_cache()
    if cache:
        # Filter categories
        if category_type == "all":
            show_categories = list(_CATEGORY_DISPLAY.values())
        else:
            show_categories = [_CATEGORY_DISPLAY.get(category_type, category_type)]

        formatted_output = f"Browser tree for '{category_type}':\n\n"
        for cat_display in show_categories:
            # Use category index for O(1) lookup instead of scanning all items
            cat_items = _browser_cache_by_category.get(cat_display, [])
            # Top-level items have paths like "sounds/Operator" (2 segments)
            top_items = [
                item for item in cat_items
                if item.get("path", "").count("/") == 1
            ]
            if not top_items:
                continue

            formatted_output += f"**{cat_display}** ({len(top_items)} items):\n"
            for item in sorted(top_items, key=lambda x: x.get("name", "")):
                loadable = " [loadable]" if item.get("is_loadable", False) else ""
                folder = " [+]" if item.get("is_folder", False) else ""
                formatted_output += f"  • {item['name']}{loadable}{folder}"
                if item.get("uri"):
                    formatted_output += f"  (URI: {item['uri']})"
                formatted_output += "\n"
            formatted_output += "\n"

        return formatted_output

    # Fallback: fetch from Ableton directly
    ableton = get_ableton_connection()
    result = ableton.send_command("get_browser_tree", {
        "category_type": category_type
    })

    if "available_categories" in result and len(result.get("categories", [])) == 0:
        available_cats = result.get("available_categories", [])
        return (f"No categories found for '{category_type}'. "
               f"Available browser categories: {', '.join(available_cats)}")

    total_folders = result.get("total_folders", 0)
    formatted_output = f"Browser tree for '{category_type}' (showing {total_folders} folders):\n\n"

    def format_tree(item, indent=0):
        output = ""
        if item:
            prefix = "  " * indent
            name = item.get("name", "Unknown")
            path = item.get("path", "")
            has_more = item.get("has_more", False)
            output += f"{prefix}• {name}"
            if path:
                output += f" (path: {path})"
            if has_more:
                output += " [...]"
            output += "\n"
            for child in item.get("children", []):
                output += format_tree(child, indent + 1)
        return output

    for category in result.get("categories", []):
        formatted_output += format_tree(category)
        formatted_output += "\n"

    return formatted_output

@mcp.tool()
@_tool_handler("getting browser items at path")
def get_browser_items_at_path(ctx: Context, path: str) -> str:
    """
    Get browser items at a specific path in Ableton's browser.
    
    Parameters:
    - path: Path in the format "category/folder/subfolder"
            where category is one of the available browser categories in Ableton
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("get_browser_items_at_path", {
        "path": path
    })
        
    # Check if there was an error with available categories
    if "error" in result and "available_categories" in result:
        error = result.get("error", "")
        available_cats = result.get("available_categories", [])
        return (f"Error: {error}\n"
               f"Available browser categories: {', '.join(available_cats)}")
        
    return json.dumps(result)

@mcp.tool()
@_tool_handler("getting device parameters")
def get_device_parameters(ctx: Context, track_index: int, device_index: int,
                           track_type: str = "track") -> str:
    """
    Get all parameters and their current values for a device on a track.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - track_type: Type of track: "track" (default), "return", or "master"
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if track_type not in ("track", "return", "master"):
        return "Error: track_type must be 'track', 'return', or 'master'"
    ableton = get_ableton_connection()
    result = ableton.send_command("get_device_parameters", {
        "track_index": track_index,
        "device_index": device_index,
        "track_type": track_type,
    })
    return json.dumps(result)
@mcp.tool()
@_tool_handler("setting device parameter")
def set_device_parameter(ctx: Context, track_index: int, device_index: int,
                          parameter_name: str, value: float,
                          track_type: str = "track") -> str:
    """
    Set a device parameter value.

    Use for a single standard parameter change. For multiple params at once,
    use set_device_parameters instead. For hidden/non-automatable params, use
    set_device_hidden_parameter (requires M4L bridge).

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - parameter_name: The name of the parameter to set
    - value: The new value for the parameter (will be clamped to min/max)
    - track_type: Type of track: "track" (default), "return", or "master"
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if track_type not in ("track", "return", "master"):
        return "Error: track_type must be 'track', 'return', or 'master'"
    ableton = get_ableton_connection()
    result = ableton.send_command("set_device_parameter", {
        "track_index": track_index,
        "device_index": device_index,
        "parameter_name": parameter_name,
        "value": value,
        "track_type": track_type,
    })
    pname = result.get('parameter', parameter_name)
    if result.get("clamped", False):
        return f"Set parameter '{pname}' to {result.get('value')} (value was clamped to valid range)"
    return f"Set parameter '{pname}' to {result.get('value')}"
@mcp.tool()
@_tool_handler("setting device parameters")
def set_device_parameters(ctx: Context, track_index: int, device_index: int,
                           parameters: str, track_type: str = "track") -> str:
    """
    Set multiple device parameters in a single call (much faster than setting one at a time).

    ALWAYS prefer this over calling set_device_parameter multiple times.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - parameters: JSON string of parameter list, e.g. '[{"name": "Filter Freq", "value": 0.5}, {"name": "Resonance", "value": 0.3}]'
    - track_type: Type of track: "track" (default), "return", or "master"
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if track_type not in ("track", "return", "master"):
        return "Error: track_type must be 'track', 'return', or 'master'"

    params_list = json.loads(parameters) if isinstance(parameters, str) else parameters
    if not isinstance(params_list, list) or not params_list:
        return "Error: parameters must be a non-empty JSON array of {name, value} objects"

    ableton = get_ableton_connection()
    result = ableton.send_command("set_device_parameters_batch", {
        "track_index": track_index,
        "device_index": device_index,
        "parameters": params_list,
        "track_type": track_type,
    })

    device_name = result.get("device_name", "?")
    results = result.get("results", [])
    ok = [r for r in results if "error" not in r]
    errs = [r for r in results if "error" in r]

    summary = f"Set {len(ok)} parameters on '{device_name}'"
    if errs:
        summary += f" ({len(errs)} not found: {', '.join(r['name'] for r in errs)})"
    return summary
@mcp.tool()
@_tool_handler("sending real-time parameter")
def realtime_set_parameter(ctx: Context, track_index: int, device_index: int,
                           parameter_name: str, value: float,
                           track_type: str = "track") -> str:
    """
    Set a device parameter via UDP for real-time control (fire-and-forget, no confirmation).

    Use this instead of set_device_parameter when you need rapid parameter changes
    (e.g., filter sweeps, volume ramps) where response confirmation is not needed.
    The value is applied immediately with minimal latency.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - parameter_name: The name of the parameter to set
    - value: The new value for the parameter (will be clamped to min/max)
    - track_type: Type of track: "track" (default), "return", or "master"
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if track_type not in ("track", "return", "master"):
        return "Error: track_type must be 'track', 'return', or 'master'"
    ableton = get_ableton_connection()
    ableton.send_udp_command("set_device_parameter", {
        "track_index": track_index,
        "device_index": device_index,
        "parameter_name": parameter_name,
        "value": value,
        "track_type": track_type,
    })
    return f"Sent real-time parameter update: '{parameter_name}' = {value} (fire-and-forget via UDP)"
@mcp.tool()
@_tool_handler("sending real-time batch parameters")
def realtime_batch_set_parameters(ctx: Context, track_index: int, device_index: int,
                                  parameters: str, track_type: str = "track") -> str:
    """
    Set multiple device parameters at once via UDP for real-time control (fire-and-forget).

    Use for rapid multi-param changes (e.g., morphing presets in real-time).
    No response confirmation — fire-and-forget. For confirmed batch updates,
    use set_device_parameters instead.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - parameters: JSON string of parameter list, e.g. '[{"name": "Filter Freq", "value": 0.5}]'
    - track_type: Type of track: "track" (default), "return", or "master"
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if track_type not in ("track", "return", "master"):
        return "Error: track_type must be 'track', 'return', or 'master'"

    params_list = json.loads(parameters) if isinstance(parameters, str) else parameters
    if not isinstance(params_list, list) or not params_list:
        return "Error: parameters must be a non-empty JSON array of {name, value} objects"

    ableton = get_ableton_connection()
    ableton.send_udp_command("batch_set_device_parameters", {
        "track_index": track_index,
        "device_index": device_index,
        "parameters": params_list,
        "track_type": track_type,
    })
    return f"Sent real-time batch update for {len(params_list)} parameters (fire-and-forget via UDP)"
@mcp.tool()
@_tool_handler("getting user library")
def get_user_library(ctx: Context) -> str:
    """
    Get the user library browser tree, including user folders and samples.
    Returns the browser structure for user-added content.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("get_user_library")
    return json.dumps(result)

@mcp.tool()
@_tool_handler("getting user folders")
def get_user_folders(ctx: Context) -> str:
    """
    Get user-configured sample folders from Ableton's browser.
    Note: Returns browser items (URIs), not raw filesystem paths.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("get_user_folders")
    return json.dumps(result)

def _resolve_sample_uri(uri_or_name: str) -> str:
    """Resolve a sample filename, query:UserLibrary URI, or LOM URI.

    Handles three input formats:
    1. ``query:UserLibrary#subfolder:filename.mp3`` — extracts filename, searches cache/live
    2. Real LOM URI (contains ':' but not 'query:') — returned as-is
    3. Plain filename or substring — searched in cache then live User Library
    """
    filename: str = ""  # set when parsing query: format

    # --- Handle query:UserLibrary#subfolder:filename format ---
    if uri_or_name.startswith("query:"):
        # "query:UserLibrary#eleven_labs_audio:filename.mp3" → filename = "filename.mp3"
        parts = uri_or_name.split(":")
        filename = parts[-1].strip() if len(parts) >= 3 else ""
        if filename:
            filename_lower = filename.lower()
            with _browser_cache_lock:
                snapshot = list(_browser_cache_flat)
            # exact name match
            for item in snapshot:
                if item.get("search_name") == filename_lower and item.get("uri"):
                    logger.info("Resolved query URI '%s' to '%s'", uri_or_name, item["uri"])
                    return item["uri"]
            # substring fallback
            for item in snapshot:
                if filename_lower in item.get("search_name", "") and item.get("uri"):
                    logger.info("Resolved query URI '%s' to '%s' (substring)", uri_or_name, item["uri"])
                    return item["uri"]
        # Not in cache — fall through to live lookup below

    # --- Already a real LOM URI (has ":" but not "query:") ---
    if (":" in uri_or_name or "#" in uri_or_name) and not uri_or_name.startswith("query:"):
        return uri_or_name

    # --- Plain filename: search cache ---
    name_lower = (filename or uri_or_name).strip().lower()
    with _browser_cache_lock:
        snapshot = list(_browser_cache_flat)
    # exact match
    for item in snapshot:
        if item.get("search_name") == name_lower and item.get("is_loadable") and item.get("uri"):
            logger.info("Resolved sample name '%s' to URI '%s'", uri_or_name, item["uri"])
            return item["uri"]
    # substring match
    for item in snapshot:
        sn = item.get("search_name", "")
        if name_lower in sn and item.get("is_loadable") and item.get("uri"):
            logger.info("Resolved sample name '%s' to URI '%s' (substring)", uri_or_name, item["uri"])
            return item["uri"]

    # --- Cache miss: live lookup of user_library subfolders ---
    _MAX_LIVE_LOOKUP_FOLDERS = 10
    try:
        logger.info("Sample '%s' not in cache, trying live User Library lookup", uri_or_name)
        ableton = get_ableton_connection()
        result = ableton.send_command("get_browser_items_at_path",
                                      {"path": "user_library"}, timeout=10.0)
        folder_count = 0
        for sub in result.get("items", []):
            if not sub.get("is_folder"):
                # Check non-folder items at root level too
                item_name = sub.get("name", "").lower()
                if name_lower in item_name and sub.get("uri"):
                    logger.info("Resolved sample '%s' via live lookup to '%s'",
                                uri_or_name, sub["uri"])
                    return sub["uri"]
                continue
            if folder_count >= _MAX_LIVE_LOOKUP_FOLDERS:
                break
            folder_count += 1
            time.sleep(0.05)
            sub_result = ableton.send_command(
                "get_browser_items_at_path",
                {"path": "user_library/" + sub["name"]},
                timeout=10.0,
            )
            for item in sub_result.get("items", []):
                if item.get("is_folder"):
                    continue
                item_name = item.get("name", "").lower()
                if name_lower in item_name and item.get("uri"):
                    logger.info("Resolved sample '%s' via live lookup to '%s'",
                                uri_or_name, item["uri"])
                    return item["uri"]
    except Exception as exc:
        logger.warning("Live User Library lookup failed: %s", exc)

    logger.warning("Could not resolve sample '%s' to a known URI, passing through as-is", uri_or_name)
    return uri_or_name


@mcp.tool()
@_tool_handler("loading sample")
def load_sample(ctx: Context, track_index: int, sample_uri: str) -> str:
    """
    Load an audio sample onto a track from the browser.

    Accepts a full browser URI, a ``query:UserLibrary#...`` style URI, or
    just a filename (resolved automatically via the browser cache).

    Parameters:
    - track_index: The index of the track to load the sample onto
    - sample_uri: The URI or filename of the sample (use get_user_library or search_browser to find URIs)
    """
    _validate_index(track_index, "track_index")
    resolved_uri = _resolve_sample_uri(sample_uri)
    ableton = get_ableton_connection()
    result = ableton.send_command("load_sample", {
        "track_index": track_index,
        "sample_uri": resolved_uri
    })
    if result.get("loaded", False):
        return f"Loaded sample '{result.get('item_name', result.get('sample_name', 'unknown'))}' onto track {track_index}"
    return f"Failed to load sample"

@mcp.tool()
@_tool_handler("creating clip automation")
def create_clip_automation(ctx: Context, track_index: int, clip_index: int,
                            parameter_name: str, automation_points: List[Dict[str, float]]) -> str:
    """Create automation for a parameter within a session clip.

    For automation inside a session clip's envelope. For arrangement-level track
    automation (Volume, Pan, etc. on the timeline), use create_track_automation instead.

    Parameters:
    - track_index: The index of the track
    - clip_index: The index of the clip slot
    - parameter_name: Name of the parameter to automate (e.g., "Osc 1 Pos", "Filter 1 Freq")
    - automation_points: List of {time: float, value: float} dictionaries

    IMPORTANT — use as FEW points as possible.  Ableton linearly interpolates
    between breakpoints, so a smooth ramp from 0→1 over 4 beats needs only
    2 points:  [{"time": 0, "value": 0}, {"time": 4, "value": 1}]
    For a triangle (up then down) use 3 points.  For gentle curves 4-8 max.
    Do NOT send 20+ points for simple shapes — it creates staircase artifacts.

    Values are in the parameter's native range (usually 0.0–1.0).
    Time is in beats from clip start.
    Any existing automation for this parameter is cleared before writing.
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    _validate_automation_points(automation_points)
    automation_points = _reduce_automation_points(automation_points)
    ableton = get_ableton_connection()
    result = ableton.send_command("create_clip_automation", {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_name": parameter_name,
        "automation_points": automation_points
    })
    pts = result.get("points_added", len(automation_points))
    return f"Created automation with {pts} points for parameter '{parameter_name}'"
# ======================================================================
# Arrangement View Workflow
# ======================================================================

@mcp.tool()
@_tool_handler("getting song transport")
def get_song_transport(ctx: Context) -> str:
    """
    Get the current transport/arrangement state of the Ableton session.

    Returns: current playback time, playing state, tempo, time signature,
    loop bracket settings, record mode, and song length.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("get_song_transport", {})
    return json.dumps(result)

@mcp.tool()
@_tool_handler("setting song time")
def set_song_time(ctx: Context, time: float) -> str:
    """
    Set the playback position (arrangement playhead).

    Parameters:
    - time: The position in beats to jump to (0.0 = start of song)
    """
    ableton = get_ableton_connection()
    ableton.send_command("set_song_time", {"time": time})
    return f"Playhead set to beat {time}"

@mcp.tool()
@_tool_handler("setting song loop")
def set_song_loop(ctx: Context, enabled: bool = None, start: float = None, length: float = None) -> str:
    """
    Control the arrangement loop bracket.

    Parameters:
    - enabled: True to enable looping, False to disable (optional)
    - start: Loop start position in beats (optional)
    - length: Loop length in beats (optional)
    """
    params = {}
    if enabled is not None:
        params["enabled"] = enabled
    if start is not None:
        params["start"] = start
    if length is not None:
        params["length"] = length
    ableton = get_ableton_connection()
    result = ableton.send_command("set_song_loop", params)
    # Use the values we sent, with result as fallback
    state = "enabled" if (enabled if enabled is not None else result.get("loop_enabled")) else "disabled"
    s = start if start is not None else result.get('loop_start', 0)
    l = length if length is not None else result.get('loop_length', 0)
    return f"Loop {state}: start={s}, length={l} beats"

@mcp.tool()
@_tool_handler("duplicating clip to arrangement")
def duplicate_clip_to_arrangement(ctx: Context, track_index: int, clip_index: int, time: float) -> str:
    """
    Copy a session clip to the arrangement timeline at a given beat position.

    This is the primary arrangement workflow tool — build clips in session view,
    then place them on the arrangement timeline.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - time: The beat position on the arrangement timeline to place the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("duplicate_clip_to_arrangement", {
        "track_index": track_index,
        "clip_index": clip_index,
        "time": time,
    })
    return (f"Placed clip '{result.get('clip_name', '')}' on arrangement at beat {result.get('placed_at', time)} "
            f"(track {track_index}, length {result.get('clip_length', '?')} beats)")

# ======================================================================
# Advanced Clip Operations
# ======================================================================

@mcp.tool()
@_tool_handler("cropping clip")
def crop_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Trim a clip to its current loop region, discarding content outside.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("crop_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    return f"Cropped clip '{result.get('clip_name', '')}' — new length: {result.get('new_length', '?')} beats"

@mcp.tool()
@_tool_handler("duplicating clip loop")
def duplicate_clip_loop(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    Double the loop content of a clip (e.g., 4 bars becomes 8 bars with content repeated).

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("duplicate_clip_loop", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    return (f"Doubled loop of clip '{result.get('clip_name', '')}' — "
            f"{result.get('old_length', '?')} → {result.get('new_length', '?')} beats")

@mcp.tool()
@_tool_handler("setting clip start/end markers")
def set_clip_start_end(ctx: Context, track_index: int, clip_index: int,
                       start_marker: float = None, end_marker: float = None) -> str:
    """
    Set clip start_marker and end_marker positions (controls playback region without changing notes).

    Sets the playback START/END markers, which are separate from the loop region.
    Different from set_clip_loop_points which sets the loop boundaries.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - start_marker: The new start marker position in beats (optional)
    - end_marker: The new end marker position in beats (optional)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    params = {"track_index": track_index, "clip_index": clip_index}
    if start_marker is not None:
        params["start_marker"] = start_marker
    if end_marker is not None:
        params["end_marker"] = end_marker
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_start_end", params)
    return (f"Clip '{result.get('clip_name', '')}' markers set — "
            f"start: {result.get('start_marker', '?')}, end: {result.get('end_marker', '?')}")
# ======================================================================
# Advanced MIDI Note Editing
# ======================================================================

@mcp.tool()
@_tool_handler("adding extended notes")
def add_notes_extended(ctx: Context, track_index: int, clip_index: int,
                       notes: List[Dict]) -> str:
    """
    Add MIDI notes with Live 11+ extended properties.

    Use instead of add_notes_to_clip when you need to set probability,
    velocity_deviation, or release_velocity on notes.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - notes: List of note dictionaries with:
        - pitch (int): MIDI note number (0-127)
        - start_time (float): Start position in beats
        - duration (float): Note duration in beats
        - velocity (int): Note velocity (1-127)
        - mute (bool): Whether the note is muted (optional, default false)
        - probability (float): Note trigger probability 0.0-1.0 (Live 11+, optional)
        - velocity_deviation (float): Random velocity range -127 to 127 (Live 11+, optional)
        - release_velocity (int): Note release velocity 0-127 (Live 11+, optional)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    if not notes:
        return "No notes provided"
    ableton = get_ableton_connection()
    result = ableton.send_command("add_notes_extended", {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes": notes,
    })
    ext = " (with extended properties)" if result.get("extended") else ""
    return f"Added {result.get('note_count', 0)} notes to clip{ext}"
@mcp.tool()
@_tool_handler("getting extended notes")
def get_notes_extended(ctx: Context, track_index: int, clip_index: int,
                       start_time: float = 0.0, time_span: float = 0.0) -> str:
    """
    Get MIDI notes with Live 11+ extended properties (probability, velocity_deviation, release_velocity).

    Use instead of get_clip_notes when you need probability, velocity_deviation,
    or release_velocity data. Does not include stable note IDs — for that, use
    get_clip_notes_with_ids (requires M4L bridge).

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - start_time: Start time in beats (default: 0.0)
    - time_span: Duration in beats to retrieve (default: 0.0 = entire clip)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_notes_extended", {
        "track_index": track_index,
        "clip_index": clip_index,
        "start_time": start_time,
        "time_span": time_span,
    })
    return json.dumps(result)
@mcp.tool()
@_tool_handler("removing notes range")
def remove_notes_range(ctx: Context, track_index: int, clip_index: int,
                       from_time: float = 0.0, time_span: float = 0.0,
                       from_pitch: int = 0, pitch_span: int = 128) -> str:
    """
    Selectively remove MIDI notes within a specific time and pitch range.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - from_time: Start time in beats (default: 0.0)
    - time_span: Time range in beats (default: 0.0 = entire clip)
    - from_pitch: Lowest MIDI pitch to remove (default: 0)
    - pitch_span: Range of pitches to remove (default: 128 = all)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("remove_notes_range", {
        "track_index": track_index,
        "clip_index": clip_index,
        "from_time": from_time,
        "time_span": time_span,
        "from_pitch": from_pitch,
        "pitch_span": pitch_span,
    })
    return f"Removed {result.get('notes_removed', 0)} notes from range (time={from_time}-{from_time+time_span}, pitch={from_pitch}-{from_pitch+pitch_span})"
# ======================================================================
# Automation Reading & Editing
# ======================================================================

@mcp.tool()
@_tool_handler("getting clip automation")
def get_clip_automation(ctx: Context, track_index: int, clip_index: int,
                        parameter_name: str) -> str:
    """
    Read existing automation from a clip for a specific parameter.

    Samples the automation envelope at 64 evenly-spaced points across the clip length.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - parameter_name: Name of the parameter (e.g., "Volume", "Pan", or any device parameter name)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_clip_automation", {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_name": parameter_name,
    })
    if not result.get("has_automation"):
        reason = result.get("reason", "No automation found")
        return f"No automation for '{parameter_name}': {reason}"
    return json.dumps(result)
@mcp.tool()
@_tool_handler("clearing clip automation")
def clear_clip_automation(ctx: Context, track_index: int, clip_index: int,
                          parameter_name: str) -> str:
    """
    Clear automation for a specific parameter in a clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - parameter_name: Name of the parameter to clear automation for
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("clear_clip_automation", {
        "track_index": track_index,
        "clip_index": clip_index,
        "parameter_name": parameter_name,
    })
    if result.get("cleared"):
        return f"Cleared automation for '{parameter_name}'"
    return f"Could not clear automation for '{parameter_name}': {result.get('reason', 'Unknown')}"
@mcp.tool()
@_tool_handler("listing automated parameters")
def list_clip_automated_parameters(ctx: Context, track_index: int, clip_index: int) -> str:
    """
    List all parameters that have automation in a given clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("list_clip_automated_params", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    params = result.get("automated_parameters", [])
    if not params:
        return "No automated parameters found in this clip"
    output = f"Found {len(params)} automated parameter(s):\n\n"
    for p in params:
        source = p.get("source", "Unknown")
        output += f"• {p.get('name', '?')} (source: {source})"
        if "device_index" in p:
            output += f" [device {p['device_index']}]"
        output += "\n"
    return output

@mcp.tool()
@_tool_handler("searching browser")
def search_browser(ctx: Context, query: str, category: str = "all") -> str:
    """
    Search the Ableton browser for items matching a query.

    Uses a cached browser index for instant results. The cache is built
    automatically on first use and refreshed every 5 minutes.

    Parameters:
    - query: Search string to find items (searches by name)
    - category: Limit search to category ('all', 'instruments', 'sounds', 'drums', 'audio_effects', 'midi_effects', 'max_for_live', 'plugins', 'clips', 'samples', 'packs', 'user_library')
    """
    cache = _get_browser_cache()
    if not cache:
        return "Browser cache is empty. Make sure Ableton is running and try again."

    query_lower = query.lower()

    # Use category index for filtered search (smaller list to scan)
    filter_display = _CATEGORY_DISPLAY.get(category) if category != "all" else None
    search_list = _browser_cache_by_category.get(filter_display, cache) if filter_display else cache

    results = []
    for item in search_list:
        # Substring match using pre-lowercased search_name
        if query_lower in item.get("search_name", item.get("name", "").lower()):
            results.append(item)

    if not results:
        return f"No results found for '{query}' in category '{category}'"

    # Sort: loadable items first, then by name
    results.sort(key=lambda x: (not x.get("is_loadable", False), x.get("name", "").lower()))

    # Limit to 50 results
    results = results[:50]

    formatted_output = f"Found {len(results)} results for '{query}':\n\n"
    for item in results:
        loadable = " [loadable]" if item.get("is_loadable", False) else ""
        folder = " [folder]" if item.get("is_folder", False) else ""
        formatted_output += f"• {item.get('name', 'Unknown')}{loadable}{folder}\n"
        formatted_output += f"  Category: {item.get('category', '?')} | Path: {item.get('path', '?')}\n"
        if item.get("uri"):
            formatted_output += f"  URI: {item.get('uri')}\n"

    return formatted_output

@mcp.tool()
@_tool_handler("refreshing browser cache")
def refresh_browser_cache(ctx: Context) -> str:
    """
    Force a refresh of the browser cache.

    Use this after installing new packs, instruments, or effects so that
    search_browser can find them. The cache is also auto-refreshed every
    5 minutes.
    """
    success = _populate_browser_cache(force=True)
    if success:
        with _browser_cache_lock:
            count = len(_browser_cache_flat)
            cats = len(_browser_cache_by_category)
            devices = len(_device_uri_map)
        return f"Browser cache refreshed: {count} items across {cats} categories, {devices} device names mapped (saved to disk)"
    return "Failed to refresh browser cache. Make sure Ableton is running."


@mcp.tool()
@_tool_handler("loading drum kit")
def load_drum_kit(ctx: Context, track_index: int, rack_uri: str, kit_path: str) -> str:
    """
    Load a drum rack and then load a specific drum kit into it.

    Specialized two-step loader: creates a Drum Rack then loads a kit into it.
    For loading individual instruments, use load_instrument_or_effect instead.

    Parameters:
    - track_index: The index of the track to load on
    - rack_uri: The URI of the drum rack to load (e.g., 'Drums/Drum Rack')
    - kit_path: Path to the drum kit inside the browser (e.g., 'drums/acoustic/kit1')
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()

    # Step 1: Load the drum rack
    result = ableton.send_command("load_browser_item", {
        "track_index": track_index,
        "item_uri": rack_uri
    })
        
    if not result.get("loaded", False):
        return f"Failed to load drum rack with URI '{rack_uri}'"
        
    # Step 2: Get the drum kit items at the specified path
    kit_result = ableton.send_command("get_browser_items_at_path", {
        "path": kit_path
    })
        
    if "error" in kit_result:
        return f"Loaded drum rack but failed to find drum kit: {kit_result.get('error')}"
        
    # Step 3: Find a loadable drum kit
    kit_items = kit_result.get("items", [])
    loadable_kits = [item for item in kit_items if item.get("is_loadable", False)]
        
    if not loadable_kits:
        return f"Loaded drum rack but no loadable drum kits found at '{kit_path}'"
        
    # Step 4: Load the first loadable kit
    kit_uri = loadable_kits[0].get("uri")
    load_result = ableton.send_command("load_browser_item", {
        "track_index": track_index,
        "item_uri": kit_uri
    })
        
    return f"Loaded drum rack and kit '{loadable_kits[0].get('name')}' on track {track_index}"

@mcp.tool()
@_tool_handler("checking M4L bridge status")
def m4l_status(ctx: Context) -> str:
    """Check if the AbletonMCP Max for Live bridge device is loaded and responsive.

    The M4L bridge is an optional device that provides access to hidden/non-automatable
    device parameters via the Live Object Model (LOM). All standard MCP tools work
    without it; only the hidden-parameter tools require it.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("ping")
    data = _m4l_result(result)
    version = data.get("version", "unknown")
    return f"M4L bridge connected (v{version})."


@mcp.tool()
@_tool_handler("discovering device parameters")
def discover_device_params(ctx: Context, track_index: int, device_index: int) -> str:
    """Discover ALL parameters for a device including hidden/non-automatable ones.

    Use to LIST parameter indices and names — needed before calling set_device_hidden_parameter
    or batch_set_hidden_parameters. To READ current parameter values instead, use
    get_device_hidden_parameters.

    Uses the M4L bridge to enumerate every parameter exposed by the Live Object Model,
    which typically includes parameters not visible through the standard Remote Script API.
    Works with any Ableton device (Operator, Wavetable, Simpler, Analog, Drift, etc.).

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.

    Compare the results with get_device_parameters() to see which parameters are hidden.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")

    m4l = get_m4l_connection()
    result = m4l.send_command("discover_params", {
        "track_index": track_index,
        "device_index": device_index
    })

    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("getting hidden device parameters")
def get_device_hidden_parameters(ctx: Context, track_index: int, device_index: int) -> str:
    """Get ALL parameters for a device including hidden/non-automatable ones.

    Use to READ current parameter values (including hidden ones). To get parameter
    indices for setting values, use discover_device_params instead.

    This is similar to get_device_parameters() but uses the M4L bridge to access
    the full Live Object Model parameter tree, which exposes parameters that the
    standard API hides. Works with any Ableton device.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")

    m4l = get_m4l_connection()
    result = m4l.send_command("get_hidden_params", {
        "track_index": track_index,
        "device_index": device_index
    })

    data = _m4l_result(result)
    device_name = data.get("device_name", "Unknown")
    device_class = data.get("device_class", "Unknown")
    params = data.get("parameters", [])

    output = f"Device: {device_name} ({device_class})\n"
    output += f"Total LOM parameters: {len(params)}\n\n"

    for p in params:
        quant = " [quantized]" if p.get("is_quantized") else ""
        output += (
            f"  [{p.get('index', '?')}] {p.get('name', '?')}: "
            f"{p.get('value', '?')} "
            f"(range: {p.get('min', '?')} – {p.get('max', '?')}){quant}\n"
        )
        if p.get("value_items"):
            output += f"       options: {p.get('value_items')}\n"

    return output


@mcp.tool()
@_tool_handler("setting hidden device parameter")
def set_device_hidden_parameter(
    ctx: Context,
    track_index: int,
    device_index: int,
    parameter_index: int,
    value: float
) -> str:
    """Set a device parameter by its LOM index, including hidden/non-automatable ones.

    Only for hidden/non-automatable params not accessible via the standard
    set_device_parameter. Use discover_device_params() first to find parameter indices.
    The value will be clamped to the parameter's valid range.
    Works with any Ableton device.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    _validate_index(parameter_index, "parameter_index")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("value must be a number.")

    m4l = get_m4l_connection()
    result = m4l.send_command("set_hidden_param", {
        "track_index": track_index,
        "device_index": device_index,
        "parameter_index": parameter_index,
        "value": value
    })

    data = _m4l_result(result)
    name = data.get("parameter_name", "Unknown")
    actual = data.get("actual_value", "?")
    clamped = data.get("was_clamped", False)
    msg = f"Set parameter [{parameter_index}] '{name}' to {actual}"
    if clamped:
        msg += f" (clamped from requested {value})"
    return msg
# ---------------------------------------------------------------------------
# Device Property Knowledge Base
#
# Comprehensive registry of device-level LOM properties keyed by class_name.
# Used by get_device_property / set_device_property / list_device_properties
# to provide human-readable labels, validation, and documentation.
#
# Each property entry has:
#   "description" : str   — what the property controls
#   "type"        : str   — "enum" | "int" | "float" | "list"
#   "values"      : dict  — (enum only) int→label mapping
#   "min" / "max" : num   — (int/float only) valid range bounds
#   "readonly"    : bool  — True if property cannot be set
#   "note"        : str   — (optional) special behavioral notes
# ---------------------------------------------------------------------------
DEVICE_PROPERTIES: Dict[str, Dict[str, Dict[str, Any]]] = {

    # ===== Wavetable (InstrumentVector) =====================================
    "InstrumentVector": {
        # --- Voice / Unison ---
        "unison_mode": {
            "description": "Unison stacking mode",
            "type": "enum",
            "values": {
                0: "None", 1: "Classic", 2: "Shimmer",
                3: "Noise", 4: "Phase Sync", 5: "Position Spread",
            },
        },
        "unison_voice_count": {
            "description": "Number of unison voices",
            "type": "int", "min": 2, "max": 8,
        },
        "poly_voices": {
            "description": "Polyphony voice count (value + 2 = actual voices)",
            "type": "enum",
            "values": {
                0: "2 voices", 1: "3 voices", 2: "4 voices", 3: "5 voices",
                4: "6 voices", 5: "7 voices", 6: "8 voices",
            },
        },
        "mono_poly": {
            "description": "Mono/Poly voice mode",
            "type": "enum",
            "values": {0: "Mono", 1: "Poly"},
        },

        # --- Filter ---
        "filter_routing": {
            "description": "Routing between Filter 1 and Filter 2",
            "type": "enum",
            "values": {0: "Serial", 1: "Parallel", 2: "Split"},
        },

        # --- Oscillator Effect Mode ---
        "oscillator_1_effect_mode": {
            "description": "Oscillator 1 warp effect type",
            "type": "enum",
            "values": {0: "None", 1: "FM", 2: "Classic", 3: "Modern", 4: "Ping Pong"},
        },
        "oscillator_2_effect_mode": {
            "description": "Oscillator 2 warp effect type",
            "type": "enum",
            "values": {0: "None", 1: "FM", 2: "Classic", 3: "Modern", 4: "Ping Pong"},
        },

        # --- Wavetable Selection ---
        "oscillator_1_wavetable_category": {
            "description": "Osc 1 wavetable category index",
            "type": "int", "min": 0,
            "note": "Changing this updates the list from oscillator_1_wavetables",
        },
        "oscillator_1_wavetable_index": {
            "description": "Osc 1 wavetable index within current category",
            "type": "int", "min": 0,
        },
        "oscillator_2_wavetable_category": {
            "description": "Osc 2 wavetable category index",
            "type": "int", "min": 0,
            "note": "Changing this updates the list from oscillator_2_wavetables",
        },
        "oscillator_2_wavetable_index": {
            "description": "Osc 2 wavetable index within current category",
            "type": "int", "min": 0,
        },

        # --- Read-only Lists ---
        "oscillator_wavetable_categories": {
            "description": "Available wavetable category names (comma-separated)",
            "type": "list", "readonly": True,
        },
        "oscillator_1_wavetables": {
            "description": "Available wavetable names for Osc 1 in current category",
            "type": "list", "readonly": True,
        },
        "oscillator_2_wavetables": {
            "description": "Available wavetable names for Osc 2 in current category",
            "type": "list", "readonly": True,
        },
        "visible_modulation_target_names": {
            "description": "Modulation target parameter names (comma-separated)",
            "type": "list", "readonly": True,
        },
    },

    # Future devices will be added here:
    # "Drift": { ... },
    # "Operator": { ... },
    # "OriginalSimpler": { ... },
    # "Analog": { ... },
    # "InstrumentImpulse": { ... },
}


def _get_property_info(device_class: str, property_name: str) -> Optional[Dict[str, Any]]:
    """Look up property metadata from the DEVICE_PROPERTIES knowledge base."""
    device_props = DEVICE_PROPERTIES.get(device_class, {})
    return device_props.get(property_name)


def _format_property_value(prop_info: Optional[Dict[str, Any]], value) -> str:
    """Format a property value with its human-readable label."""
    if prop_info and prop_info.get("type") == "enum" and "values" in prop_info:
        if isinstance(value, (int, float)):
            label = prop_info["values"].get(int(value))
            if label:
                return f"{value} ({label})"
    return str(value)


def _format_property_options(prop_info: Optional[Dict[str, Any]]) -> str:
    """Build a human-readable options string for enum properties."""
    if not prop_info or prop_info.get("type") != "enum":
        return ""
    values = prop_info.get("values", {})
    if not values:
        return ""
    return "Options: " + ", ".join(f"{k}={v}" for k, v in sorted(values.items()))


def _validate_property_value(
    prop_info: Optional[Dict[str, Any]], property_name: str, value: float
) -> None:
    """Validate a value against known property constraints.

    Raises ValueError if validation fails.  Does nothing for unknown properties.
    """
    if prop_info is None:
        return  # Unknown property — let the bridge handle it

    if prop_info.get("readonly"):
        raise ValueError(
            f"Property '{property_name}' is read-only and cannot be set."
        )

    if prop_info["type"] == "enum":
        valid_keys = list(prop_info.get("values", {}).keys())
        if int(value) not in valid_keys:
            options = ", ".join(f"{k}={v}" for k, v in sorted(prop_info["values"].items()))
            raise ValueError(
                f"Invalid value {int(value)} for '{property_name}'. Valid options: {options}"
            )
    elif prop_info["type"] in ("int", "float"):
        min_val = prop_info.get("min")
        max_val = prop_info.get("max")
        if min_val is not None and value < min_val:
            raise ValueError(f"Value {value} below minimum {min_val} for '{property_name}'.")
        if max_val is not None and value > max_val:
            raise ValueError(f"Value {value} above maximum {max_val} for '{property_name}'.")


@mcp.tool()
@_tool_handler("getting device property")
def get_device_property(
    ctx: Context,
    track_index: int,
    device_index: int,
    property_name: str
) -> str:
    """Read a device-level LOM property (not an indexed parameter).

    Reads properties directly on the device object in the Live Object Model.
    For supported devices (currently: Wavetable/InstrumentVector), the response
    includes human-readable labels, descriptions, and available options.

    Use list_device_properties() to see all known properties for a device.
    Use discover_device_params() for indexed parameters instead.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if not isinstance(property_name, str) or not property_name.strip():
        raise ValueError("property_name must be a non-empty string.")

    m4l = get_m4l_connection()
    result = m4l.send_command("get_device_property", {
        "track_index": track_index,
        "device_index": device_index,
        "property_name": property_name.strip()
    })

    data = _m4l_result(result)
    device_name = data.get("device_name", "Unknown")
    device_class = data.get("device_class", "Unknown")
    prop = data.get("property_name", property_name)
    val = data.get("value", "?")

    # Look up property in knowledge base
    prop_info = _get_property_info(device_class, prop)
    val_str = _format_property_value(prop_info, val)

    msg = f"Device: {device_name} ({device_class})\n"
    msg += f"Property '{prop}' = {val_str}"

    if prop_info:
        if prop_info.get("description"):
            msg += f"\n  {prop_info['description']}"
        if prop_info.get("readonly"):
            msg += "\n  (read-only)"
        options = _format_property_options(prop_info)
        if options:
            msg += f"\n  {options}"
        if prop_info.get("note"):
            msg += f"\n  Note: {prop_info['note']}"

    return msg

@mcp.tool()
@_tool_handler("setting device property")
def set_device_property(
    ctx: Context,
    track_index: int,
    device_index: int,
    property_name: str,
    value: float
) -> str:
    """Set a device-level LOM property (not an indexed parameter).

    Sets properties directly on the device object in the Live Object Model.
    For supported devices (currently: Wavetable/InstrumentVector), the value
    is validated against the knowledge base before sending.

    Use list_device_properties() to see all known properties and valid values.
    Use get_device_property() to read the current value first.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if not isinstance(property_name, str) or not property_name.strip():
        raise ValueError("property_name must be a non-empty string.")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("value must be a number.")

    prop_name = property_name.strip()
    m4l = get_m4l_connection()

    # Pre-validate: get device class, then check knowledge base
    class_result = m4l.send_command("get_device_property", {
        "track_index": track_index,
        "device_index": device_index,
        "property_name": "class_name"
    })
    device_class = None
    class_data = _m4l_result(class_result)
    device_class = class_data.get("value")
    if isinstance(device_class, str):
        prop_info = _get_property_info(device_class, prop_name)
        _validate_property_value(prop_info, prop_name, value)

    result = m4l.send_command("set_device_property", {
        "track_index": track_index,
        "device_index": device_index,
        "property_name": prop_name,
        "value": float(value)
    })

    data = _m4l_result(result)
    device_name = data.get("device_name", "Unknown")
    resp_class = data.get("device_class", device_class or "Unknown")
    prop = data.get("property_name", prop_name)
    old_val = data.get("old_value", "?")
    new_val = data.get("new_value", "?")
    success = data.get("success", False)

    prop_info = _get_property_info(resp_class, prop)
    old_str = _format_property_value(prop_info, old_val)
    new_str = _format_property_value(prop_info, new_val)

    msg = (
        f"Device: {device_name} ({resp_class})\n"
        f"Property '{prop}': {old_str} -> {new_str}"
    )
    if not success:
        msg += " (WARNING: value may not have changed — property might be read-only or value out of range)"
    return msg
@mcp.tool()
@_tool_handler("listing device properties")
def list_device_properties(
    ctx: Context,
    track_index: int,
    device_index: int
) -> str:
    """List all known LOM properties for a device from the knowledge base.

    Shows available device-level properties including their types, valid
    values, descriptions, and whether they are settable or read-only.

    Currently supported: Wavetable (InstrumentVector).
    More devices will be added over time.

    Use get_device_property() / set_device_property() to read/write these.
    Use discover_device_params() for indexed parameters instead.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")

    m4l = get_m4l_connection()
    result = m4l.send_command("get_device_property", {
        "track_index": track_index,
        "device_index": device_index,
        "property_name": "class_name"
    })

    data = _m4l_result(result)
    device_name = data.get("device_name", "Unknown")
    device_class = data.get("value", "Unknown")

    if device_class not in DEVICE_PROPERTIES:
        supported = ", ".join(sorted(DEVICE_PROPERTIES.keys()))
        return (
            f"Device: {device_name} ({device_class})\n"
            f"No property knowledge base for class '{device_class}'.\n"
            f"You can still use get_device_property() / set_device_property() "
            f"with any valid LOM property name.\n"
            f"Supported classes: {supported}"
        )

    props = DEVICE_PROPERTIES[device_class]
    settable = {k: v for k, v in props.items() if not v.get("readonly")}
    readonly = {k: v for k, v in props.items() if v.get("readonly")}

    msg = f"Device: {device_name} ({device_class})\n"
    msg += f"Known properties: {len(props)} ({len(settable)} settable, {len(readonly)} read-only)\n"

    if settable:
        msg += "\n--- Settable Properties ---\n"
        for name, info in settable.items():
            msg += f"\n  {name}"
            if info.get("description"):
                msg += f" — {info['description']}"
            if info["type"] == "enum" and "values" in info:
                opts = ", ".join(f"{k}={v}" for k, v in sorted(info["values"].items()))
                msg += f"\n    Values: {opts}"
            elif info["type"] in ("int", "float"):
                parts = []
                if "min" in info:
                    parts.append(f"min={info['min']}")
                if "max" in info:
                    parts.append(f"max={info['max']}")
                if parts:
                    msg += f"\n    Range: {', '.join(parts)}"
            if info.get("note"):
                msg += f"\n    Note: {info['note']}"

    if readonly:
        msg += "\n\n--- Read-Only Properties ---\n"
        for name, info in readonly.items():
            msg += f"\n  {name}"
            if info.get("description"):
                msg += f" — {info['description']}"

    return msg
# --- VST/AU Workaround Tool ---

@mcp.tool()
@_tool_handler("listing presets")
def list_instrument_rack_presets(ctx: Context) -> str:
    """List Instrument Rack presets saved in the user library.

    This is the recommended workaround for loading VST/AU plugins, since
    Ableton's API does not support loading third-party plugins directly.

    Workflow:
      1. Load your VST/AU plugin manually in Ableton
      2. Group it into an Instrument Rack (Cmd+G / Ctrl+G)
      3. Save the rack to your User Library
      4. Use this tool to find it, then load_instrument_or_effect() to load it

    This tool searches the user library for saved device presets (.adg files)
    that can be loaded onto tracks.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("get_user_library")

    if not result:
        return "Could not retrieve user library."

    # Recursively collect loadable items from the user library
    presets = []

    def collect_loadable(items, path=""):
        if isinstance(items, list):
            for item in items:
                collect_loadable(item, path)
        elif isinstance(items, dict):
            name = items.get("name", "")
            is_loadable = items.get("is_loadable", False)
            uri = items.get("uri", "")
            current_path = f"{path}/{name}" if path else name

            if is_loadable and uri:
                presets.append({
                    "name": name,
                    "path": current_path,
                    "uri": uri
                })

            # Recurse into children
            children = items.get("children", [])
            if children:
                collect_loadable(children, current_path)

    collect_loadable(result)

    if not presets:
        return (
            "No loadable presets found in the user library.\n\n"
            "To create a VST/AU wrapper preset:\n"
            "  1. Load your VST/AU plugin manually in Ableton\n"
            "  2. Group it into an Instrument Rack (Cmd+G / Ctrl+G)\n"
            "  3. Save the rack to your User Library (Ctrl+S / Cmd+S on the rack)\n"
            "  4. Run this tool again to find it"
        )

    output = f"Found {len(presets)} loadable preset(s) in user library:\n\n"
    for p in presets:
        output += f"  - {p['name']}\n"
        output += f"    Path: {p['path']}\n"
        output += f"    URI: {p['uri']}\n"
        output += f"    Load with: load_instrument_or_effect(track_index, \"{p['uri']}\")\n\n"

    return output


# ==========================================================================
# v1.6.0 Feature Tools — Layer 0: Core Primitives
# ==========================================================================

@mcp.tool()
@_tool_handler("batch setting parameters")
def batch_set_hidden_parameters(
    ctx: Context,
    track_index: int,
    device_index: int,
    parameters: List[Dict[str, float]]
) -> str:
    """Set multiple device parameters at once by their LOM indices (including hidden ones).

    Only for hidden/non-automatable params. For standard visible params, use
    set_device_parameters instead. Much faster than calling
    set_device_hidden_parameter() in a loop — single round-trip to the M4L bridge.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - parameters: List of {"index": parameter_index, "value": target_value} dicts

    Use discover_device_params() first to find parameter indices.
    Values will be clamped to each parameter's valid range.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if not isinstance(parameters, list) or len(parameters) == 0:
        raise ValueError("parameters must be a non-empty list.")

    # Filter out parameter index 0 ("Device On") to prevent accidentally
    # disabling the device — a common source of issues.
    safe_params = [p for p in parameters if "index" in p and int(p["index"]) != 0]
    skipped = len(parameters) - len(safe_params)

    for i, p in enumerate(safe_params):
        if not isinstance(p, dict):
            raise ValueError(f"Parameter at index {i} must be a dictionary.")
        if "index" not in p or "value" not in p:
            raise ValueError(f"Parameter at index {i} must have 'index' and 'value' keys.")

    if len(safe_params) == 0:
        return "No settable parameters after filtering (parameter 0 'Device On' is excluded)."

    # Send individual set_hidden_param commands with a small delay between
    # each to avoid overwhelming Ableton.  This is more reliable than the
    # base64-encoded batch OSC approach which can fail with long payloads.
    m4l = get_m4l_connection()
    ok_count = 0
    fail_count = 0
    errors = []

    for p in safe_params:
        try:
            result = m4l.send_command("set_hidden_param", {
                "track_index": track_index,
                "device_index": device_index,
                "parameter_index": int(p["index"]),
                "value": float(p["value"])
            })
            if result.get("status") == "success":
                ok_count += 1
            else:
                fail_count += 1
                errors.append(f"[{p['index']}]: {result.get('message', '?')}")
        except Exception as e:
            fail_count += 1
            errors.append(f"[{p['index']}]: {str(e)}")

        # Small delay between params to let Ableton breathe
        if len(safe_params) > 6:
            time.sleep(0.05)

    total = ok_count + fail_count
    msg = f"Batch set complete: {ok_count}/{total} parameters set successfully ({fail_count} failed)."
    if skipped:
        msg += f" ({skipped} skipped: 'Device On' excluded for safety.)"
    if errors:
        msg += f" Errors: {'; '.join(errors[:5])}"
    return msg
@mcp.tool()
@_tool_handler("capturing device snapshot")
def snapshot_device_state(
    ctx: Context,
    track_index: int,
    device_index: int,
    snapshot_name: str = ""
) -> str:
    """Capture the complete state of a device (all parameters including hidden ones).

    Stores the snapshot in memory with a unique ID for later recall.
    Use restore_device_snapshot() to restore a saved state.
    Use list_snapshots() to see all stored snapshots.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - snapshot_name: Optional human-readable name for the snapshot

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")

    m4l = get_m4l_connection()
    result = m4l.send_command("discover_params", {
        "track_index": track_index,
        "device_index": device_index
    })

    if result.get("status") != "success":
        return f"M4L bridge error: {result.get('message', 'Unknown error')}"

    data = result.get("result", {})
    snapshot_id = str(uuid.uuid4())[:8]
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    snapshot = {
        "id": snapshot_id,
        "name": snapshot_name or f"{data.get('device_name', 'Unknown')}_{snapshot_id}",
        "timestamp": timestamp,
        "track_index": track_index,
        "device_index": device_index,
        "device_name": data.get("device_name", "Unknown"),
        "device_class": data.get("device_class", "Unknown"),
        "parameter_count": data.get("parameter_count", 0),
        "parameters": data.get("parameters", [])
    }

    _snapshot_store[snapshot_id] = snapshot

    return (
        f"Snapshot saved: '{snapshot['name']}' (ID: {snapshot_id})\n"
        f"Device: {snapshot['device_name']} ({snapshot['device_class']})\n"
        f"Parameters captured: {snapshot['parameter_count']}\n"
        f"Timestamp: {timestamp}"
    )
@mcp.tool()
@_tool_handler("restoring device snapshot")
def restore_device_snapshot(
    ctx: Context,
    snapshot_id: str,
    track_index: int = -1,
    device_index: int = -1
) -> str:
    """Restore a previously captured device state from a snapshot.

    Applies all parameter values from the snapshot to the device using batch set.
    By default restores to the same track/device the snapshot was taken from.
    Optionally specify different track_index/device_index to apply to a different device.

    Parameters:
    - snapshot_id: The ID of the snapshot to restore (from snapshot_device_state or list_snapshots)
    - track_index: Override target track (-1 = use original track from snapshot)
    - device_index: Override target device (-1 = use original device from snapshot)

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    try:
        if snapshot_id not in _snapshot_store:
            return f"Snapshot '{snapshot_id}' not found. Use list_snapshots() to see available snapshots."

        snapshot = _snapshot_store[snapshot_id]
        target_track = track_index if track_index >= 0 else snapshot["track_index"]
        target_device = device_index if device_index >= 0 else snapshot["device_index"]

        params_to_set = [{"index": p["index"], "value": p["value"]} for p in snapshot["parameters"]]

        if not params_to_set:
            return "Snapshot contains no parameters to restore."

        m4l = get_m4l_connection()
        data = _m4l_batch_set_params(m4l, target_track, target_device, params_to_set)
        ok = data["params_set"]
        failed = data["params_failed"]
        return (
            f"Restored snapshot '{snapshot['name']}' (ID: {snapshot_id})\n"
            f"Target: track {target_track}, device {target_device}\n"
            f"Parameters restored: {ok}/{len(params_to_set)} ({failed} failed)"
        )
    except ConnectionError as e:
        return f"M4L bridge not available: {e}"
    except Exception as e:
        logger.error(f"Error restoring device snapshot: {str(e)}")
        return f"Error restoring device snapshot: {str(e)}"


@mcp.tool()
@_tool_handler("listing snapshots")
def list_snapshots(ctx: Context) -> str:
    """List all stored device state snapshots.

    Shows snapshot IDs, names, device info, and timestamps.
    Use snapshot IDs with restore_device_snapshot() to recall states.
    """
    non_group = {k: v for k, v in _snapshot_store.items() if v.get("type") != "group"}
    if not non_group:
        return "No snapshots stored. Use snapshot_device_state() to capture a device state."

    output = f"Stored snapshots ({len(non_group)}):\n\n"
    for sid, snap in non_group.items():
        output += (
            f"  ID: {sid}\n"
            f"  Name: {snap['name']}\n"
            f"  Device: {snap.get('device_name', '?')} ({snap.get('device_class', '?')})\n"
            f"  Location: track {snap.get('track_index', '?')}, device {snap.get('device_index', '?')}\n"
            f"  Parameters: {snap.get('parameter_count', '?')}\n"
            f"  Captured: {snap.get('timestamp', '?')}\n\n"
        )
    return output


@mcp.tool()
@_tool_handler("deleting snapshot")
def delete_snapshot(ctx: Context, snapshot_id: str) -> str:
    """Delete a stored device state snapshot.

    Parameters:
    - snapshot_id: The ID of the snapshot to delete
    """
    if snapshot_id not in _snapshot_store:
        return f"Snapshot '{snapshot_id}' not found."
    name = _snapshot_store[snapshot_id].get("name", snapshot_id)
    del _snapshot_store[snapshot_id]
    return f"Deleted snapshot '{name}' (ID: {snapshot_id})."


@mcp.tool()
@_tool_handler("getting snapshot details")
def get_snapshot_details(ctx: Context, snapshot_id: str) -> str:
    """Get the full parameter details of a stored snapshot.

    Parameters:
    - snapshot_id: The ID of the snapshot to inspect
    """
    if snapshot_id not in _snapshot_store:
        return f"Snapshot '{snapshot_id}' not found."

    snap = _snapshot_store[snapshot_id]
    output = (
        f"Snapshot: {snap.get('name', snapshot_id)} (ID: {snapshot_id})\n"
        f"Device: {snap.get('device_name', '?')} ({snap.get('device_class', '?')})\n"
        f"Location: track {snap.get('track_index', '?')}, device {snap.get('device_index', '?')}\n"
        f"Captured: {snap.get('timestamp', '?')}\n"
        f"Parameters ({snap.get('parameter_count', 0)}):\n\n"
    )
    for p in snap.get("parameters", []):
        quant = " [quantized]" if p.get("is_quantized") else ""
        output += (
            f"  [{p.get('index', '?')}] {p.get('name', '?')}: "
            f"{p.get('value', '?')} "
            f"(range: {p.get('min', '?')} - {p.get('max', '?')}){quant}\n"
        )
    return output


@mcp.tool()
@_tool_handler("deleting all snapshots")
def delete_all_snapshots(ctx: Context) -> str:
    """Delete all stored snapshots, macros, and parameter maps.

    Clears all in-memory feature data. This cannot be undone.
    """
    global _snapshot_store, _macro_store, _param_map_store
    count = len(_snapshot_store) + len(_macro_store) + len(_param_map_store)
    _snapshot_store = {}
    _macro_store = {}
    _param_map_store = {}
    return f"Cleared all feature data: {count} items deleted."


# ==========================================================================
# v1.6.0 Feature Tools — Feature 5: Device State Versioning & Undo
# ==========================================================================

@mcp.tool()
@_tool_handler("capturing group snapshot")
def snapshot_all_devices(
    ctx: Context,
    track_indices: List[int],
    snapshot_name: str = ""
) -> str:
    """Snapshot the state of all devices across one or more tracks.

    Captures every device on the specified tracks into a group of snapshots
    that can be restored together with restore_group_snapshot().

    Parameters:
    - track_indices: List of track indices to snapshot
    - snapshot_name: Optional name for the group snapshot

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    if not isinstance(track_indices, list) or len(track_indices) == 0:
        raise ValueError("track_indices must be a non-empty list of integers.")
    for ti in track_indices:
        _validate_index(ti, "track_index")

    m4l = get_m4l_connection()
    ableton = get_ableton_connection()
    group_id = str(uuid.uuid4())[:8]
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    snapshot_ids = []
    device_count = 0

    for ti in track_indices:
        track_info = ableton.send_command("get_track_info", {"track_index": ti})
        devices = track_info.get("devices", [])

        for di, dev in enumerate(devices):
            result = m4l.send_command("discover_params", {
                "track_index": ti,
                "device_index": di
            })

            if result.get("status") != "success":
                continue

            data = result.get("result", {})
            snap_id = str(uuid.uuid4())[:8]

            _snapshot_store[snap_id] = {
                "id": snap_id,
                "group_id": group_id,
                "name": f"{data.get('device_name', 'Unknown')}_t{ti}_d{di}",
                "timestamp": timestamp,
                "track_index": ti,
                "device_index": di,
                "device_name": data.get("device_name", "Unknown"),
                "device_class": data.get("device_class", "Unknown"),
                "parameter_count": data.get("parameter_count", 0),
                "parameters": data.get("parameters", [])
            }
            snapshot_ids.append(snap_id)
            device_count += 1

    group_name = snapshot_name or f"group_{group_id}"

    _snapshot_store[f"group_{group_id}"] = {
        "id": f"group_{group_id}",
        "type": "group",
        "name": group_name,
        "timestamp": timestamp,
        "track_indices": track_indices,
        "snapshot_ids": snapshot_ids,
        "device_count": device_count
    }

    return (
        f"Group snapshot '{group_name}' saved (ID: group_{group_id})\n"
        f"Tracks: {track_indices}\n"
        f"Devices captured: {device_count}\n"
        f"Individual snapshot IDs: {', '.join(snapshot_ids)}"
    )
@mcp.tool()
@_tool_handler("restoring group snapshot")
def restore_group_snapshot(ctx: Context, group_id: str) -> str:
    """Restore all device states from a group snapshot.

    Restores every device captured in a snapshot_all_devices() call.

    Parameters:
    - group_id: The group snapshot ID (starts with 'group_')

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    if group_id not in _snapshot_store:
        return f"Group snapshot '{group_id}' not found."

    group = _snapshot_store[group_id]
    if group.get("type") != "group":
        return f"'{group_id}' is not a group snapshot. Use restore_device_snapshot() instead."

    m4l = get_m4l_connection()
    total_devices = 0
    total_params = 0
    total_failed = 0

    for snap_id in group.get("snapshot_ids", []):
        if snap_id not in _snapshot_store:
            continue

        snap = _snapshot_store[snap_id]
        params_to_set = [{"index": p["index"], "value": p["value"]} for p in snap.get("parameters", [])]

        if not params_to_set:
            continue

        data = _m4l_batch_set_params(m4l, snap["track_index"], snap["device_index"], params_to_set)
        total_params += data["params_set"]
        total_failed += data["params_failed"]
        total_devices += 1

    return (
        f"Restored group snapshot '{group['name']}'\n"
        f"Devices restored: {total_devices}\n"
        f"Parameters restored: {total_params} ({total_failed} failed)"
    )


@mcp.tool()
@_tool_handler("comparing snapshots")
def compare_snapshots(ctx: Context, snapshot_a_id: str, snapshot_b_id: str) -> str:
    """Compare two device snapshots and show parameter differences.

    Useful for understanding what changed between two states.

    Parameters:
    - snapshot_a_id: First snapshot ID
    - snapshot_b_id: Second snapshot ID
    """
    if snapshot_a_id not in _snapshot_store:
        return f"Snapshot '{snapshot_a_id}' not found."
    if snapshot_b_id not in _snapshot_store:
        return f"Snapshot '{snapshot_b_id}' not found."

    snap_a = _snapshot_store[snapshot_a_id]
    snap_b = _snapshot_store[snapshot_b_id]

    a_by_index = {p["index"]: p for p in snap_a.get("parameters", [])}
    b_by_index = {p["index"]: p for p in snap_b.get("parameters", [])}

    all_indices = sorted(set(a_by_index.keys()) | set(b_by_index.keys()))

    changed = []
    unchanged = 0

    for idx in all_indices:
        in_a = idx in a_by_index
        in_b = idx in b_by_index

        if in_a and in_b:
            val_a = a_by_index[idx]["value"]
            val_b = b_by_index[idx]["value"]
            if abs(val_a - val_b) > 0.001:
                changed.append({
                    "index": idx,
                    "name": a_by_index[idx].get("name", "?"),
                    "value_a": val_a,
                    "value_b": val_b,
                    "delta": val_b - val_a
                })
            else:
                unchanged += 1
        else:
            unchanged += 1

    output = (
        f"Comparison: '{snap_a.get('name', snapshot_a_id)}' vs '{snap_b.get('name', snapshot_b_id)}'\n"
        f"Changed: {len(changed)} | Unchanged: {unchanged}\n\n"
    )

    if changed:
        output += "Changed parameters:\n"
        for c in changed:
            direction = "+" if c["delta"] > 0 else ""
            output += (
                f"  [{c['index']}] {c['name']}: "
                f"{c['value_a']:.4f} -> {c['value_b']:.4f} "
                f"({direction}{c['delta']:.4f})\n"
            )
    else:
        output += "No parameter differences found.\n"

    return output


# ==========================================================================
# v1.6.0 Feature Tools — Feature 4: Preset Morph Engine
# ==========================================================================

@mcp.tool()
@_tool_handler("during morph")
def morph_between_snapshots(
    ctx: Context,
    snapshot_a_id: str,
    snapshot_b_id: str,
    position: float,
    track_index: int = -1,
    device_index: int = -1
) -> str:
    """Morph between two device snapshots by interpolating all parameters.

    Takes two previously captured snapshots and smoothly blends between them.
    Position 0.0 = fully snapshot A, position 1.0 = fully snapshot B.
    Quantized parameters (e.g. waveform selectors) snap at the midpoint.

    Parameters:
    - snapshot_a_id: ID of the first snapshot (position 0.0)
    - snapshot_b_id: ID of the second snapshot (position 1.0)
    - position: Morph position (0.0 to 1.0)
    - track_index: Override target track (-1 = use snapshot A's track)
    - device_index: Override target device (-1 = use snapshot A's device)

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_range(position, "position", 0.0, 1.0)

    if snapshot_a_id not in _snapshot_store:
        return f"Snapshot A '{snapshot_a_id}' not found."
    if snapshot_b_id not in _snapshot_store:
        return f"Snapshot B '{snapshot_b_id}' not found."

    snap_a = _snapshot_store[snapshot_a_id]
    snap_b = _snapshot_store[snapshot_b_id]

    target_track = track_index if track_index >= 0 else snap_a["track_index"]
    target_device = device_index if device_index >= 0 else snap_a["device_index"]

    b_by_index = {p["index"]: p for p in snap_b.get("parameters", [])}

    params_to_set = []
    skipped = 0
    for p_a in snap_a.get("parameters", []):
        idx = p_a["index"]
        if idx not in b_by_index:
            skipped += 1
            continue

        p_b = b_by_index[idx]
        val_a = p_a["value"]
        val_b = p_b["value"]

        if p_a.get("is_quantized", False):
            interpolated = val_a if position < 0.5 else val_b
        else:
            interpolated = val_a + (val_b - val_a) * position

        params_to_set.append({"index": idx, "value": interpolated})

    if not params_to_set:
        return "No matching parameters found between the two snapshots."

    m4l = get_m4l_connection()
    data = _m4l_batch_set_params(m4l, target_track, target_device, params_to_set)
    ok = data["params_set"]
    return (
            f"Morph at position {position:.2f} "
            f"('{snap_a.get('name', snapshot_a_id)}' -> '{snap_b.get('name', snapshot_b_id)}')\n"
            f"Interpolated {ok} parameters, skipped {skipped} (unmatched)\n"
            f"Target: track {target_track}, device {target_device}"
        )
# ==========================================================================
# v1.6.0 Feature Tools — Feature 2: Smart Macro Controller
# ==========================================================================

@mcp.tool()
@_tool_handler("creating macro controller")
def create_macro_controller(
    ctx: Context,
    name: str,
    mappings: List[Dict[str, Any]]
) -> str:
    """Create a macro controller that links multiple device parameters together.

    A macro controller maps a single 0.0-1.0 value to multiple device parameters,
    each with their own range mapping.

    Parameters:
    - name: Human-readable name for the macro (e.g., "Brightness", "Intensity")
    - mappings: List of parameter mappings, each with:
        - track_index: int
        - device_index: int
        - parameter_index: int (LOM index from discover_device_params)
        - min_value: float (parameter value when macro = 0.0)
        - max_value: float (parameter value when macro = 1.0)

    After creation, use set_macro_value() to control all linked parameters at once.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    if not isinstance(mappings, list) or len(mappings) == 0:
        raise ValueError("mappings must be a non-empty list.")
    required = {"track_index", "device_index", "parameter_index", "min_value", "max_value"}
    for i, m in enumerate(mappings):
        if not isinstance(m, dict):
            raise ValueError(f"Mapping at index {i} must be a dictionary.")
        missing = required - m.keys()
        if missing:
            raise ValueError(f"Mapping at index {i} missing keys: {', '.join(sorted(missing))}")

    macro_id = str(uuid.uuid4())[:8]
    _macro_store[macro_id] = {
        "id": macro_id,
        "name": name,
        "mappings": mappings,
        "current_value": 0.0,
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    output = (
        f"Macro controller '{name}' created (ID: {macro_id})\n"
        f"Linked parameters: {len(mappings)}\n"
        f"Use set_macro_value('{macro_id}', value) to control (0.0-1.0)\n\n"
        f"Mappings:\n"
    )
    for m in mappings:
        output += (
            f"  - Track {m['track_index']}, Device {m['device_index']}, "
            f"Param [{m['parameter_index']}]: "
            f"{m['min_value']} -> {m['max_value']}\n"
        )

    return output
@mcp.tool()
@_tool_handler("setting macro value")
def set_macro_value(ctx: Context, macro_id: str, value: float) -> str:
    """Set the value of a macro controller, updating all linked parameters.

    Interpolates the macro value (0.0-1.0) across all mapped parameters
    and applies them via batch set.

    Parameters:
    - macro_id: The ID of the macro controller
    - value: The macro value (0.0 to 1.0)

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    if macro_id not in _macro_store:
        return f"Macro '{macro_id}' not found. Use list_macros() to see available macros."
    _validate_range(value, "value", 0.0, 1.0)

    macro = _macro_store[macro_id]
    macro["current_value"] = value

    grouped: Dict[tuple, list] = {}
    for m in macro["mappings"]:
        key = (m["track_index"], m["device_index"])
        interpolated = m["min_value"] + (m["max_value"] - m["min_value"]) * value
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({"index": m["parameter_index"], "value": interpolated})

    m4l = get_m4l_connection()
    total_set = 0
    total_failed = 0

    for (ti, di), params in grouped.items():
        data = _m4l_batch_set_params(m4l, ti, di, params)
        total_set += data["params_set"]
        total_failed += data["params_failed"]

    return (
        f"Macro '{macro['name']}' set to {value:.2f}\n"
        f"Updated {total_set} parameters across {len(grouped)} device(s) "
        f"({total_failed} failed)"
    )


@mcp.tool()
@_tool_handler("listing macros")
def list_macros(ctx: Context) -> str:
    """List all created macro controllers.

    Shows macro IDs, names, number of linked parameters, and current values.
    """
    if not _macro_store:
        return "No macro controllers created. Use create_macro_controller() to create one."

    output = f"Macro controllers ({len(_macro_store)}):\n\n"
    for mid, macro in _macro_store.items():
        output += (
            f"  ID: {mid}\n"
            f"  Name: {macro['name']}\n"
            f"  Linked params: {len(macro['mappings'])}\n"
            f"  Current value: {macro['current_value']:.2f}\n"
            f"  Created: {macro['created']}\n\n"
        )
    return output


@mcp.tool()
@_tool_handler("deleting macro")
def delete_macro(ctx: Context, macro_id: str) -> str:
    """Delete a macro controller.

    Parameters:
    - macro_id: The ID of the macro to delete
    """
    if macro_id not in _macro_store:
        return f"Macro '{macro_id}' not found."
    name = _macro_store[macro_id]["name"]
    del _macro_store[macro_id]
    return f"Deleted macro controller '{name}' (ID: {macro_id})."


# ==========================================================================
# v1.6.0 Feature Tools — Feature 1: Intelligent Preset Generator
# ==========================================================================

@mcp.tool()
@_tool_handler("during preset generation")
def generate_preset(
    ctx: Context,
    track_index: int,
    device_index: int,
    description: str,
    variation_count: int = 1
) -> str:
    """Generate an intelligent preset for a device based on a text description.

    Discovers all parameters on the target device and returns them so Claude can
    intelligently set values based on the description (e.g., "bright bass",
    "warm pad", "aggressive lead"). The current state is auto-saved as a snapshot
    for easy revert.

    After calling this tool, use batch_set_hidden_parameters() to apply the preset.
    Use restore_device_snapshot() with the revert snapshot ID to undo.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - description: Text description of the desired sound (e.g., "bright plucky bass")
    - variation_count: How many variations to suggest (default: 1)

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if variation_count < 1 or variation_count > 5:
        raise ValueError("variation_count must be between 1 and 5.")

    m4l = get_m4l_connection()
    result = m4l.send_command("discover_params", {
        "track_index": track_index,
        "device_index": device_index
    })

    if result.get("status") != "success":
        return f"M4L bridge error: {result.get('message', 'Unknown error')}"

    data = result.get("result", {})
    device_name = data.get("device_name", "Unknown")
    device_class = data.get("device_class", "Unknown")
    params = data.get("parameters", [])

    # Auto-snapshot current state for revert
    snapshot_id = str(uuid.uuid4())[:8]
    _snapshot_store[snapshot_id] = {
        "id": snapshot_id,
        "name": f"pre_preset_{device_name}_{snapshot_id}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "track_index": track_index,
        "device_index": device_index,
        "device_name": device_name,
        "device_class": device_class,
        "parameter_count": len(params),
        "parameters": params
    }

    output = (
        f"PRESET GENERATION for: '{description}'\n"
        f"Device: {device_name} ({device_class}) on track {track_index}, device {device_index}\n"
        f"Variations requested: {variation_count}\n"
        f"Revert snapshot ID: {snapshot_id} (use restore_device_snapshot to undo)\n\n"
        f"Device has {len(params)} parameters:\n\n"
    )

    for p in params:
        quant = " [quantized]" if p.get("is_quantized") else ""
        items = f" options: {p.get('value_items')}" if p.get("value_items") else ""
        output += (
            f"  [{p['index']}] {p.get('name', '?')}: "
            f"current={p.get('value', '?')} "
            f"(range: {p.get('min', '?')}-{p.get('max', '?')}"
            f", default={p.get('default_value', '?')}){quant}{items}\n"
        )

    output += (
        f"\nNow calculate appropriate values for each parameter based on the description "
        f"'{description}' and device type '{device_class}'. Then call "
        f"batch_set_hidden_parameters(track_index={track_index}, device_index={device_index}, "
        f"parameters=[...]) with the calculated values."
    )

    return output
# ==========================================================================
# v1.6.0 Feature Tools — Feature 3: VST/AU Parameter Mapper
# ==========================================================================

@mcp.tool()
@_tool_handler("creating parameter map")
def create_parameter_map(
    ctx: Context,
    track_index: int,
    device_index: int,
    friendly_names: List[Dict[str, Any]]
) -> str:
    """Create a custom parameter map with friendly names for a device's parameters.

    Stores a mapping from cryptic parameter names/indices to human-readable names.
    Particularly useful for VST/AU plugins with obscure parameter names.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    - friendly_names: List of mappings, each with:
        - parameter_index: int (LOM index)
        - original_name: str (the parameter's actual name)
        - friendly_name: str (human-readable name)
        - category: str (optional grouping like "Filter", "Oscillator", "Envelope")

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if not isinstance(friendly_names, list) or len(friendly_names) == 0:
        raise ValueError("friendly_names must be a non-empty list.")

    m4l = get_m4l_connection()
    result = m4l.send_command("discover_params", {
        "track_index": track_index,
        "device_index": device_index
    })

    data = _m4l_result(result)
    device_name = data.get("device_name", "Unknown")
    device_class = data.get("device_class", "Unknown")

    map_id = str(uuid.uuid4())[:8]
    _param_map_store[map_id] = {
        "id": map_id,
        "track_index": track_index,
        "device_index": device_index,
        "device_name": device_name,
        "device_class": device_class,
        "mappings": friendly_names,
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    output = (
        f"Parameter map created for '{device_name}' (ID: {map_id})\n"
        f"Mapped parameters: {len(friendly_names)}\n\n"
    )

    categories: Dict[str, list] = {}
    for fn in friendly_names:
        cat = fn.get("category", "Uncategorized")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(fn)

    for cat, maps in categories.items():
        output += f"  [{cat}]\n"
        for m in maps:
            output += (
                f"    [{m.get('parameter_index', '?')}] "
                f"'{m.get('original_name', '?')}' -> "
                f"'{m.get('friendly_name', '?')}'\n"
            )
        output += "\n"

    return output
@mcp.tool()
@_tool_handler("getting parameter map")
def get_parameter_map(ctx: Context, map_id: str) -> str:
    """Retrieve a stored parameter map with friendly names.

    Parameters:
    - map_id: The ID of the parameter map to retrieve
    """
    if map_id not in _param_map_store:
        return f"Parameter map '{map_id}' not found."
    return json.dumps(_param_map_store[map_id])


@mcp.tool()
@_tool_handler("listing parameter maps")
def list_parameter_maps(ctx: Context) -> str:
    """List all stored parameter maps."""
    if not _param_map_store:
        return "No parameter maps stored. Use create_parameter_map() to create one."

    output = f"Parameter maps ({len(_param_map_store)}):\n\n"
    for mid, pmap in _param_map_store.items():
        output += (
            f"  ID: {mid}\n"
            f"  Device: {pmap.get('device_name', '?')} ({pmap.get('device_class', '?')})\n"
            f"  Location: track {pmap.get('track_index', '?')}, device {pmap.get('device_index', '?')}\n"
            f"  Mapped params: {len(pmap.get('mappings', []))}\n"
            f"  Created: {pmap.get('created', '?')}\n\n"
        )
    return output


@mcp.tool()
@_tool_handler("deleting parameter map")
def delete_parameter_map(ctx: Context, map_id: str) -> str:
    """Delete a stored parameter map.

    Parameters:
    - map_id: The ID of the parameter map to delete
    """
    if map_id not in _param_map_store:
        return f"Parameter map '{map_id}' not found."
    name = _param_map_store[map_id].get("device_name", map_id)
    del _param_map_store[map_id]
    return f"Deleted parameter map for '{name}' (ID: {map_id})."


# ==============================================================================
# Phase 7: Cue Points & Locators (M4L Bridge)
# ==============================================================================

@mcp.tool()
@_tool_handler("getting cue points")
def get_cue_points(ctx: Context) -> str:
    """Get all cue points (locators) from the arrangement view.

    Returns a list of all arrangement locators with their names and positions (in beats).
    Cue points are the markers visible in the arrangement timeline.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("get_cue_points")
    data = _m4l_result(result)
    cue_points = data.get("cue_points", [])
    count = data.get("cue_point_count", 0)

    if count == 0:
        return "No cue points (locators) found in the arrangement."

    output = f"Cue Points ({count}):\n\n"
    for cp in cue_points:
        time_beats = cp.get("time", 0)
        bars = int(time_beats // 4) + 1
        beat_in_bar = (time_beats % 4) + 1
        output += (
            f"  [{cp.get('index', '?')}] \"{cp.get('name', '')}\" "
            f"at {time_beats:.2f} beats (bar {bars}, beat {beat_in_bar:.1f})\n"
        )
    return output


@mcp.tool()
@_tool_handler("jumping to cue point")
def jump_to_cue_point(ctx: Context, cue_point_index: int) -> str:
    """Jump the playback position to a specific cue point (locator).

    Parameters:
    - cue_point_index: The index of the cue point to jump to (use get_cue_points to see available indices)

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(cue_point_index, "cue_point_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("jump_to_cue_point", {
        "cue_point_index": cue_point_index
    })

    data = _m4l_result(result)
    return (
        f"Jumped to cue point [{data.get('jumped_to', '?')}] "
        f"\"{data.get('name', '')}\" at {data.get('time', 0):.2f} beats."
    )


# ==============================================================================
# Phase 8: Groove Pool Access (M4L Bridge)
# ==============================================================================

@mcp.tool()
@_tool_handler("getting groove pool")
def get_groove_pool(ctx: Context) -> str:
    """Get all grooves from Ableton's groove pool.

    Returns groove templates with their properties: base amount, timing, velocity,
    random, and quantize rate. Grooves affect the rhythmic feel of clips.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("get_groove_pool")
    data = _m4l_result(result)
    grooves = data.get("grooves", [])
    count = data.get("groove_count", 0)

    if count == 0:
        return "Groove pool is empty. Drag groove files into Ableton's groove pool to use them."

    output = f"Groove Pool ({count} grooves):\n\n"
    for g in grooves:
        output += f"  [{g.get('index', '?')}] \"{g.get('name', '')}\"\n"
        if "base" in g:
            output += f"    Base: {g['base']:.0%}"
        if "timing" in g:
            output += f"  Timing: {g['timing']:.0%}"
        if "velocity" in g:
            output += f"  Velocity: {g['velocity']:.0%}"
        if "random" in g:
            output += f"  Random: {g['random']:.0%}"
        if "quantize_rate" in g:
            output += f"  Quantize: {g['quantize_rate']}"
        output += "\n"
    return output


@mcp.tool()
@_tool_handler("setting groove properties")
def set_groove_properties(
    ctx: Context,
    groove_index: int,
    base: float = None,
    timing: float = None,
    velocity: float = None,
    random: float = None,
    quantize_rate: int = None,
) -> str:
    """Set properties on a groove in the groove pool.

    Parameters:
    - groove_index: The index of the groove (use get_groove_pool to see available indices)
    - base: Base groove amount (0.0 to 1.0)
    - timing: Timing groove amount (0.0 to 1.0)
    - velocity: Velocity groove amount (0.0 to 1.0)
    - random: Random groove amount (0.0 to 1.0)
    - quantize_rate: Quantize rate index

    All property parameters are optional — only provided values will be changed.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(groove_index, "groove_index")
    properties = {}
    if base is not None:
        properties["base"] = float(base)
    if timing is not None:
        properties["timing"] = float(timing)
    if velocity is not None:
        properties["velocity"] = float(velocity)
    if random is not None:
        properties["random"] = float(random)
    if quantize_rate is not None:
        properties["quantize_rate"] = int(quantize_rate)

    if not properties:
        return "No properties specified to set. Provide at least one of: base, timing, velocity, random, quantize_rate."

    m4l = get_m4l_connection()
    result = m4l.send_command("set_groove_properties", {
        "groove_index": groove_index,
        "properties": properties,
    })

    data = _m4l_result(result)
    set_count = data.get("properties_set", 0)
    details = data.get("details", [])
    errors = data.get("errors", [])
    output = f"Groove [{groove_index}]: {set_count} properties set."
    if details:
        output += "\n" + ", ".join(f"{d['property']}={d['value']}" for d in details)
    if errors:
        output += f"\nErrors: {errors}"
    return output
# ==============================================================================
# Phase 6: Event-Driven Monitoring (M4L Bridge)
# ==============================================================================

@mcp.tool()
@_tool_handler("starting observation")
def observe_property(ctx: Context, lom_path: str, property_name: str) -> str:
    """Start monitoring a Live Object Model property for changes.

    Uses M4L's live.observer for near-instant (~10ms) change detection,
    much faster than polling via TCP.

    Parameters:
    - lom_path: The LOM path to observe (e.g., "live_set", "live_set tracks 0")
    - property_name: The property to watch (e.g., "is_playing", "tempo", "current_song_time")

    Common useful observations:
    - "live_set" + "is_playing" — detect play/stop
    - "live_set" + "tempo" — detect tempo changes
    - "live_set" + "current_song_time" — track playback position
    - "live_set tracks N" + "output_meter_level" — track level meter

    Use get_property_changes() to retrieve accumulated changes.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("observe_property", {
        "lom_path": lom_path,
        "property_name": property_name,
    })

    data = _m4l_result(result)
    if data.get("already_observing"):
        return f"Already observing {data.get('key', '?')}."
    return f"Now observing: {data.get('path', '?')}.{data.get('property', '?')}"


@mcp.tool()
@_tool_handler("stopping observation")
def stop_observing(ctx: Context, lom_path: str, property_name: str) -> str:
    """Stop monitoring a Live Object Model property.

    Parameters:
    - lom_path: The LOM path that was being observed
    - property_name: The property that was being watched

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("stop_observing", {
        "lom_path": lom_path,
        "property_name": property_name,
    })

    data = _m4l_result(result)
    if not data.get("was_observing", True):
        return f"Was not observing {data.get('key', '?')}."
    return (
        f"Stopped observing {data.get('key', '?')}. "
        f"Discarded {data.get('pending_changes_discarded', 0)} pending changes."
    )


@mcp.tool()
@_tool_handler("getting property changes")
def get_property_changes(ctx: Context) -> str:
    """Get accumulated property change events from all active observers.

    Returns all changes since the last call (changes are cleared after reading).
    Each change includes the property name, new value, and timestamp.

    Use observe_property() first to start monitoring properties.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("get_observed_changes")

    data = _m4l_result(result)
    total = data.get("total_changes", 0)
    obs_count = data.get("observer_count", 0)
    changes = data.get("changes", {})

    if obs_count == 0:
        return "No active observers. Use observe_property() to start monitoring."

    if total == 0:
        return f"No changes detected ({obs_count} active observers)."

    output = f"Property Changes ({total} total, {obs_count} observers):\n\n"
    for key, events in changes.items():
        output += f"  {key}:\n"
        for evt in events[-20:]:  # Show last 20 per observer
            output += f"    [{evt.get('time', '?')}] {evt.get('property', '?')} = {evt.get('value', '?')}\n"
        if len(events) > 20:
            output += f"    ... ({len(events) - 20} more)\n"
    return output


# ==============================================================================
# Phase 9: Undo-Clean Parameter Control (M4L Bridge)
# ==============================================================================

@mcp.tool()
@_tool_handler("setting parameter cleanly")
def set_parameter_clean(
    ctx: Context,
    track_index: int,
    device_index: int,
    parameter_index: int,
    value: float,
) -> str:
    """Set a device parameter via the M4L bridge with minimal undo impact.

    Unlike set_device_parameter (which goes through the Remote Script and creates
    a full undo entry), this routes through the M4L bridge for a lighter touch.
    Useful for automation-style continuous parameter changes where you don't want
    to pollute the undo history.

    Parameters:
    - track_index: The track containing the device
    - device_index: The device index on the track
    - parameter_index: The LOM parameter index (use discover_device_params to find indices)
    - value: The value to set (will be clamped to parameter min/max)

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    _validate_index(parameter_index, "parameter_index")

    m4l = get_m4l_connection()
    result = m4l.send_command("set_param_clean", {
        "track_index": track_index,
        "device_index": device_index,
        "parameter_index": parameter_index,
        "value": float(value),
    })

    data = _m4l_result(result)
    output = (
        f"Parameter '{data.get('parameter_name', '?')}' "
        f"set to {data.get('actual_value', '?')}"
    )
    if data.get("was_clamped"):
        output += f" (clamped from {data.get('requested_value', '?')})"
    return output
# ==============================================================================
# Phase 5: Audio Analysis (M4L Bridge)
# ==============================================================================

@mcp.tool()
@_tool_handler("analyzing audio")
def analyze_track_audio(ctx: Context, track_index: int = -1) -> str:
    """Analyze audio levels on any track (cross-track meter reading).

    Returns output meter levels (left/right) from the LOM for the target track,
    plus MSP-derived RMS/peak data if the Max patch has audio analysis objects
    connected (MSP data always comes from the device's own track).

    Parameters:
        track_index: Track to analyze (0-based). Default -1 = the track where
                     the M4L bridge device is loaded. Use -2 for master track.
                     Any track index 0+ reads that track's meters remotely.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("analyze_audio", {"track_index": track_index})
    data = _m4l_result(result)
    target = data.get("target_track_index", -1)
    track_label = data.get("track_name", f"track {target}")
    if target == -2:
        track_label = data.get("track_name", "Master")
    output = f"Audio Analysis ({track_label}):\n"

    if "output_meter_left" in data:
        output += f"  Output Meter L: {data['output_meter_left']:.4f}\n"
    if "output_meter_right" in data:
        output += f"  Output Meter R: {data['output_meter_right']:.4f}\n"
    if "output_meter_peak_left" in data:
        output += f"  Peak Level: {data['output_meter_peak_left']:.4f}\n"

    if data.get("has_msp_data"):
        output += f"\n  MSP Analysis from device track (age: {data.get('msp_data_age_ms', '?')}ms):\n"
        output += f"    RMS L: {data.get('rms_left', 0):.4f}  R: {data.get('rms_right', 0):.4f}\n"
        output += f"    Peak L: {data.get('peak_left', 0):.4f}  R: {data.get('peak_right', 0):.4f}\n"
    else:
        note = data.get("note", "")
        if note:
            output += f"\n  Note: {note}\n"

    return output


@mcp.tool()
@_tool_handler("analyzing spectrum")
def analyze_track_spectrum(ctx: Context) -> str:
    """Get spectral analysis data from the track where the M4L Audio Effect bridge is loaded.

    Returns frequency band magnitudes (8-band via fffb~ filter bank), dominant band,
    and spectral centroid. The M4L device must be an Audio Effect (not MIDI Effect)
    with plugin~ -> fffb~ 8 -> snapshot~ -> pack -> prepend spectrum_data -> [js] wired.

    If no spectral data is available, returns instructions for setting up the analysis.

    Requires the AbletonMCP_Bridge M4L Audio Effect device to be loaded on a track.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("analyze_spectrum")
    data = _m4l_result(result)

    if not data.get("has_spectrum"):
        return data.get("note", "No spectral data available. Set up fft~ in the Max patch.")

    output = "Spectral Analysis:\n"
    output += f"  Bins: {data.get('bin_count', 0)}\n"
    output += f"  Dominant bin: {data.get('dominant_bin', '?')} (magnitude: {data.get('dominant_magnitude', 0):.4f})\n"
    output += f"  Spectral centroid: {data.get('spectral_centroid', 0):.2f}\n"
    output += f"  Data age: {data.get('data_age_ms', '?')}ms\n"

    return output


@mcp.tool()
@_tool_handler("in cross-track audio analysis")
def analyze_cross_track_audio(ctx: Context, track_index: int, wait_ms: int = 500) -> str:
    """Analyze real MSP audio data (RMS, peak, 8-band spectrum) from ANY track via send-based routing.

    Temporarily routes audio from the target track to the return track where the
    M4L bridge device is loaded. Non-destructive: source track's main output to
    master continues normally, and the send level is restored after capture.

    Requirements:
    - The AbletonMCP_Bridge M4L Audio Effect device must be on a RETURN track
    - Audio must be playing on the target track during analysis
    - The Max patch must have plugin~ -> fffb~ 8 -> abs~ -> snapshot~ -> [js] wired
      (abs~ after each fffb~ outlet is REQUIRED for correct amplitude values)
    - The Max patch must have plugin~ -> peakamp~ -> snapshot~ -> [js] for RMS/peak

    Parameters:
        track_index: Track to analyze (0-based index of regular tracks)
        wait_ms: How long to wait for audio to flow through MSP chain (default 500ms,
                 range 300-2000ms). Increase for more stable readings.

    Returns RMS levels, peak levels, 8-band spectrum, spectral centroid, and output
    meters for both source and analysis return tracks.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("analyze_cross_track", {
        "track_index": track_index,
        "wait_ms": wait_ms,
    })

    data = _m4l_result(result)
    track_name = data.get("track_name", f"Track {track_index}")
    output = f"Cross-Track Audio Analysis ({track_name}, track {track_index}):\n"
    output += f"  Return track used: {data.get('return_track_index', '?')}\n"
    output += f"  Capture wait: {data.get('capture_wait_ms', '?')}ms "
    output += f"(actual: {data.get('actual_capture_time_ms', '?')}ms)\n\n"

    if data.get("has_msp_data"):
        output += "  MSP Analysis (from return track DSP chain):\n"
        output += f"    RMS  L: {data.get('rms_left', 0):.6f}  R: {data.get('rms_right', 0):.6f}\n"
        output += f"    Peak L: {data.get('peak_left', 0):.6f}  R: {data.get('peak_right', 0):.6f}\n"
    else:
        note = data.get("note", "No MSP data captured.")
        output += f"  MSP Data: NOT AVAILABLE\n  Note: {note}\n"

    output += f"\n  Source Track Meters:\n"
    output += f"    L: {data.get('source_output_meter_left', 0):.4f}  "
    output += f"R: {data.get('source_output_meter_right', 0):.4f}\n"
    output += f"  Return Track Meters:\n"
    output += f"    L: {data.get('return_output_meter_left', 0):.4f}  "
    output += f"R: {data.get('return_output_meter_right', 0):.4f}\n"

    if data.get("has_spectrum"):
        output += f"\n  Spectrum ({data.get('bin_count', 0)} bands):\n"
        bins = data.get("spectrum", [])
        band_labels = ["Sub", "Bass", "Low-Mid", "Mid", "Upper-Mid", "Presence", "Brilliance", "Air"]
        for i, val in enumerate(bins):
            label = band_labels[i] if i < len(band_labels) else f"Band {i}"
            bar = "#" * min(40, int(val * 50))
            output += f"    {label:>12}: {val:.4f} {bar}\n"
        output += f"  Dominant band: {data.get('dominant_bin', '?')} "
        output += f"(magnitude: {data.get('dominant_magnitude', 0):.4f})\n"
        output += f"  Spectral centroid: {data.get('spectral_centroid', 0):.2f}\n"

    output += f"\n  Send restored to: {data.get('original_send_value', 0):.4f}\n"
    return output


# ==============================================================================
# M4L Bridge v3.3.0 — New Tools (App Version, Automation States, Chain Discovery)
# ==============================================================================

@mcp.tool()
@_tool_handler("getting Ableton version")
def get_ableton_version(ctx: Context) -> str:
    """Get the Ableton Live application version via M4L bridge.

    Returns major, minor, bugfix version numbers and display string.
    Useful for version-gating features (e.g. AB comparison requires Live 12.3+).

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.
    """
    m4l = get_m4l_connection()
    result = m4l.send_command("get_app_version")
    data = _m4l_result(result)
    display = data.get("display", "Unknown")
    vs = data.get("version_string")
    if vs:
        return f"{display} ({vs})"
    return display


@mcp.tool()
@_tool_handler("getting automation states")
def get_automation_states(ctx: Context, track_index: int, device_index: int) -> str:
    """Get automation state for all parameters of a device via M4L bridge.

    Returns only parameters that have automation (state > 0).
    States: 0=none, 1=active, 2=overridden (manually changed after automation was written).

    Use this to check which parameters have automation before modifying them,
    or to detect overridden automation that may need re-enabling.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device to inspect
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("get_automation_states", {
        "track_index": track_index,
        "device_index": device_index,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("discovering device chains via M4L")
def discover_chains_m4l(ctx: Context, track_index: int, device_index: int, extra_path: str = "") -> str:
    """Discover chains in a rack device via M4L bridge with enhanced detail.

    Returns chain hierarchy including:
    - Regular chains with their devices
    - Return chains (Rack-level sends, e.g. Instrument Rack return chains)
    - Drum pad details: in_note, out_note, choke_group, mute, solo

    Use extra_path to navigate nested racks (e.g. "chains 0 devices 1").

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.

    Parameters:
    - track_index: The index of the track containing the rack device
    - device_index: The index of the rack device
    - extra_path: Additional LOM path to navigate into nested racks (optional)
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("discover_chains", {
        "track_index": track_index,
        "device_index": device_index,
        "extra_path": extra_path,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("getting chain device parameters via M4L")
def get_chain_device_params_m4l(ctx: Context, track_index: int, device_index: int, chain_index: int, chain_device_index: int) -> str:
    """Discover ALL parameters (including hidden/non-automatable) of a device inside a rack chain.

    Uses M4L bridge to access the full LOM parameter tree of a device nested
    inside a chain of a rack (Instrument Rack, Audio Effect Rack, Drum Rack, etc.).

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.

    Parameters:
    - track_index: The index of the track containing the rack
    - device_index: The index of the rack device
    - chain_index: The index of the chain within the rack
    - chain_device_index: The index of the device within the chain
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    _validate_index(chain_index, "chain_index")
    _validate_index(chain_device_index, "chain_device_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("get_chain_device_params", {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
        "chain_device_index": chain_device_index,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("setting chain device parameter via M4L")
def set_chain_device_param_m4l(ctx: Context, track_index: int, device_index: int, chain_index: int, chain_device_index: int, parameter_index: int, value: float) -> str:
    """Set a parameter value on a device inside a rack chain via M4L bridge.

    Allows setting any parameter (including hidden/non-automatable) on devices
    nested inside rack chains. Use get_chain_device_params_m4l() first to discover
    available parameters and their valid ranges.

    Requires the AbletonMCP_Bridge M4L device to be loaded on any track.

    Parameters:
    - track_index: The index of the track containing the rack
    - device_index: The index of the rack device
    - chain_index: The index of the chain within the rack
    - chain_device_index: The index of the device within the chain
    - parameter_index: The index of the parameter to set
    - value: The value to set the parameter to (must be within min/max range)
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    _validate_index(chain_index, "chain_index")
    _validate_index(chain_device_index, "chain_device_index")
    _validate_index(parameter_index, "parameter_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("set_chain_device_param", {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
        "chain_device_index": chain_device_index,
        "parameter_index": parameter_index,
        "value": value,
    })
    data = _m4l_result(result)
    return json.dumps(data)


# ==============================================================================
# M4L Bridge v3.6.0 — Note Surgery, Chain Mixing, AB Compare, Scrub, Stereo
# ==============================================================================

@mcp.tool()
@_tool_handler("getting clip notes with IDs")
def get_clip_notes_with_ids(ctx: Context, track_index: int, clip_index: int) -> str:
    """Get all MIDI notes in a clip with stable note IDs via M4L bridge.

    Returns notes with unique note_id fields that can be used for in-place
    editing via modify_clip_notes() or surgical removal via remove_clip_notes_by_id().
    Each note includes: note_id, pitch, start_time, duration, velocity, mute,
    probability, velocity_deviation, release_velocity.

    Requires the AbletonMCP_Bridge M4L device. Live 11+ required for note IDs.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the MIDI clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("get_clip_notes_by_id", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("modifying clip notes by ID")
def modify_clip_notes(ctx: Context, track_index: int, clip_index: int, modifications: str) -> str:
    """Modify MIDI notes in-place by their stable note ID via M4L bridge.

    Performs non-destructive in-place editing — no remove+re-add needed.
    Use get_clip_notes_with_ids() first to get note IDs.

    Each modification dict must include 'note_id' and any properties to change:
    pitch, start_time, duration, velocity, mute, probability, velocity_deviation, release_velocity.

    Requires the AbletonMCP_Bridge M4L device. Live 11+ required.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the MIDI clip
    - modifications: JSON string of list of note modification dicts, each with 'note_id' and changed properties.
      Example: '[{"note_id": 1, "velocity": 100}, {"note_id": 5, "pitch": 64, "start_time": 2.0}]'
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    mods = json.loads(modifications) if isinstance(modifications, str) else modifications
    m4l = get_m4l_connection()
    result = m4l.send_command("modify_clip_notes", {
        "track_index": track_index,
        "clip_index": clip_index,
        "modifications": mods,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("removing clip notes by ID")
def remove_clip_notes_by_id(ctx: Context, track_index: int, clip_index: int, note_ids: str) -> str:
    """Remove specific MIDI notes by their stable note ID via M4L bridge.

    Surgical note removal — only removes the exact notes specified by ID.
    Use get_clip_notes_with_ids() first to get note IDs.

    Requires the AbletonMCP_Bridge M4L device. Live 11+ required.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the MIDI clip
    - note_ids: JSON string of list of note IDs to remove. Example: '[1, 5, 12]'
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ids = json.loads(note_ids) if isinstance(note_ids, str) else note_ids
    m4l = get_m4l_connection()
    result = m4l.send_command("remove_clip_notes_by_id", {
        "track_index": track_index,
        "clip_index": clip_index,
        "note_ids": ids,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("getting chain mixing state")
def get_chain_mixing(ctx: Context, track_index: int, device_index: int, chain_index: int) -> str:
    """Get mixing state (volume, pan, sends, mute, solo) of a chain in a rack device via M4L bridge.

    Returns the ChainMixerDevice properties: volume, panning, chain_activator (mute),
    sends, plus the chain's mute and solo state. Critical for Drum Rack pad balancing
    and Instrument Rack chain mixing.

    Requires the AbletonMCP_Bridge M4L device.

    Parameters:
    - track_index: The index of the track containing the rack
    - device_index: The index of the rack device (Instrument Rack, Audio Effect Rack, Drum Rack)
    - chain_index: The index of the chain within the rack
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    _validate_index(chain_index, "chain_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("get_chain_mixing", {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("setting chain mixing state")
def set_chain_mixing(ctx: Context, track_index: int, device_index: int, chain_index: int, properties: str) -> str:
    """Set mixing properties on a chain in a rack device via M4L bridge.

    Set any combination of: volume, panning, chain_activator (1=active, 0=muted),
    mute (0/1), solo (0/1), sends (array of {index, value}).

    Requires the AbletonMCP_Bridge M4L device.

    Parameters:
    - track_index: The index of the track containing the rack
    - device_index: The index of the rack device
    - chain_index: The index of the chain within the rack
    - properties: JSON string with mixing properties to set.
      Example: '{"volume": 0.8, "panning": -0.5, "mute": 0, "sends": [{"index": 0, "value": 0.5}]}'
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    _validate_index(chain_index, "chain_index")
    props = json.loads(properties) if isinstance(properties, str) else properties
    m4l = get_m4l_connection()
    result = m4l.send_command("set_chain_mixing", {
        "track_index": track_index,
        "device_index": device_index,
        "chain_index": chain_index,
        "properties": props,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("comparing device AB presets")
def device_ab_compare(ctx: Context, track_index: int, device_index: int, action: str) -> str:
    """Compare device presets using AB comparison via M4L bridge (Live 12.3+).

    Save device state to A/B slots for instant comparison during sound design.
    Actions:
    - 'get_state': Check if AB comparison is supported and which slot is active
    - 'save': Save current device state to the other AB slot
    - 'toggle': Toggle between A and B presets

    Requires the AbletonMCP_Bridge M4L device and Ableton Live 12.3+.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device
    - action: 'get_state', 'save', or 'toggle'
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if action not in ("get_state", "save", "toggle"):
        return "action must be 'get_state', 'save', or 'toggle'"
    m4l = get_m4l_connection()
    result = m4l.send_command("device_ab_compare", {
        "track_index": track_index,
        "device_index": device_index,
        "action": action,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("scrubbing clip")
def clip_scrub(ctx: Context, track_index: int, clip_index: int, action: str, beat_time: float = 0.0) -> str:
    """Scrub within a clip at a specific beat position via M4L bridge.

    Performs quantized clip scrubbing (like mouse scrubbing in Ableton) —
    respects Global Quantization, loops in time with transport.
    Different from navigate_playback(scrub_by) which moves the global transport.

    Actions:
    - 'scrub': Start scrubbing at the given beat_time (continues until stop_scrub)
    - 'stop_scrub': Stop scrubbing

    Requires the AbletonMCP_Bridge M4L device.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot
    - action: 'scrub' or 'stop_scrub'
    - beat_time: The beat position to scrub to (only for 'scrub' action)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    if action not in ("scrub", "stop_scrub"):
        return "action must be 'scrub' or 'stop_scrub'"
    m4l = get_m4l_connection()
    result = m4l.send_command("clip_scrub", {
        "track_index": track_index,
        "clip_index": clip_index,
        "action": action,
        "beat_time": beat_time,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("getting split stereo panning")
def get_split_stereo(ctx: Context, track_index: int) -> str:
    """Get the split stereo panning values (left and right) for a track via M4L bridge.

    Returns the Left Split Stereo and Right Split Stereo DeviceParameter values
    from the track's mixer_device. These control independent L/R panning when
    split stereo mode is enabled.

    Requires the AbletonMCP_Bridge M4L device.

    Parameters:
    - track_index: The index of the track
    """
    _validate_index(track_index, "track_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("get_split_stereo", {
        "track_index": track_index,
    })
    data = _m4l_result(result)
    return json.dumps(data)


@mcp.tool()
@_tool_handler("setting split stereo panning")
def set_split_stereo(ctx: Context, track_index: int, left: float, right: float) -> str:
    """Set the split stereo panning values (left and right) for a track via M4L bridge.

    Sets the Left Split Stereo and Right Split Stereo DeviceParameter values
    on the track's mixer_device.

    Requires the AbletonMCP_Bridge M4L device.

    Parameters:
    - track_index: The index of the track
    - left: Left channel pan value (typically -1.0 to 1.0)
    - right: Right channel pan value (typically -1.0 to 1.0)
    """
    _validate_index(track_index, "track_index")
    m4l = get_m4l_connection()
    result = m4l.send_command("set_split_stereo", {
        "track_index": track_index,
        "left": left,
        "right": right,
    })
    data = _m4l_result(result)
    return json.dumps(data)


# ==============================================================================
# Grid Notation Tools
# ==============================================================================

@mcp.tool()
@_tool_handler("converting clip to grid")
def clip_to_grid(ctx: Context, track_index: int, clip_index: int) -> str:
    """Read a MIDI clip and display as ASCII grid notation (auto-detects drum vs melodic).

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    try:
        from MCP_Server.grid_notation import notes_to_grid
        _validate_index(track_index, "track_index")
        _validate_index(clip_index, "clip_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_clip_notes", {
            "track_index": track_index,
            "clip_index": clip_index,
            "start_time": 0.0,
            "time_span": 0.0,
            "start_pitch": 0,
            "pitch_span": 128,
        })
        notes = result.get("notes", [])
        clip_length = result.get("clip_length", 4.0)
        clip_name = result.get("clip_name", "Unknown")
        grid = notes_to_grid(notes)
        return f"Clip: {clip_name} ({clip_length} beats)\n\n{grid}"
    except ImportError:
        return "Error: grid_notation module not available"


@mcp.tool()
@_tool_handler("writing grid to clip")
def grid_to_clip(
    ctx: Context,
    track_index: int,
    clip_index: int,
    grid: str,
    length: float = 4.0,
    clear_existing: bool = True,
) -> str:
    """Write ASCII grid notation to a MIDI clip. Creates the clip if it doesn't exist.

    Grid format for drums:
        KK|o---o---|o---o-o-|
        SN|----o---|----o---|
        HC|x-x-x-x-|x-x-x-x-|

    Grid format for melodic:
        G4|----o---|--------|
        E4|--o-----|oooo----|
        C4|o-------|----oooo|

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot
    - grid: ASCII grid string (multi-line)
    - length: Clip length in beats (default: 4.0)
    - clear_existing: Clear existing notes before writing (default: true)
    """
    from MCP_Server.grid_notation import parse_grid
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    if length <= 0:
        return "Error: length must be greater than 0"

    notes = parse_grid(grid)
    if not notes:
        return "Error: No notes parsed from grid. Check the grid format."

    ableton = get_ableton_connection()

    # Create clip if it doesn't exist (ignore error if it already exists)
    try:
        ableton.send_command("create_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "length": length,
        })
    except Exception:
        pass

    # Clear existing notes if requested
    if clear_existing:
        try:
            ableton.send_command("clear_clip_notes", {
                "track_index": track_index,
                "clip_index": clip_index,
            })
        except Exception:
            pass

    # Add the parsed notes
    ableton.send_command("add_notes_to_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
        "notes": notes,
    })
    return f"Wrote {len(notes)} notes from grid to track {track_index}, slot {clip_index} ({length} beats)"
# ==============================================================================
# New Tools: Session / Transport
# ==============================================================================

@mcp.tool()
@_tool_handler("getting loop info")
def get_loop_info(ctx: Context) -> str:
    """Get loop bracket information including start, end, length, and current playback time."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_loop_info")
    return json.dumps(result)


@mcp.tool()
@_tool_handler("getting recording status")
def get_recording_status(ctx: Context) -> str:
    """Get the current recording status including armed tracks, record mode, and overdub state."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_recording_status")
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting loop start")
def set_loop_start(ctx: Context, position: float) -> str:
    """Set the loop start position in beats.

    Parameters:
    - position: The loop start position in beats
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("set_loop_start", {"position": position})
    return f"Loop start set to {result.get('loop_start', position)} beats"


@mcp.tool()
@_tool_handler("setting loop end")
def set_loop_end(ctx: Context, position: float) -> str:
    """Set the loop end position in beats.

    Parameters:
    - position: The loop end position in beats
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("set_loop_end", {"position": position})
    return f"Loop end set to {result.get('loop_end', position)} beats"


@mcp.tool()
@_tool_handler("setting loop length")
def set_loop_length(ctx: Context, length: float) -> str:
    """Set the loop length in beats (adjusts loop end relative to loop start).

    Parameters:
    - length: The loop length in beats
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("set_loop_length", {"length": length})
    return f"Loop length set to {result.get('loop_length', length)} beats"


@mcp.tool()
@_tool_handler("setting playback position")
def set_playback_position(ctx: Context, position: float) -> str:
    """Move the playhead to a specific beat position.

    Parameters:
    - position: The position in beats to jump to (0.0 = start of song)
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("set_playback_position", {"position": position})
    return f"Playback position set to {result.get('position', position)} beats"


@mcp.tool()
@_tool_handler("setting arrangement overdub")
def set_arrangement_overdub(ctx: Context, enabled: bool) -> str:
    """Enable or disable arrangement overdub mode.

    Parameters:
    - enabled: True to enable overdub, False to disable
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("set_arrangement_overdub", {"enabled": enabled})
    return f"Arrangement overdub {'enabled' if result.get('overdub', enabled) else 'disabled'}"


@mcp.tool()
@_tool_handler("starting arrangement recording")
def start_arrangement_recording(ctx: Context) -> str:
    """Start arrangement recording in Ableton."""
    ableton = get_ableton_connection()
    result = ableton.send_command("start_arrangement_recording")
    return "Arrangement recording started"


@mcp.tool()
@_tool_handler("stopping arrangement recording")
def stop_arrangement_recording(ctx: Context) -> str:
    """Stop arrangement recording in Ableton."""
    ableton = get_ableton_connection()
    result = ableton.send_command("stop_arrangement_recording")
    return "Arrangement recording stopped"


@mcp.tool()
@_tool_handler("setting metronome")
def set_metronome(ctx: Context, enabled: bool) -> str:
    """Enable or disable the metronome.

    Parameters:
    - enabled: True to enable the metronome, False to disable
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("set_metronome", {"enabled": enabled})
    return f"Metronome {'enabled' if result.get('metronome', enabled) else 'disabled'}"


@mcp.tool()
@_tool_handler("tapping tempo")
def tap_tempo(ctx: Context) -> str:
    """Tap tempo - call repeatedly to set tempo by tapping."""
    ableton = get_ableton_connection()
    result = ableton.send_command("tap_tempo")
    return f"Tap tempo registered. Current tempo: {result.get('tempo', '?')} BPM"


# ==============================================================================
# New Tools: Tracks
# ==============================================================================

@mcp.tool()
@_tool_handler("getting all tracks info")
def get_all_tracks_info(ctx: Context) -> str:
    """Get information about all tracks in the session at once (bulk query)."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_all_tracks_info")
    return json.dumps(result)


@mcp.tool()
@_tool_handler("getting return tracks info")
def get_return_tracks_info(ctx: Context) -> str:
    """Get detailed information about all return tracks (bulk query)."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_return_tracks_info")
    return json.dumps(result)


@mcp.tool()
@_tool_handler("creating return track")
def create_return_track(ctx: Context) -> str:
    """Create a new return track in the session."""
    ableton = get_ableton_connection()
    result = ableton.send_command("create_return_track")
    return f"Created return track: {result.get('name', 'unknown')}"


@mcp.tool()
@_tool_handler("setting track color")
def set_track_color(ctx: Context, track_index: int, color_index: int) -> str:
    """Set the color of a track.

    Parameters:
    - track_index: The index of the track
    - color_index: The color index (0-69, Ableton's color palette)
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_color", {
        "track_index": track_index,
        "color_index": color_index,
    })
    return f"Track {track_index} color set to {color_index}"


@mcp.tool()
@_tool_handler("arming track")
def arm_track(ctx: Context, track_index: int) -> str:
    """Arm a track for recording.

    Parameters:
    - track_index: The index of the track to arm
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("arm_track", {"track_index": track_index})
    return f"Track {track_index} armed"


@mcp.tool()
@_tool_handler("disarming track")
def disarm_track(ctx: Context, track_index: int) -> str:
    """Disarm a track (disable recording).

    Parameters:
    - track_index: The index of the track to disarm
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("disarm_track", {"track_index": track_index})
    return f"Track {track_index} disarmed"


@mcp.tool()
@_tool_handler("grouping tracks")
def group_tracks(ctx: Context, track_indices: list) -> str:
    """Group multiple tracks together.

    Parameters:
    - track_indices: List of track indices to group together
    """
    if not isinstance(track_indices, list) or len(track_indices) < 2:
        return "Error: track_indices must be a list of at least 2 track indices"
    ableton = get_ableton_connection()
    result = ableton.send_command("group_tracks", {"track_indices": track_indices})
    return f"Grouped {len(track_indices)} tracks"


# ==============================================================================
# New Tools: Audio
# ==============================================================================

@mcp.tool()
@_tool_handler("getting audio clip info")
def get_audio_clip_info(ctx: Context, track_index: int, clip_index: int) -> str:
    """Get detailed information about an audio clip (warp mode, gain, file path, etc.).

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_audio_clip_info", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("analyzing audio clip")
def analyze_audio_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """Analyze an audio clip comprehensively (tempo, warp, sample properties, frequency hints).

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("analyze_audio_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting warp mode")
def set_warp_mode(ctx: Context, track_index: int, clip_index: int, warp_mode: str) -> str:
    """Set the warp mode for an audio clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - warp_mode: The warp mode (beats, tones, texture, re_pitch, complex, complex_pro)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_warp_mode", {
        "track_index": track_index,
        "clip_index": clip_index,
        "warp_mode": warp_mode,
    })
    return f"Warp mode set to {result.get('warp_mode', warp_mode)}"


@mcp.tool()
@_tool_handler("setting clip warp")
def set_clip_warp(ctx: Context, track_index: int, clip_index: int, warping_enabled: bool) -> str:
    """Enable or disable warping for an audio clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - warping_enabled: True to enable warping, False to disable
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_warp", {
        "track_index": track_index,
        "clip_index": clip_index,
        "warping_enabled": warping_enabled,
    })
    return f"Warping {'enabled' if result.get('warping', warping_enabled) else 'disabled'}"


@mcp.tool()
@_tool_handler("reversing clip")
def reverse_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """Reverse an audio clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("reverse_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    return f"Clip reversed: {result.get('reversed', True)}"


@mcp.tool()
@_tool_handler("freezing track")
def freeze_track(ctx: Context, track_index: int) -> str:
    """Freeze a track (render effects in place to reduce CPU load).

    Parameters:
    - track_index: The index of the track to freeze
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("freeze_track", {"track_index": track_index})
    return f"Track {track_index} ({result.get('track_name', '?')}) frozen"


@mcp.tool()
@_tool_handler("unfreezing track")
def unfreeze_track(ctx: Context, track_index: int) -> str:
    """Unfreeze a track.

    Parameters:
    - track_index: The index of the track to unfreeze
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("unfreeze_track", {"track_index": track_index})
    return f"Track {track_index} ({result.get('track_name', '?')}) unfrozen"


# ==============================================================================
# New Tools: MIDI
# ==============================================================================

@mcp.tool()
@_tool_handler("capturing MIDI")
def capture_midi(ctx: Context) -> str:
    """Capture recently played MIDI notes (requires Live 11 or later)."""
    ableton = get_ableton_connection()
    result = ableton.send_command("capture_midi")
    return "MIDI captured successfully"


@mcp.tool()
@_tool_handler("applying groove")
def apply_groove(ctx: Context, track_index: int, clip_index: int, groove_amount: float) -> str:
    """Apply groove to a MIDI clip.

    Parameters:
    - track_index: The index of the track containing the clip
    - clip_index: The index of the clip slot containing the clip
    - groove_amount: Groove amount (0.0 to 1.0)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("apply_groove", {
        "track_index": track_index,
        "clip_index": clip_index,
        "groove_amount": groove_amount,
    })
    return f"Groove amount set to {result.get('groove_amount', groove_amount)}"


# ==============================================================================
# New Tools: Arrangement
# ==============================================================================

@mcp.tool()
@_tool_handler("getting arrangement clips")
def get_arrangement_clips(ctx: Context, track_index: int) -> str:
    """Get all clips in arrangement view for a track.

    Parameters:
    - track_index: The index of the track to get arrangement clips from
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_arrangement_clips", {"track_index": track_index})
    return json.dumps(result)


@mcp.tool()
@_tool_handler("deleting time")
def delete_time(ctx: Context, start_time: float, end_time: float) -> str:
    """Delete a section of time from the arrangement (removes time and shifts everything after).

    Parameters:
    - start_time: Start position in beats
    - end_time: End position in beats
    """
    if start_time >= end_time:
        return "Error: start_time must be less than end_time"
    ableton = get_ableton_connection()
    result = ableton.send_command("delete_time", {
        "start_time": start_time,
        "end_time": end_time,
    })
    return f"Deleted time from {start_time} to {end_time} ({result.get('deleted_length', end_time - start_time)} beats)"


@mcp.tool()
@_tool_handler("duplicating time")
def duplicate_time(ctx: Context, start_time: float, end_time: float) -> str:
    """Duplicate a section of time in the arrangement (copies and inserts after the selection).

    Parameters:
    - start_time: Start position in beats
    - end_time: End position in beats
    """
    if start_time >= end_time:
        return "Error: start_time must be less than end_time"
    ableton = get_ableton_connection()
    result = ableton.send_command("duplicate_time", {
        "start_time": start_time,
        "end_time": end_time,
    })
    return f"Duplicated time from {start_time} to {end_time} (pasted at {result.get('pasted_at', end_time)})"


@mcp.tool()
@_tool_handler("inserting silence")
def insert_silence(ctx: Context, position: float, length: float) -> str:
    """Insert silence at a position in the arrangement (shifts everything after).

    Parameters:
    - position: The position in beats to insert silence at
    - length: The length of silence in beats
    """
    if length <= 0:
        return "Error: length must be greater than 0"
    ableton = get_ableton_connection()
    result = ableton.send_command("insert_silence", {
        "position": position,
        "length": length,
    })
    return f"Inserted {length} beats of silence at position {position}"


# ==============================================================================
# New Tools: Track-level Automation
# ==============================================================================

@mcp.tool()
@_tool_handler("creating track automation")
def create_track_automation(
    ctx: Context,
    track_index: int,
    parameter_name: str,
    automation_points: list,
) -> str:
    """Create automation for a track parameter (arrangement-level).

    For arrangement-level automation on the timeline. For automation within a
    session clip's envelope, use create_clip_automation instead.

    Parameters:
    - track_index: The index of the track
    - parameter_name: Name of the parameter to automate (e.g., "Volume", "Pan")
    - automation_points: List of {time: float, value: float} dictionaries
    """
    _validate_index(track_index, "track_index")
    _validate_automation_points(automation_points)
    automation_points = _reduce_automation_points(automation_points)
    ableton = get_ableton_connection()
    result = ableton.send_command("create_track_automation", {
        "track_index": track_index,
        "parameter_name": parameter_name,
        "automation_points": automation_points,
    })
    return f"Created track automation for '{parameter_name}' with {result.get('points_added', len(automation_points))} points"
@mcp.tool()
@_tool_handler("clearing track automation")
def clear_track_automation(
    ctx: Context,
    track_index: int,
    parameter_name: str,
    start_time: float,
    end_time: float,
) -> str:
    """Clear automation for a parameter in a time range (arrangement-level).

    Parameters:
    - track_index: The index of the track
    - parameter_name: Name of the parameter to clear automation for
    - start_time: Start time in beats
    - end_time: End time in beats
    """
    _validate_index(track_index, "track_index")
    if start_time >= end_time:
        return "Error: start_time must be less than end_time"
    ableton = get_ableton_connection()
    result = ableton.send_command("clear_track_automation", {
        "track_index": track_index,
        "parameter_name": parameter_name,
        "start_time": start_time,
        "end_time": end_time,
    })
    return f"Cleared automation for '{parameter_name}' from {start_time} to {end_time}"
# ==============================================================================
# New Tools: Devices (track_type support)
# ==============================================================================

@mcp.tool()
@_tool_handler("getting macro values")
def get_macro_values(ctx: Context, track_index: int, device_index: int) -> str:
    """Get the current macro knob values for an Instrument Rack.

    Parameters:
    - track_index: The index of the track containing the device
    - device_index: The index of the device on the track
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_macro_values", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return json.dumps(result)


# ==============================================================================
# New Tools: v2.1.0 — Undo/Redo, Cue Points, Transport, Pitch, Routing, Scenes
# ==============================================================================

@mcp.tool()
@_tool_handler("performing undo")
def undo(ctx: Context) -> str:
    """Undo the last action in Ableton.

    Useful for reverting changes made by previous tool calls. Returns whether
    the undo was performed or if there was nothing to undo.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("undo")
    if result.get("undone"):
        return "Undo performed"
    return f"Nothing to undo: {result.get('reason', 'unknown')}"


@mcp.tool()
@_tool_handler("performing redo")
def redo(ctx: Context) -> str:
    """Redo the last undone action in Ableton.

    Re-applies a previously undone action.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("redo")
    if result.get("redone"):
        return "Redo performed"
    return f"Nothing to redo: {result.get('reason', 'unknown')}"


@mcp.tool()
@_tool_handler("continuing playback")
def continue_playing(ctx: Context) -> str:
    """Continue playback from the current position.

    Unlike start_playback which jumps to the play position, this resumes
    from exactly where the playhead is now. Useful after stopping to audition
    a section without losing your place.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("continue_playing")
    return f"Playback continued from beat {result.get('position', '?')}"


@mcp.tool()
@_tool_handler("re-enabling automation")
def re_enable_automation(ctx: Context) -> str:
    """Re-enable all automation that has been manually overridden.

    When you manually adjust a parameter that has automation, Ableton disables
    the automation for that parameter (shown as an orange LED). This tool
    re-enables all overridden automation at once.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("re_enable_automation")
    return "All automation re-enabled"


@mcp.tool()
@_tool_handler("toggling cue point")
def set_or_delete_cue(ctx: Context) -> str:
    """Toggle a cue point at the current playback position.

    If a cue point exists at the current position, it is deleted.
    Otherwise, a new cue point is created. Use set_playback_position
    first to move the playhead to the desired location.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("set_or_delete_cue")
    return f"Cue point toggled at beat {result.get('position', '?')}"


@mcp.tool()
@_tool_handler("jumping to cue")
def jump_to_cue(ctx: Context, direction: str) -> str:
    """Jump the playhead to the next or previous cue point.

    Parameters:
    - direction: 'next' to jump forward, 'prev' to jump backward
    """
    if direction not in ("next", "prev"):
        return "Error: direction must be 'next' or 'prev'"
    ableton = get_ableton_connection()
    result = ableton.send_command("jump_to_cue", {"direction": direction})
    if result.get("jumped"):
        return f"Jumped to {direction} cue point at beat {result.get('position', '?')}"
    return f"Cannot jump: {result.get('reason', 'no cue point found')}"


@mcp.tool()
@_tool_handler("setting clip pitch")
def set_clip_pitch(ctx: Context, track_index: int, clip_index: int,
                   pitch_coarse: int = None, pitch_fine: float = None) -> str:
    """Set pitch transposition for an audio clip.

    Parameters:
    - track_index: The index of the track
    - clip_index: The index of the clip slot
    - pitch_coarse: Semitones shift (-48 to +48). Optional.
    - pitch_fine: Cents shift (-50.0 to +50.0). Optional.

    Only works on audio clips (not MIDI). Useful for tuning samples,
    creating harmonies, or pitch-correcting audio.
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    params = {"track_index": track_index, "clip_index": clip_index}
    if pitch_coarse is not None:
        params["pitch_coarse"] = pitch_coarse
    if pitch_fine is not None:
        params["pitch_fine"] = pitch_fine
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_pitch", params)
    return f"Clip '{result.get('clip_name', '?')}' pitch set to {result.get('pitch_coarse', 0)} semitones, {result.get('pitch_fine', 0)} cents"
@mcp.tool()
@_tool_handler("setting clip launch mode")
def set_clip_launch_mode(ctx: Context, track_index: int, clip_index: int,
                         launch_mode: int) -> str:
    """Set the launch mode for a clip.

    Parameters:
    - track_index: The index of the track
    - clip_index: The index of the clip slot
    - launch_mode: 0=trigger (default), 1=gate (plays while held), 2=toggle, 3=repeat

    Controls how the clip responds to launch triggers in session view.
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    mode_names = {0: "trigger", 1: "gate", 2: "toggle", 3: "repeat"}
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_launch_mode", {
        "track_index": track_index,
        "clip_index": clip_index,
        "launch_mode": launch_mode,
    })
    mode_name = mode_names.get(result.get("launch_mode", launch_mode), "unknown")
    return f"Clip '{result.get('clip_name', '?')}' launch mode set to {mode_name}"
@mcp.tool()
@_tool_handler("setting scene tempo")
def set_scene_tempo(ctx: Context, scene_index: int, tempo: float) -> str:
    """Set a tempo override for a scene.

    Parameters:
    - scene_index: The index of the scene
    - tempo: BPM value (e.g. 120.0), or 0 to clear the tempo override

    When a scene with a tempo override is fired, the song tempo changes
    to match. Set to 0 to remove the override.
    """
    _validate_index(scene_index, "scene_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_scene_tempo", {
        "scene_index": scene_index,
        "tempo": tempo,
    })
    if tempo == 0:
        return f"Scene {scene_index} ('{result.get('name', '?')}') tempo override cleared"
    return f"Scene {scene_index} ('{result.get('name', '?')}') tempo set to {result.get('tempo', tempo)} BPM"


@mcp.tool()
@_tool_handler("getting track routing")
def get_track_routing(ctx: Context, track_index: int) -> str:
    """Get current input/output routing and available options for a track.

    Parameters:
    - track_index: The index of the track

    Returns the current input/output routing types and channels, plus lists
    of all available routing options. Useful for understanding and configuring
    side-chain routing, resampling, and multi-output setups.
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_track_routing", {
        "track_index": track_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting track routing")
def set_track_routing(ctx: Context, track_index: int,
                      input_type: str = None, input_channel: str = None,
                      output_type: str = None, output_channel: str = None) -> str:
    """Set input/output routing for a track by display name.

    Parameters:
    - track_index: The index of the track
    - input_type: Input routing type (e.g. 'Ext. In', 'No Input', a track name). Optional.
    - input_channel: Input channel (e.g. '1/2', 'All Channels', 'Pre FX'). Optional.
    - output_type: Output routing type (e.g. 'Master', 'Sends Only', a track name). Optional.
    - output_channel: Output channel (e.g. 'Track In'). Optional.

    Use get_track_routing first to see available routing options for the track.
    Useful for setting up side-chain compression, resampling, or routing to
    specific outputs.
    """
    _validate_index(track_index, "track_index")
    params = {"track_index": track_index}
    if input_type is not None:
        params["input_type"] = input_type
    if input_channel is not None:
        params["input_channel"] = input_channel
    if output_type is not None:
        params["output_type"] = output_type
    if output_channel is not None:
        params["output_channel"] = output_channel
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_routing", params)
    changes = [f"{k}={v}" for k, v in result.items() if k not in ("track_index", "track_name")]
    return f"Track {track_index} ('{result.get('track_name', '?')}') routing updated: {', '.join(changes) if changes else 'no changes'}"
@mcp.tool()
@_tool_handler("setting track monitoring")
def set_track_monitoring(ctx: Context, track_index: int, state: int) -> str:
    """Set the monitoring state of a track.

    Parameters:
    - track_index: The index of the track
    - state: 0=IN (always monitor input), 1=AUTO (monitor when armed), 2=OFF (never monitor)

    Controls whether the track passes its input through to the output.
    AUTO is the default and monitors only when the track is armed for recording.
    """
    _validate_index(track_index, "track_index")
    _validate_range(state, "state", 0, 2)
    state_names = {0: "IN", 1: "AUTO", 2: "OFF"}
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_monitoring", {
        "track_index": track_index,
        "state": state,
    })
    state_name = state_names.get(result.get("monitoring_state", state), "unknown")
    return f"Track {track_index} ('{result.get('track_name', '?')}') monitoring set to {state_name}"


@mcp.tool()
@_tool_handler("setting clip launch quantization")
def set_clip_launch_quantization(ctx: Context, track_index: int, clip_index: int,
                                  quantization: int) -> str:
    """Set when a clip starts playing after being triggered.

    Parameters:
    - track_index: The index of the track
    - clip_index: The index of the clip slot
    - quantization: 0=none, 1=8_bars, 2=4_bars, 3=2_bars, 4=bar, 5=half,
      6=half_triplet, 7=quarter, 8=quarter_triplet, 9=eighth, 10=eighth_triplet,
      11=sixteenth, 12=sixteenth_triplet, 13=thirtysecond, 14=global

    Overrides the global launch quantization for this specific clip.
    Use 14 to follow the song's global launch quantization setting.
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    _validate_range(quantization, "quantization", 0, 14)
    quant_names = {
        0: "none", 1: "8 bars", 2: "4 bars", 3: "2 bars", 4: "1 bar",
        5: "1/2", 6: "1/2T", 7: "1/4", 8: "1/4T", 9: "1/8", 10: "1/8T",
        11: "1/16", 12: "1/16T", 13: "1/32", 14: "global",
    }
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_launch_quantization", {
        "track_index": track_index,
        "clip_index": clip_index,
        "quantization": quantization,
    })
    q_name = quant_names.get(result.get("launch_quantization", quantization), "unknown")
    return f"Clip '{result.get('clip_name', '?')}' launch quantization set to {q_name}"
@mcp.tool()
@_tool_handler("setting clip legato")
def set_clip_legato(ctx: Context, track_index: int, clip_index: int,
                     legato: bool) -> str:
    """Enable or disable legato mode for a clip.

    Parameters:
    - track_index: The index of the track
    - clip_index: The index of the clip slot
    - legato: True = clip plays from the position of the previously playing clip
              (seamless transition). False = clip starts from its start position.

    Legato mode is useful for live performance, allowing smooth transitions
    between clips without resetting to the beginning.
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_legato", {
        "track_index": track_index,
        "clip_index": clip_index,
        "legato": legato,
    })
    state = "enabled" if result.get("legato", legato) else "disabled"
    return f"Clip '{result.get('clip_name', '?')}' legato {state}"
@mcp.tool()
@_tool_handler("getting drum pads")
def get_drum_pads(ctx: Context, track_index: int, device_index: int) -> str:
    """Get information about all drum pads in a Drum Rack device.

    Parameters:
    - track_index: The index of the track containing the Drum Rack
    - device_index: The index of the Drum Rack device on the track

    Returns a list of pads with their MIDI note number, name, mute, and solo states.
    Use this to inspect drum pad assignments before modifying them with set_drum_pad.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_drum_pads", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting drum pad")
def set_drum_pad(ctx: Context, track_index: int, device_index: int,
                  note: int, mute: bool = None, solo: bool = None) -> str:
    """Set mute or solo state on a drum pad by MIDI note number.

    Parameters:
    - track_index: The index of the track containing the Drum Rack
    - device_index: The index of the Drum Rack device on the track
    - note: MIDI note number (0-127) identifying the pad (e.g. 36=C1 kick)
    - mute: True to mute the pad, False to unmute. Optional.
    - solo: True to solo the pad, False to unsolo. Optional.

    Use get_drum_pads first to see available pads and their note numbers.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    _validate_range(note, "note", 0, 127)
    params = {"track_index": track_index, "device_index": device_index, "note": note}
    if mute is not None:
        params["mute"] = mute
    if solo is not None:
        params["solo"] = solo
    ableton = get_ableton_connection()
    result = ableton.send_command("set_drum_pad", params)
    return f"Drum pad '{result.get('name', '?')}' (note {note}): mute={result.get('mute')}, solo={result.get('solo')}"
@mcp.tool()
@_tool_handler("copying drum pad")
def copy_drum_pad(ctx: Context, track_index: int, device_index: int,
                   source_note: int, dest_note: int) -> str:
    """Copy the contents of one drum pad to another.

    Parameters:
    - track_index: The index of the track containing the Drum Rack
    - device_index: The index of the Drum Rack device on the track
    - source_note: MIDI note of the pad to copy FROM (0-127)
    - dest_note: MIDI note of the pad to copy TO (0-127)

    Copies the device chain (instrument + effects) from the source pad
    to the destination pad. The destination pad's previous contents are replaced.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    _validate_range(source_note, "source_note", 0, 127)
    _validate_range(dest_note, "dest_note", 0, 127)
    ableton = get_ableton_connection()
    result = ableton.send_command("copy_drum_pad", {
        "track_index": track_index,
        "device_index": device_index,
        "source_note": source_note,
        "dest_note": dest_note,
    })
    return f"Copied drum pad from note {source_note} ('{result.get('source_name', '?')}') to note {dest_note}"
@mcp.tool()
@_tool_handler("getting rack variations")
def get_rack_variations(ctx: Context, track_index: int, device_index: int) -> str:
    """Get variation info for a Rack device (macro snapshots).

    Parameters:
    - track_index: The index of the track containing the Rack
    - device_index: The index of the Rack device

    Returns the number of stored variations, which variation is currently selected,
    and whether the rack has macro mappings. Use with rack_variation_action to
    store, recall, or delete variations.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_rack_variations", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("performing rack variation action")
def rack_variation_action(ctx: Context, track_index: int, device_index: int,
                           action: str, variation_index: int = None) -> str:
    """Perform a variation action on a Rack device (macro snapshots).

    Parameters:
    - track_index: The index of the track containing the Rack
    - device_index: The index of the Rack device
    - action: One of 'store' (save current macros as new variation),
              'recall' (load a stored variation), 'delete' (remove a variation),
              'randomize' (randomize all macro values)
    - variation_index: Required for 'recall' and 'delete'. The 0-based variation index.

    Use get_rack_variations first to see how many variations exist.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if action not in ("store", "recall", "delete", "randomize"):
        raise ValueError("action must be 'store', 'recall', 'delete', or 'randomize'")
    if action in ("recall", "delete") and variation_index is None:
        raise ValueError(f"variation_index is required for '{action}'")
    params = {
        "track_index": track_index,
        "device_index": device_index,
        "action": action,
    }
    if variation_index is not None:
        params["variation_index"] = variation_index
    ableton = get_ableton_connection()
    result = ableton.send_command("rack_variation_action", params)
    device_name = result.get("device_name", "?")
    if action == "store":
        return f"Stored new variation on '{device_name}' (now {result.get('variation_count', '?')} variations)"
    elif action == "recall":
        return f"Recalled variation {variation_index} on '{device_name}'"
    elif action == "delete":
        return f"Deleted variation {variation_index} from '{device_name}' ({result.get('variation_count', '?')} remaining)"
    else:
        return f"Randomized macros on '{device_name}'"
## get_groove_pool — defined in Phase 8 (M4L Bridge) above


@mcp.tool()
@_tool_handler("setting groove settings")
def set_groove_settings(ctx: Context,
                         groove_amount: float = None,
                         groove_index: int = None,
                         timing_amount: float = None,
                         quantization_amount: float = None,
                         random_amount: float = None,
                         velocity_amount: float = None) -> str:
    """Set global groove amount or individual groove parameters.

    Parameters:
    - groove_amount: Global groove intensity (0.0 to 1.0). Optional.
    - groove_index: Index of the groove to modify (from get_groove_pool). Optional.
    - timing_amount: Groove timing influence (0.0 to 1.0). Requires groove_index.
    - quantization_amount: Groove quantization amount (0.0 to 1.0). Requires groove_index.
    - random_amount: Groove random timing variation (0.0 to 1.0). Requires groove_index.
    - velocity_amount: Groove velocity influence (0.0 to 1.0). Requires groove_index.

    Set groove_amount alone to change the global groove intensity, or specify
    groove_index with one or more individual parameters to modify a specific groove.
    """
    params = {}
    if groove_amount is not None:
        _validate_range(groove_amount, "groove_amount", 0.0, 1.0)
        params["groove_amount"] = groove_amount
    if groove_index is not None:
        _validate_index(groove_index, "groove_index")
        params["groove_index"] = groove_index
    if timing_amount is not None:
        _validate_range(timing_amount, "timing_amount", 0.0, 1.0)
        params["timing_amount"] = timing_amount
    if quantization_amount is not None:
        _validate_range(quantization_amount, "quantization_amount", 0.0, 1.0)
        params["quantization_amount"] = quantization_amount
    if random_amount is not None:
        _validate_range(random_amount, "random_amount", 0.0, 1.0)
        params["random_amount"] = random_amount
    if velocity_amount is not None:
        _validate_range(velocity_amount, "velocity_amount", 0.0, 1.0)
        params["velocity_amount"] = velocity_amount
    if not params:
        return "No parameters specified. Provide groove_amount or groove_index with params."
    ableton = get_ableton_connection()
    result = ableton.send_command("set_groove_settings", params)
    parts = []
    if "groove_amount" in result:
        parts.append(f"Global groove amount: {result['groove_amount']}")
    if "groove_index" in result:
        parts.append(f"Groove {result['groove_index']} ('{result.get('groove_name', '?')}'): "
                     f"timing={result.get('timing_amount', '?')}, "
                     f"quantize={result.get('quantization_amount', '?')}, "
                     f"random={result.get('random_amount', '?')}, "
                     f"velocity={result.get('velocity_amount', '?')}")
    return " | ".join(parts)
@mcp.tool()
@_tool_handler("converting audio to MIDI")
def audio_to_midi(ctx: Context, track_index: int, clip_index: int,
                   conversion_type: str) -> str:
    """Convert an audio clip to a MIDI clip using Ableton's audio-to-MIDI algorithms.

    Parameters:
    - track_index: The index of the track containing the audio clip
    - clip_index: The index of the clip slot containing the audio clip
    - conversion_type: 'drums' (percussive audio to drum MIDI),
                       'harmony' (polyphonic audio to chord MIDI),
                       'melody' (monophonic audio to single-note MIDI)

    Creates a new MIDI track with the converted clip. The original audio clip
    is not modified. This is equivalent to right-clicking an audio clip and
    selecting "Convert Drums/Harmony/Melody to New MIDI Track" in Ableton.

    Requires Live 12+.
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    if conversion_type not in ("drums", "harmony", "melody"):
        raise ValueError("conversion_type must be 'drums', 'harmony', or 'melody'")
    ableton = get_ableton_connection()
    result = ableton.send_command("audio_to_midi", {
        "track_index": track_index,
        "clip_index": clip_index,
        "conversion_type": conversion_type,
    }, timeout=30.0)
    return f"Converted audio clip '{result.get('source_clip', '?')}' to MIDI ({conversion_type}). A new MIDI track was created."
@mcp.tool()
@_tool_handler("creating MIDI track with Simpler")
def create_midi_track_with_simpler(ctx: Context, track_index: int, clip_index: int) -> str:
    """Create a new MIDI track with a Simpler instrument loaded with an audio clip's sample.

    Parameters:
    - track_index: The index of the track containing the source audio clip
    - clip_index: The index of the clip slot containing the audio clip

    Creates a new MIDI track with a Simpler device that has the audio clip's
    sample loaded. You can then play the sample chromatically via MIDI.

    Requires Live 12+.
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("create_midi_track_with_simpler", {
        "track_index": track_index,
        "clip_index": clip_index,
    }, timeout=20.0)
    return f"Created MIDI track with Simpler from audio clip '{result.get('source_clip', '?')}'"


@mcp.tool()
@_tool_handler("converting Simpler to Drum Rack")
def sliced_simpler_to_drum_rack(ctx: Context, track_index: int, device_index: int) -> str:
    """Convert a sliced Simpler device into a Drum Rack.

    Parameters:
    - track_index: The index of the track containing the Simpler
    - device_index: The index of the Simpler device on the track

    The Simpler must be in Slicing mode (not Classic or One-Shot).
    Each slice becomes a separate pad in the Drum Rack, allowing
    independent processing and effects per slice.

    Requires Live 12+.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("sliced_simpler_to_drum_rack", {
        "track_index": track_index,
        "device_index": device_index,
    }, timeout=20.0)
    return f"Converted Simpler '{result.get('source_device', '?')}' to Drum Rack"


@mcp.tool()
@_tool_handler("getting compressor sidechain")
def get_compressor_sidechain(ctx: Context, track_index: int, device_index: int) -> str:
    """Get side-chain routing info for a Compressor device.

    Parameters:
    - track_index: The index of the track containing the Compressor
    - device_index: The index of the Compressor device on the track

    Returns the current side-chain input routing type and channel, plus lists
    of all available input routing options. The device must be a Compressor.
    Use this before set_compressor_sidechain to see available routing options.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_compressor_sidechain", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting compressor sidechain")
def set_compressor_sidechain(ctx: Context, track_index: int, device_index: int,
                              input_type: str = None, input_channel: str = None) -> str:
    """Set side-chain routing on a Compressor device by display name.

    Parameters:
    - track_index: The index of the track containing the Compressor
    - device_index: The index of the Compressor device on the track
    - input_type: Side-chain source type display name (e.g. a track name, 'Ext. In'). Optional.
    - input_channel: Side-chain source channel display name (e.g. 'Post FX', 'Pre FX'). Optional.

    The device must be a Compressor. Use get_compressor_sidechain first to see
    available routing options. At least one of input_type or input_channel should be provided.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    params = {"track_index": track_index, "device_index": device_index}
    if input_type is not None:
        params["input_type"] = input_type
    if input_channel is not None:
        params["input_channel"] = input_channel
    ableton = get_ableton_connection()
    result = ableton.send_command("set_compressor_sidechain", params)
    changes = [f"{k}={v}" for k, v in result.items()
               if k not in ("track_index", "device_index", "device_name")]
    device_name = result.get("device_name", "?")
    return f"Compressor '{device_name}' sidechain updated: {', '.join(changes) if changes else 'no changes'}"
@mcp.tool()
@_tool_handler("getting EQ8 properties")
def get_eq8_properties(ctx: Context, track_index: int, device_index: int) -> str:
    """Get EQ Eight-specific properties beyond standard device parameters.

    Parameters:
    - track_index: The index of the track containing the EQ Eight
    - device_index: The index of the EQ Eight device on the track

    Returns edit_mode (0=A curve, 1=B curve), global_mode (0=Stereo, 1=L/R, 2=M/S),
    oversample (boolean), and selected_band (0-7). The device must be an EQ Eight.
    Use get_device_parameters for the standard EQ band parameters (frequency, gain, Q, etc.).
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_eq8_properties", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting EQ8 properties")
def set_eq8_properties(ctx: Context, track_index: int, device_index: int,
                        edit_mode: int = None, global_mode: int = None,
                        oversample: bool = None, selected_band: int = None) -> str:
    """Set EQ Eight-specific properties.

    Parameters:
    - track_index: The index of the track containing the EQ Eight
    - device_index: The index of the EQ Eight device on the track
    - edit_mode: 0 for curve A, 1 for curve B. Optional.
    - global_mode: 0 for Stereo, 1 for Left/Right, 2 for Mid/Side. Optional.
    - oversample: True to enable oversampling, False to disable. Optional.
    - selected_band: Select an EQ band (0-7) for editing. Optional.

    The device must be an EQ Eight. Set any combination of properties in a single call.
    Use get_device_parameters + set_device_parameter for the standard band parameters
    (frequency, gain, Q, type, etc.).
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    params = {"track_index": track_index, "device_index": device_index}
    if edit_mode is not None:
        _validate_range(edit_mode, "edit_mode", 0, 1)
        params["edit_mode"] = edit_mode
    if global_mode is not None:
        _validate_range(global_mode, "global_mode", 0, 2)
        params["global_mode"] = global_mode
    if oversample is not None:
        params["oversample"] = oversample
    if selected_band is not None:
        _validate_range(selected_band, "selected_band", 0, 7)
        params["selected_band"] = selected_band
    ableton = get_ableton_connection()
    result = ableton.send_command("set_eq8_properties", params)
    device_name = result.get("device_name", "?")
    changes = [f"{k}={v}" for k, v in result.items()
               if k not in ("track_index", "device_index", "device_name")]
    return f"EQ Eight '{device_name}' updated: {', '.join(changes) if changes else 'no changes'}"
@mcp.tool()
@_tool_handler("getting Hybrid Reverb IR")
def get_hybrid_reverb_ir(ctx: Context, track_index: int, device_index: int) -> str:
    """Get impulse response (IR) configuration from a Hybrid Reverb device.

    Parameters:
    - track_index: The index of the track containing the Hybrid Reverb
    - device_index: The index of the Hybrid Reverb device on the track

    Returns the list of IR categories and files, the currently selected category
    and file indices, and time shaping parameters (attack_time, decay_time,
    size_factor, time_shaping_on). The device must be a Hybrid Reverb.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_hybrid_reverb_ir", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting Hybrid Reverb IR")
def set_hybrid_reverb_ir(ctx: Context, track_index: int, device_index: int,
                          ir_category_index: int = None, ir_file_index: int = None,
                          ir_attack_time: float = None, ir_decay_time: float = None,
                          ir_size_factor: float = None, ir_time_shaping_on: bool = None) -> str:
    """Set impulse response (IR) configuration on a Hybrid Reverb device.

    Parameters:
    - track_index: The index of the track containing the Hybrid Reverb
    - device_index: The index of the Hybrid Reverb device on the track
    - ir_category_index: Index into ir_category_list to select an IR category. Optional.
    - ir_file_index: Index into ir_file_list to select an IR file within the current category. Optional.
    - ir_attack_time: IR attack time (float). Optional.
    - ir_decay_time: IR decay time (float). Optional.
    - ir_size_factor: IR size scaling factor (float). Optional.
    - ir_time_shaping_on: True to enable time shaping, False to disable. Optional.

    The device must be a Hybrid Reverb. Use get_hybrid_reverb_ir first to see available
    categories and files. When changing both category and file, set them in the same call
    — the category is applied first, then the file index within the new category.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    params = {"track_index": track_index, "device_index": device_index}
    if ir_category_index is not None:
        _validate_index(ir_category_index, "ir_category_index")
        params["ir_category_index"] = ir_category_index
    if ir_file_index is not None:
        _validate_index(ir_file_index, "ir_file_index")
        params["ir_file_index"] = ir_file_index
    if ir_attack_time is not None:
        params["ir_attack_time"] = ir_attack_time
    if ir_decay_time is not None:
        params["ir_decay_time"] = ir_decay_time
    if ir_size_factor is not None:
        params["ir_size_factor"] = ir_size_factor
    if ir_time_shaping_on is not None:
        params["ir_time_shaping_on"] = ir_time_shaping_on
    ableton = get_ableton_connection()
    result = ableton.send_command("set_hybrid_reverb_ir", params)
    device_name = result.get("device_name", "?")
    changes = [f"{k}={v}" for k, v in result.items()
               if k not in ("track_index", "device_index", "device_name")]
    return f"Hybrid Reverb '{device_name}' IR updated: {', '.join(changes) if changes else 'no changes'}"
# --- Song Settings & Navigation ---


@mcp.tool()
@_tool_handler("getting song settings")
def get_song_settings(ctx: Context) -> str:
    """Get global song settings: time signature, swing amount, clip trigger quantization,
    MIDI recording quantization, arrangement overdub, back to arranger, follow song, and draw mode.
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("get_song_settings", {})
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting song settings")
def set_song_settings(ctx: Context,
                       signature_numerator: int = None,
                       signature_denominator: int = None,
                       swing_amount: float = None,
                       clip_trigger_quantization: int = None,
                       midi_recording_quantization: int = None,
                       back_to_arranger: bool = None,
                       follow_song: bool = None,
                       draw_mode: bool = None,
                       session_automation_record: bool = None) -> str:
    """Set global song settings. All parameters are optional — only specified values are changed.

    Parameters:
    - signature_numerator: Time signature numerator (1-99, e.g. 3 for 3/4)
    - signature_denominator: Time signature denominator (1, 2, 4, 8, or 16)
    - swing_amount: Global swing amount (0.0-1.0)
    - clip_trigger_quantization: Global clip launch quantization (0=None, 1=8 Bars, 2=4 Bars, 3=2 Bars, 4=1 Bar, 5=1/2, 6=1/2T, 7=1/4, 8=1/4T, 9=1/8, 10=1/8T, 11=1/16, 12=1/16T, 13=1/32)
    - midi_recording_quantization: MIDI input recording quantization (0=None, 1=1/4, 2=1/8, 3=1/8T, 4=1/8+1/8T, 5=1/16, 6=1/16T, 7=1/16+1/16T, 8=1/32)
    - back_to_arranger: If true, triggering a Session clip disables Arrangement playback
    - follow_song: If true, Arrangement view auto-scrolls to follow the play marker
    - draw_mode: If true, enables envelope/note draw mode
    - session_automation_record: If true, enables the Automation Arm button for session recording
    """
    params = {}
    if signature_numerator is not None:
        params["signature_numerator"] = signature_numerator
    if signature_denominator is not None:
        params["signature_denominator"] = signature_denominator
    if swing_amount is not None:
        _validate_range(swing_amount, "swing_amount", 0.0, 1.0)
        params["swing_amount"] = swing_amount
    if clip_trigger_quantization is not None:
        _validate_index(clip_trigger_quantization, "clip_trigger_quantization")
        params["clip_trigger_quantization"] = clip_trigger_quantization
    if midi_recording_quantization is not None:
        _validate_index(midi_recording_quantization, "midi_recording_quantization")
        params["midi_recording_quantization"] = midi_recording_quantization
    if back_to_arranger is not None:
        params["back_to_arranger"] = back_to_arranger
    if follow_song is not None:
        params["follow_song"] = follow_song
    if draw_mode is not None:
        params["draw_mode"] = draw_mode
    if session_automation_record is not None:
        params["session_automation_record"] = session_automation_record
    if not params:
        return "No parameters specified. Provide at least one setting to change."
    ableton = get_ableton_connection()
    result = ableton.send_command("set_song_settings", params)
    changes = [f"{k}={v}" for k, v in result.items()]
    return f"Song settings updated: {', '.join(changes)}"

# ======================================================================
# Scale & Root Note
# ======================================================================

@mcp.tool()
@_tool_handler("getting song scale")
def get_song_scale(ctx: Context) -> str:
    """Get the song's current scale settings: root note (0-11, C=0), scale name,
    scale mode (on/off), and scale intervals. Essential for harmonically-aware
    MIDI generation and chord suggestions."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_song_scale", {})
    return json.dumps(result)

@mcp.tool()
@_tool_handler("setting song scale")
def set_song_scale(ctx: Context,
                    root_note: int = None,
                    scale_name: str = None,
                    scale_mode: bool = None) -> str:
    """Set the song's scale settings for harmonic awareness.

    Parameters:
    - root_note: Root note 0-11 (C=0, C#=1, D=2, D#=3, E=4, F=5, F#=6, G=7, G#=8, A=9, A#=10, B=11)
    - scale_name: Scale name as shown in Live (e.g. 'Major', 'Minor', 'Dorian', 'Mixolydian', 'Phrygian', 'Lydian', 'Locrian', 'Whole Tone', 'Diminished', 'Whole-Half', 'Minor Blues', 'Minor Pentatonic', 'Major Pentatonic', 'Harmonic Minor', 'Melodic Minor', 'Chromatic')
    - scale_mode: True to enable Scale Mode (highlights scale notes in MIDI editor)
    """
    params = {}
    if root_note is not None:
        _validate_range(root_note, "root_note", 0, 11)
        params["root_note"] = root_note
    if scale_name is not None:
        params["scale_name"] = scale_name
    if scale_mode is not None:
        params["scale_mode"] = scale_mode
    if not params:
        return "No parameters specified. Provide at least one scale setting."
    ableton = get_ableton_connection()
    result = ableton.send_command("set_song_scale", params)
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    parts = []
    if "root_note" in result:
        parts.append(f"root={note_names[result['root_note']]}")
    if "scale_name" in result:
        parts.append(f"scale={result['scale_name']}")
    if "scale_mode" in result:
        parts.append(f"mode={'on' if result['scale_mode'] else 'off'}")
    return f"Scale updated: {', '.join(parts)}"

# ======================================================================
# Punch In/Out Recording
# ======================================================================

@mcp.tool()
@_tool_handler("setting punch recording")
def set_punch_recording(ctx: Context,
                         punch_in: bool = None,
                         punch_out: bool = None,
                         count_in_duration: int = None) -> str:
    """Control punch in/out recording and count-in settings.

    Parameters:
    - punch_in: Enable/disable punch-in (only record within the loop region)
    - punch_out: Enable/disable punch-out (stop recording at the loop end)
    - count_in_duration: Metronome count-in before recording (0=None, 1=1 Bar, 2=2 Bars, 3=4 Bars). Note: may be read-only in some Live versions.
    """
    params = {}
    if punch_in is not None:
        params["punch_in"] = punch_in
    if punch_out is not None:
        params["punch_out"] = punch_out
    if count_in_duration is not None:
        _validate_range(count_in_duration, "count_in_duration", 0, 3)
        params["count_in_duration"] = count_in_duration
    if not params:
        return "No parameters specified."
    ableton = get_ableton_connection()
    result = ableton.send_command("set_punch", params)
    changes = [f"{k}={v}" for k, v in result.items()]
    return f"Punch recording updated: {', '.join(changes)}"

# ======================================================================
# Selection State
# ======================================================================

@mcp.tool()
@_tool_handler("getting selection state")
def get_selection_state(ctx: Context) -> str:
    """Get what is currently selected in Live's UI: the selected track, scene,
    detail clip, draw mode, and follow song state. Useful for context-aware assistance."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_selection_state", {})
    return json.dumps(result)

# ======================================================================
# Link Sync
# ======================================================================

@mcp.tool()
@_tool_handler("getting Link status")
def get_link_status(ctx: Context) -> str:
    """Get Ableton Link sync status: whether Link is enabled and
    whether start/stop sync is active."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_link_status", {})
    return json.dumps(result)

@mcp.tool()
@_tool_handler("setting Link")
def set_link_enabled(ctx: Context,
                      enabled: bool = None,
                      start_stop_sync: bool = None) -> str:
    """Enable/disable Ableton Link tempo sync and start/stop synchronization.

    Parameters:
    - enabled: True to enable Link, False to disable
    - start_stop_sync: True to enable start/stop sync between Link peers
    """
    params = {}
    if enabled is not None:
        params["enabled"] = enabled
    if start_stop_sync is not None:
        params["start_stop_sync"] = start_stop_sync
    if not params:
        return "No parameters specified."
    ableton = get_ableton_connection()
    result = ableton.send_command("set_link_enabled", params)
    changes = [f"{k}={v}" for k, v in result.items()]
    return f"Link updated: {', '.join(changes)}"

# ======================================================================
# Application View Management
# ======================================================================

@mcp.tool()
@_tool_handler("getting view state")
def get_view_state(ctx: Context) -> str:
    """Get the current state of Live's application views: which views are visible
    (Browser, Arranger, Session, Detail, Detail/Clip, Detail/DeviceChain),
    the focused view, and whether Hot-Swap/browse mode is active."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_view_state", {})
    return json.dumps(result)

@mcp.tool()
@_tool_handler("setting view")
def set_view(ctx: Context,
              action: str,
              view_name: str = "") -> str:
    """Show, hide, or focus a view in Live's UI.

    Parameters:
    - action: 'show', 'hide', 'focus', or 'toggle_browse'
    - view_name: 'Browser', 'Arranger', 'Session', 'Detail', 'Detail/Clip', 'Detail/DeviceChain'
      (not needed for toggle_browse)
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("set_view", {"action": action, "view_name": view_name})
    return f"View {action}: {view_name}" if view_name else f"Browse mode toggled"

@mcp.tool()
@_tool_handler("zooming/scrolling view")
def zoom_scroll_view(ctx: Context,
                      action: str,
                      direction: int,
                      view_name: str,
                      modifier_pressed: bool = False) -> str:
    """Zoom or scroll a view in Live's UI.

    Parameters:
    - action: 'zoom' or 'scroll'
    - direction: 0=up, 1=down, 2=left, 3=right
    - view_name: 'Arranger', 'Session', 'Browser', 'Detail/DeviceChain'
    - modifier_pressed: Modifies behavior (e.g. zoom only selected track height in Arranger)
    """
    _validate_range(direction, "direction", 0, 3)
    ableton = get_ableton_connection()
    result = ableton.send_command("zoom_scroll_view", {
        "action": action, "direction": direction,
        "view_name": view_name, "modifier_pressed": modifier_pressed
    })
    dirs = ["up", "down", "left", "right"]
    return f"View {action} {dirs[direction]}: {view_name}"

# ======================================================================
# Playing Clips
# ======================================================================

@mcp.tool()
@_tool_handler("getting playing clips")
def get_playing_clips(ctx: Context) -> str:
    """Get all currently playing and triggered clips across all tracks.
    Returns track index, clip index, clip name, and status (playing/triggered) for each active clip."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_playing_clips", {})
    return json.dumps(result)

# ======================================================================
# Warp Markers
# ======================================================================

@mcp.tool()
@_tool_handler("getting warp markers")
def get_warp_markers(ctx: Context, track_index: int, clip_index: int) -> str:
    """Get the warp markers of an audio clip. Each marker has a beat_time and sample_time.

    Parameters:
    - track_index: Track containing the audio clip
    - clip_index: Clip slot index
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("get_warp_markers", {
        "track_index": track_index, "clip_index": clip_index
    })
    return json.dumps(result)

@mcp.tool()
@_tool_handler("adding warp marker")
def add_warp_marker(ctx: Context, track_index: int, clip_index: int,
                     beat_time: float, sample_time: float = None) -> str:
    """Add a warp marker to an audio clip for time-stretching control.

    Parameters:
    - track_index: Track containing the audio clip
    - clip_index: Clip slot index
    - beat_time: Beat position for the warp marker
    - sample_time: Sample position (optional, auto-calculated by Live if omitted)
    """
    params = {"track_index": track_index, "clip_index": clip_index, "beat_time": beat_time}
    if sample_time is not None:
        params["sample_time"] = sample_time
    ableton = get_ableton_connection()
    result = ableton.send_command("add_warp_marker", params)
    return f"Warp marker added at beat {beat_time}"

@mcp.tool()
@_tool_handler("moving warp marker")
def move_warp_marker(ctx: Context, track_index: int, clip_index: int,
                      beat_time: float, beat_time_distance: float) -> str:
    """Move a warp marker by a beat-time distance.

    Parameters:
    - track_index: Track containing the audio clip
    - clip_index: Clip slot index
    - beat_time: Beat position of the warp marker to move
    - beat_time_distance: Amount (in beats) to shift the marker
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("move_warp_marker", {
        "track_index": track_index, "clip_index": clip_index,
        "beat_time": beat_time, "beat_time_distance": beat_time_distance
    })
    return f"Warp marker at beat {beat_time} moved by {beat_time_distance}"

@mcp.tool()
@_tool_handler("removing warp marker")
def remove_warp_marker(ctx: Context, track_index: int, clip_index: int,
                        beat_time: float) -> str:
    """Remove a warp marker from an audio clip by beat position.

    Parameters:
    - track_index: Track containing the audio clip
    - clip_index: Clip slot index
    - beat_time: Beat position of the warp marker to remove
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("remove_warp_marker", {
        "track_index": track_index, "clip_index": clip_index,
        "beat_time": beat_time
    })
    return f"Warp marker at beat {beat_time} removed"

# ======================================================================
# Tuning System
# ======================================================================

@mcp.tool()
@_tool_handler("getting tuning system")
def get_tuning_system(ctx: Context) -> str:
    """Get the current tuning system: name, pseudo-octave in cents,
    reference pitch, and note tunings. Useful for microtonal music."""
    ableton = get_ableton_connection()
    result = ableton.send_command("get_tuning_system", {})
    return json.dumps(result)

# ======================================================================
# Insert Device by Name (Live 12.3+)
# ======================================================================

@mcp.tool()
@_tool_handler("inserting device by name")
def insert_device_by_name(ctx: Context, track_index: int,
                           device_name: str,
                           target_index: int = None) -> str:
    """Insert a native Live device by name into a track's device chain.
    Faster than load_instrument_or_effect but native devices only (not plugins
    or M4L). Available since Live 12.3.

    Parameters:
    - track_index: Track to insert device into
    - device_name: Name as shown in Live's UI (e.g. 'Compressor', 'EQ Eight', 'Reverb', 'Auto Filter')
    - target_index: Position in the device chain (optional, defaults to end)
    """
    params = {"track_index": track_index, "device_name": device_name}
    if target_index is not None:
        params["target_index"] = target_index
    ableton = get_ableton_connection()
    result = ableton.send_command("insert_device", params)
    return f"Device '{device_name}' inserted on track {track_index}"

# ======================================================================
# Looper Device Control
# ======================================================================

@mcp.tool()
@_tool_handler("controlling looper")
def control_looper(ctx: Context, track_index: int, device_index: int,
                    action: str, clip_slot_index: int = None) -> str:
    """Control a Looper device with specialized actions.

    Parameters:
    - track_index: Track containing the Looper
    - device_index: Device index of the Looper
    - action: 'record', 'overdub', 'play', 'stop', 'clear', 'undo',
              'double_speed', 'half_speed', 'double_length', 'half_length',
              'export' (exports to a clip slot, requires clip_slot_index)
    - clip_slot_index: Required for 'export' action — the target clip slot
    """
    params = {"track_index": track_index, "device_index": device_index, "action": action}
    if clip_slot_index is not None:
        params["clip_slot_index"] = clip_slot_index
    ableton = get_ableton_connection()
    result = ableton.send_command("control_looper", params)
    return json.dumps(result)

# ======================================================================
# Take Lanes (Comping)
# ======================================================================

@mcp.tool()
@_tool_handler("getting take lanes")
def get_take_lanes(ctx: Context, track_index: int) -> str:
    """Get take lanes for a track. Take lanes are used for comping in Arrangement View —
    record multiple takes and pick the best parts.

    Parameters:
    - track_index: Track to get take lanes for
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("get_take_lanes", {"track_index": track_index})
    return json.dumps(result)

@mcp.tool()
@_tool_handler("creating take lane")
def create_take_lane(ctx: Context, track_index: int) -> str:
    """Create a new take lane for a track. Used for comping workflows in Arrangement View.

    Parameters:
    - track_index: Track to create the take lane on
    """
    ableton = get_ableton_connection()
    result = ableton.send_command("create_take_lane", {"track_index": track_index})
    return f"Take lane created on track {track_index} (now {result.get('take_lane_count', '?')} lanes)"

@mcp.tool()
@_tool_handler("triggering session record")
def trigger_session_record(ctx: Context, record_length: float = None) -> str:
    """Trigger a new session recording. Optionally specify a fixed bar length
    after which recording stops automatically.

    Parameters:
    - record_length: Optional number of bars to record. If omitted, recording continues until manually stopped.
    """
    params = {}
    if record_length is not None:
        params["record_length"] = record_length
    ableton = get_ableton_connection()
    result = ableton.send_command("trigger_session_record", params)
    if record_length is not None:
        return f"Session recording triggered for {record_length} bars"
    return "Session recording triggered"


@mcp.tool()
@_tool_handler("navigating playback")
def navigate_playback(ctx: Context, action: str, beats: float = None) -> str:
    """Navigate the playback position: jump, scrub, or play selection.

    Parameters:
    - action: 'jump_by' (relative jump, stops playback), 'scrub_by' (relative jump, keeps playing), or 'play_selection' (play the current arrangement selection)
    - beats: Number of beats to jump/scrub (positive=forward, negative=backward). Required for jump_by and scrub_by.
    """
    if action not in ("jump_by", "scrub_by", "play_selection"):
        return "action must be 'jump_by', 'scrub_by', or 'play_selection'"
    params = {"action": action}
    if beats is not None:
        params["beats"] = beats
    ableton = get_ableton_connection()
    result = ableton.send_command("navigate_playback", params)
    pos = result.get("position", "?")
    if action == "play_selection":
        return f"Playing selection (position: {pos})"
    return f"{action} by {beats} beats (position: {pos})"


@mcp.tool()
@_tool_handler("selecting scene")
def select_scene(ctx: Context, scene_index: int) -> str:
    """Select a scene by index in Live's Session view.

    Parameters:
    - scene_index: The index of the scene to select (0-based)
    """
    _validate_index(scene_index, "scene_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("select_scene", {"scene_index": scene_index})
    name = result.get("scene_name", "?")
    return f"Selected scene {scene_index}: '{name}'"


@mcp.tool()
@_tool_handler("selecting track")
def select_track(ctx: Context, track_index: int, track_type: str = "track") -> str:
    """Select a track in Live's Session or Arrangement view.

    Parameters:
    - track_index: The index of the track to select (0-based). Ignored for master.
    - track_type: 'track' (default), 'return', or 'master'
    """
    if track_type not in ("track", "return", "master"):
        return "track_type must be 'track', 'return', or 'master'"
    if track_type != "master":
        _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("select_track", {
        "track_index": track_index,
        "track_type": track_type,
    })
    name = result.get("selected_track", "?")
    return f"Selected {track_type} track: '{name}'"


@mcp.tool()
@_tool_handler("setting detail clip")
def set_detail_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    """Show a clip in Live's Detail view (the bottom panel).

    Parameters:
    - track_index: The track containing the clip
    - clip_index: The clip slot index
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_detail_clip", {
        "track_index": track_index,
        "clip_index": clip_index,
    })
    name = result.get("clip_name", "?")
    return f"Detail view showing clip '{name}' (track {track_index}, slot {clip_index})"


@mcp.tool()
@_tool_handler("getting Transmute properties")
def get_transmute_properties(ctx: Context, track_index: int, device_index: int) -> str:
    """Get Transmute-specific properties: frequency dial mode, pitch mode, mod mode,
    mono/poly mode, MIDI gate mode, polyphony, and pitch bend range.
    Each mode property includes the current index and a list of available options.

    Parameters:
    - track_index: The index of the track containing the Transmute device
    - device_index: The index of the Transmute device on the track
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_transmute_properties", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting Transmute properties")
def set_transmute_properties(ctx: Context, track_index: int, device_index: int,
                              frequency_dial_mode_index: int = None,
                              pitch_mode_index: int = None,
                              mod_mode_index: int = None,
                              mono_poly_index: int = None,
                              midi_gate_index: int = None,
                              polyphony: int = None,
                              pitch_bend_range: int = None) -> str:
    """Set Transmute-specific properties. All parameters are optional — only specified values are changed.

    Parameters:
    - track_index: The index of the track containing the Transmute device
    - device_index: The index of the Transmute device on the track
    - frequency_dial_mode_index: Index into frequency_dial_mode_list
    - pitch_mode_index: Index into pitch_mode_list
    - mod_mode_index: Index into mod_mode_list
    - mono_poly_index: Index into mono_poly_list (0=Mono, 1=Poly typically)
    - midi_gate_index: Index into midi_gate_list
    - polyphony: Number of polyphony voices
    - pitch_bend_range: Pitch bend range in semitones

    Use get_transmute_properties first to see available mode lists and current values.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    params = {"track_index": track_index, "device_index": device_index}
    if frequency_dial_mode_index is not None:
        params["frequency_dial_mode_index"] = frequency_dial_mode_index
    if pitch_mode_index is not None:
        params["pitch_mode_index"] = pitch_mode_index
    if mod_mode_index is not None:
        params["mod_mode_index"] = mod_mode_index
    if mono_poly_index is not None:
        params["mono_poly_index"] = mono_poly_index
    if midi_gate_index is not None:
        params["midi_gate_index"] = midi_gate_index
    if polyphony is not None:
        params["polyphony"] = polyphony
    if pitch_bend_range is not None:
        params["pitch_bend_range"] = pitch_bend_range
    ableton = get_ableton_connection()
    result = ableton.send_command("set_transmute_properties", params)
    device_name = result.get("device_name", "?")
    changes = [f"{k}={v}" for k, v in result.items()
               if k not in ("track_index", "device_index", "device_name")]
    return f"Transmute '{device_name}' updated: {', '.join(changes) if changes else 'no changes'}"
# --- Track Meters & Fold ---


@mcp.tool()
@_tool_handler("getting track meters")
def get_track_meters(ctx: Context, track_index: int = None) -> str:
    """Get live output meter levels and currently playing/fired clip slot info.

    Parameters:
    - track_index: Optional. If provided, returns data for just that track. If omitted, returns all tracks.

    Returns output_meter_left/right (0.0-1.0), playing_slot_index (-1 if none),
    and fired_slot_index (-1 if none).
    """
    params = {}
    if track_index is not None:
        _validate_index(track_index, "track_index")
        params["track_index"] = track_index
    ableton = get_ableton_connection()
    result = ableton.send_command("get_track_meters", params)
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting track fold")
def set_track_fold(ctx: Context, track_index: int, fold_state: bool) -> str:
    """Collapse or expand a group track.

    Parameters:
    - track_index: The index of the group track
    - fold_state: True to collapse (fold), False to expand (unfold)
    """
    _validate_index(track_index, "track_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("set_track_fold", {
        "track_index": track_index,
        "fold_state": fold_state,
    })
    name = result.get("track_name", "?")
    state = "collapsed" if fold_state else "expanded"
    return f"Track '{name}' {state}"


@mcp.tool()
@_tool_handler("setting crossfade assign")
def set_crossfade_assign(ctx: Context, track_index: int, assign: int) -> str:
    """Set A/B crossfade assignment for a track.

    Parameters:
    - track_index: The index of the track
    - assign: 0=NONE (no crossfade), 1=A, 2=B
    """
    _validate_index(track_index, "track_index")
    if assign not in (0, 1, 2):
        return "assign must be 0 (NONE), 1 (A), or 2 (B)"
    ableton = get_ableton_connection()
    result = ableton.send_command("set_crossfade_assign", {
        "track_index": track_index,
        "assign": assign,
    })
    name = result.get("track_name", "?")
    label = result.get("crossfade_assign", "?")
    return f"Track '{name}' crossfade set to {label}"


@mcp.tool()
@_tool_handler("duplicating clip region")
def duplicate_clip_region(ctx: Context, track_index: int, clip_index: int,
                           region_start: float, region_length: float,
                           destination_time: float, pitch: int = -1,
                           transposition_amount: int = 0) -> str:
    """Duplicate notes in a MIDI clip region to another position, with optional transposition.

    Parameters:
    - track_index: Track containing the clip
    - clip_index: The MIDI clip slot index
    - region_start: Start time of the region to duplicate (in beats)
    - region_length: Length of the region to duplicate (in beats)
    - destination_time: Where to place the duplicated notes (in beats)
    - pitch: Only duplicate notes at this MIDI pitch (-1 for all notes). Default: -1
    - transposition_amount: Semitones to transpose the duplicated notes. Default: 0
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("duplicate_clip_region", {
        "track_index": track_index,
        "clip_index": clip_index,
        "region_start": region_start,
        "region_length": region_length,
        "destination_time": destination_time,
        "pitch": pitch,
        "transposition_amount": transposition_amount,
    })
    return f"Duplicated region [{region_start}–{region_start + region_length}] to time {destination_time} (transpose: {transposition_amount} semitones)"
@mcp.tool()
@_tool_handler("moving clip playing position")
def move_clip_playing_pos(ctx: Context, track_index: int, clip_index: int,
                           time: float) -> str:
    """Jump to a position within a currently playing clip.

    Parameters:
    - track_index: Track containing the clip
    - clip_index: The clip slot index
    - time: The time position to jump to within the clip (in beats)
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("move_clip_playing_pos", {
        "track_index": track_index,
        "clip_index": clip_index,
        "time": time,
    })
    return f"Moved clip playing position to {time}"
@mcp.tool()
@_tool_handler("setting clip grid")
def set_clip_grid(ctx: Context, track_index: int, clip_index: int,
                   grid_quantization: int = None, grid_is_triplet: bool = None) -> str:
    """Set the MIDI editor grid resolution for a clip.

    Parameters:
    - track_index: Track containing the clip
    - clip_index: The clip slot index
    - grid_quantization: Grid resolution enum value. Optional.
    - grid_is_triplet: True for triplet grid, False for standard. Optional.
    """
    _validate_index(track_index, "track_index")
    _validate_index(clip_index, "clip_index")
    params = {"track_index": track_index, "clip_index": clip_index}
    if grid_quantization is not None:
        params["grid_quantization"] = grid_quantization
    if grid_is_triplet is not None:
        params["grid_is_triplet"] = grid_is_triplet
    if len(params) == 2:
        return "No parameters specified. Provide grid_quantization and/or grid_is_triplet."
    ableton = get_ableton_connection()
    result = ableton.send_command("set_clip_grid", params)
    changes = [f"{k}={v}" for k, v in result.items()
               if k not in ("track_index", "clip_index")]
    return f"Clip grid updated: {', '.join(changes)}"
# --- Simpler / Sample ---


@mcp.tool()
@_tool_handler("getting Simpler properties")
def get_simpler_properties(ctx: Context, track_index: int, device_index: int) -> str:
    """Get Simpler device and sample properties: playback mode, voices, retrigger,
    sample markers, gain, warp settings, slicing config, and all warp engine parameters.

    Parameters:
    - track_index: The index of the track containing the Simpler
    - device_index: The index of the Simpler device on the track
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    ableton = get_ableton_connection()
    result = ableton.send_command("get_simpler_properties", {
        "track_index": track_index,
        "device_index": device_index,
    })
    return json.dumps(result)


@mcp.tool()
@_tool_handler("setting Simpler properties")
def set_simpler_properties(ctx: Context, track_index: int, device_index: int,
                            playback_mode: int = None, voices: int = None,
                            retrigger: bool = None, slicing_playback_mode: int = None,
                            start_marker: int = None, end_marker: int = None,
                            gain: float = None, warp_mode: int = None,
                            warping: bool = None, slicing_style: int = None,
                            slicing_sensitivity: float = None,
                            slicing_beat_division: int = None,
                            beats_granulation_resolution: int = None,
                            beats_transient_envelope: float = None,
                            beats_transient_loop_mode: int = None,
                            complex_pro_formants: float = None,
                            complex_pro_envelope: float = None,
                            texture_grain_size: float = None,
                            texture_flux: float = None,
                            tones_grain_size: float = None) -> str:
    """Set Simpler device and sample properties. All parameters are optional.

    Parameters:
    - track_index, device_index: Identify the Simpler device
    - playback_mode: 0=Classic, 1=One-Shot, 2=Slicing
    - voices: Number of polyphony voices
    - retrigger: True/False for retrigger mode
    - slicing_playback_mode: 0=Mono, 1=Poly, 2=Thru
    - start_marker, end_marker: Sample start/end in sample time
    - gain: Sample gain
    - warp_mode: Warp mode index
    - warping: True/False to enable warping
    - slicing_style: 0=Transient, 1=Beat, 2=Region, 3=Manual
    - slicing_sensitivity: 0.0-1.0 sensitivity for auto-slicing
    - slicing_beat_division: Beat division index for beat slicing
    - beats_granulation_resolution, beats_transient_envelope, beats_transient_loop_mode: Beats warp params
    - complex_pro_formants, complex_pro_envelope: Complex Pro warp params
    - texture_grain_size, texture_flux: Texture warp params
    - tones_grain_size: Tones warp param

    Use get_simpler_properties first to see current values and available options.
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    params = {"track_index": track_index, "device_index": device_index}
    local_vars = {
        "playback_mode": playback_mode, "voices": voices, "retrigger": retrigger,
        "slicing_playback_mode": slicing_playback_mode,
        "start_marker": start_marker, "end_marker": end_marker, "gain": gain,
        "warp_mode": warp_mode, "warping": warping,
        "slicing_style": slicing_style, "slicing_sensitivity": slicing_sensitivity,
        "slicing_beat_division": slicing_beat_division,
        "beats_granulation_resolution": beats_granulation_resolution,
        "beats_transient_envelope": beats_transient_envelope,
        "beats_transient_loop_mode": beats_transient_loop_mode,
        "complex_pro_formants": complex_pro_formants,
        "complex_pro_envelope": complex_pro_envelope,
        "texture_grain_size": texture_grain_size, "texture_flux": texture_flux,
        "tones_grain_size": tones_grain_size,
    }
    for k, v in local_vars.items():
        if v is not None:
            params[k] = v
    ableton = get_ableton_connection()
    result = ableton.send_command("set_simpler_properties", params)
    device_name = result.get("device_name", "?")
    changes = [f"{k}={v}" for k, v in result.items()
               if k not in ("track_index", "device_index", "device_name")]
    return f"Simpler '{device_name}' updated: {', '.join(changes) if changes else 'no changes'}"
@mcp.tool()
@_tool_handler("performing Simpler action")
def simpler_sample_action(ctx: Context, track_index: int, device_index: int,
                           action: str, beats: float = None) -> str:
    """Perform an action on a Simpler device's loaded sample.

    Parameters:
    - track_index: The track containing the Simpler
    - device_index: The Simpler device index
    - action: 'reverse' (reverse the sample), 'crop' (crop to start/end markers),
              'warp_as' (warp sample to specified beat count), 'warp_double' (double the warp length),
              'warp_half' (halve the warp length)
    - beats: Required for 'warp_as' — number of beats to warp the sample to
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if action not in ("reverse", "crop", "warp_as", "warp_double", "warp_half"):
        return "action must be 'reverse', 'crop', 'warp_as', 'warp_double', or 'warp_half'"
    params = {"track_index": track_index, "device_index": device_index, "action": action}
    if beats is not None:
        params["beats"] = beats
    ableton = get_ableton_connection()
    result = ableton.send_command("simpler_sample_action", params)
    device_name = result.get("device_name", "?")
    return f"Simpler '{device_name}': {action} completed"
@mcp.tool()
@_tool_handler("managing sample slices")
def manage_sample_slices(ctx: Context, track_index: int, device_index: int,
                          action: str, slice_time: int = None,
                          new_time: int = None) -> str:
    """Manage slice points on a Simpler device's sample.

    Parameters:
    - track_index: The track containing the Simpler
    - device_index: The Simpler device index
    - action: 'insert' (add a slice at slice_time), 'move' (move slice from slice_time to new_time),
              'remove' (remove slice at slice_time), 'clear' (remove all slices), 'reset' (reset to default slices)
    - slice_time: Required for insert, move, remove — the slice time position in sample time
    - new_time: Required for move — the destination time position
    """
    _validate_index(track_index, "track_index")
    _validate_index(device_index, "device_index")
    if action not in ("insert", "move", "remove", "clear", "reset"):
        return "action must be 'insert', 'move', 'remove', 'clear', or 'reset'"
    params = {"track_index": track_index, "device_index": device_index, "action": action}
    if slice_time is not None:
        params["slice_time"] = slice_time
    if new_time is not None:
        params["new_time"] = new_time
    ableton = get_ableton_connection()
    result = ableton.send_command("manage_sample_slices", params)
    device_name = result.get("device_name", "?")
    count = result.get("slice_count", "?")
    return f"Simpler '{device_name}': {action} done ({count} slices)"
# --- Browser Preview ---


@mcp.tool()
@_tool_handler("previewing browser item")
def preview_browser_item(ctx: Context, uri: str = None, action: str = "preview") -> str:
    """Preview (audition) a browser item before loading it, or stop the current preview.

    Parameters:
    - uri: The URI of the browser item to preview (required for 'preview' action).
           Use search_browser or get_browser_tree to find URIs.
    - action: 'preview' to start previewing, 'stop' to stop the current preview. Default: 'preview'
    """
    if action not in ("preview", "stop"):
        return "action must be 'preview' or 'stop'"
    params = {"action": action}
    if uri is not None:
        params["uri"] = uri
    ableton = get_ableton_connection()
    result = ableton.send_command("preview_browser_item", params)
    if action == "stop":
        return "Preview stopped"
    name = result.get("name", "?")
    return f"Previewing: '{name}'"
def main():
    """Run the MCP server"""
    mcp.run()

if __name__ == "__main__":
    main()