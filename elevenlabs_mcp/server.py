"""
ElevenLabs MCP Server

⚠️ IMPORTANT: This server provides access to ElevenLabs API endpoints which may incur costs.
Each tool that makes an API call is marked with a cost warning. Please follow these guidelines:

1. Only use tools when explicitly requested by the user
2. For tools that generate audio, consider the length of the text as it affects costs
3. Some operations like voice cloning or text-to-voice may have higher costs

Tools without cost warnings in their description are free to use as they only read existing data.
"""

import functools
import httpx
import logging
import os
import re
import base64
from datetime import datetime
from io import BytesIO
import pathlib
from typing import Literal, List
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from elevenlabs.client import ElevenLabs
from elevenlabs_mcp.model import McpVoice
from elevenlabs_mcp.utils import (
    ElevenLabsMcpError,
    make_error,
    make_output_path,
    make_output_file,
    handle_input_file,
)
from elevenlabs_mcp.convai import create_conversation_config, create_platform_settings
from elevenlabs.types.knowledge_base_locator import KnowledgeBaseLocator

from elevenlabs.play import play
from elevenlabs_mcp import __version__

logger = logging.getLogger("ElevenLabs-MCP")

if load_dotenv is not None:
    try:
        load_dotenv()
    except Exception as e:
        logger.debug("load_dotenv failed: %s", e)
base_path = os.getenv("ELEVENLABS_MCP_BASE_PATH")
DEFAULT_VOICE_ID = "dPEieVXDPKaDPRG5YA6R"

# Default output directory - user configurable
DEFAULT_OUTPUT_DIR = os.getenv(
    "ELEVENLABS_OUTPUT_DIR",
    os.path.join(pathlib.Path.home(), "Documents", "Ableton", "User Library", "eleven_labs_audio")
)

# Lazy client initialization — only created when a tool is actually called
_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            make_error(
                "ELEVENLABS_API_KEY environment variable is required. "
                "Set it in your .env file or system environment."
            )
        custom = httpx.Client(
            headers={"User-Agent": f"ElevenLabs-MCP/{__version__}"},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        import atexit
        atexit.register(lambda: custom.close())
        _client = ElevenLabs(api_key=api_key, httpx_client=custom)
    return _client


def _safe_api(fn):
    """Decorator that catches raw ElevenLabs/httpx exceptions and re-raises
    them as ``ElevenLabsMcpError`` with actionable context, preventing internal
    stack traces from leaking to the client.  Intentional ``ElevenLabsMcpError``
    raises (via ``make_error()``) pass through unchanged."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ElevenLabsMcpError:
            raise  # intentional validation / business errors — pass through
        except httpx.TimeoutException:
            make_error("ElevenLabs API request timed out — please try again")
        except httpx.HTTPStatusError as exc:
            make_error("ElevenLabs API error (HTTP {0}): {1}".format(
                exc.response.status_code, exc.response.text[:200]))
        except Exception as exc:
            logger.exception("Unexpected error in %s", fn.__name__)
            make_error("ElevenLabs API call failed: {0}".format(str(exc)[:200]))
    return wrapper


mcp = FastMCP("ElevenLabs")


@mcp.tool(
    description="""Convert text to speech with a given voice and save the output audio file to a given directory.
    Only one of voice_id or voice_name can be provided. If none are provided, the default voice will be used.
    For importing audio files into an Ableton session, pass "query:UserLibrary#eleven_labs_audio:filename.mp3" on "uri" parameter for the "import_audio_file" Ableton MCP tool.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs.
    """
)
@_safe_api
def text_to_speech(
    text: str,
    voice_name: str = None,
    output_directory: str = DEFAULT_OUTPUT_DIR,
    voice_id: str = None,
    stability: float = 0.45,
    similarity_boost: float = 0.75,
    style: float = 0.45,
    use_speaker_boost: bool = True,
    speed: float = 1.0,
) -> TextContent:
    if not text:
        make_error("Text is required.")
    if voice_id and voice_name:
        make_error("voice_id and voice_name cannot both be provided.")

    voice = None
    if voice_id:
        voice = _get_client().voices.get(voice_id=voice_id)
    elif voice_name:
        voices = _get_client().voices.search(search=voice_name)
        if not voices.voices:
            make_error("No voices found with that name.")
        voice = next((v for v in voices.voices if voice_name.lower() in v.name.lower()), None)
        if not voice:
            make_error(f"Voice with name: {voice_name} does not exist.")

    chosen_voice_id = voice.voice_id if voice else DEFAULT_VOICE_ID
    output_path = make_output_path(output_directory, base_path)
    output_file = make_output_file("tts", text, output_path, "mp3")

    audio_data = _get_client().text_to_speech.convert(
        text=text,
        voice_id=chosen_voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
            "speed": speed,
        },
    )
    with open(output_file, "wb") as f:
        for chunk in audio_data:
            f.write(chunk)

    logger.info("text_to_speech: voice=%s chars=%d", chosen_voice_id, len(text))
    return TextContent(
        type="text",
        text=f"Success. File saved as: {output_file}. Voice used: {voice.name if voice else DEFAULT_VOICE_ID}",
    )


@mcp.tool(
    description="""Transcribe speech from an audio file and either save the output text file to a given directory or return the text to the client directly.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        file_path: Path to the audio file to transcribe
        language_code: ISO 639-3 language code for transcription (default: "eng" for English)
        diarize: Whether to diarize the audio file. If True, which speaker is currently speaking will be annotated in the transcription.
        save_transcript_to_file: Whether to save the transcript to a file.
        return_transcript_to_client_directly: Whether to return the transcript to the client directly.
        output_directory: Directory where files should be saved.
            Defaults to $HOME/Desktop if not provided.

    Returns:
        TextContent containing the transcription. If save_transcript_to_file is True, the transcription will be saved to a file in the output directory.
    """
)
@_safe_api
def speech_to_text(
    input_file_path: str,
    language_code: str = "eng",
    diarize: bool = False,
    save_transcript_to_file: bool = True,
    return_transcript_to_client_directly: bool = False,
    output_directory: str = None,
) -> TextContent:
    if not save_transcript_to_file and not return_transcript_to_client_directly:
        make_error("Must save transcript to file or return it to the client directly.")
    file_path = handle_input_file(input_file_path)
    if save_transcript_to_file:
        output_path = make_output_path(output_directory, base_path)
        output_file = make_output_file("stt", file_path.name, output_path, "txt")
    with file_path.open("rb") as f:
        audio_bytes = f.read()
    transcription = _get_client().speech_to_text.convert(
        model_id="scribe_v1",
        file=audio_bytes,
        language_code=language_code,
        enable_logging=False,
        diarize=diarize,
        tag_audio_events=True,
    )

    if save_transcript_to_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(transcription.text)

    if return_transcript_to_client_directly:
        return TextContent(type="text", text=transcription.text)
    else:
        return TextContent(
            type="text", text=f"Transcription saved to {output_file}"
        )


@mcp.tool(
    description="""Convert text description of a sound effect to sound effect with a given duration and save the output audio file to a given directory.
    Directory is optional, if not provided, the output file will be saved to $HOME/Desktop.
    Duration must be between 0.5 and 5 seconds.
    For importing audio files into an Ableton session, pass "query:UserLibrary#eleven_labs_audio:filename.mp3" on "uri" parameter for the "import_audio_file" Ableton MCP tool.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        text: Text description of the sound effect
        duration_seconds: Duration of the sound effect in seconds
        output_directory: Directory where files should be saved.
            Defaults to $HOME/Desktop if not provided.
    """
)
@_safe_api
def text_to_sound_effects(
    text: str, duration_seconds: float = 2.0, output_directory: str = DEFAULT_OUTPUT_DIR
) -> TextContent:
    if duration_seconds < 0.5 or duration_seconds > 5:
        make_error("Duration must be between 0.5 and 5 seconds")
    output_path = make_output_path(output_directory, base_path)
    output_file = make_output_file("sfx", text, output_path, "mp3")

    audio_data = _get_client().text_to_sound_effects.convert(
        text=text,
        output_format="mp3_44100_128",
        duration_seconds=duration_seconds,
    )
    with open(output_file, "wb") as f:
        for chunk in audio_data:
            f.write(chunk)

    logger.info("text_to_sound_effects: duration=%.1fs", duration_seconds)
    return TextContent(
        type="text",
        text=f"Success. File saved as: {output_file}",
    )


@mcp.tool(
    description="""
    Search for existing voices, a voice that has already been added to the user's ElevenLabs voice library. 
    Searches in name, description, labels and category.

    Args:
        search: Search term to filter voices by. Searches in name, description, labels and category.
        sort: Which field to sort by. `created_at_unix` might not be available for older voices.
        sort_direction: Sort order, either ascending or descending.

    Returns:
        List of voices that match the search criteria.
    """
)
@_safe_api
def search_voices(
    search: str = None,
    sort: Literal["created_at_unix", "name"] = "name",
    sort_direction: Literal["asc", "desc"] = "desc",
) -> list[McpVoice]:
    response = _get_client().voices.search(
        search=search, sort=sort, sort_direction=sort_direction
    )
    return [
        McpVoice(id=voice.voice_id, name=voice.name, category=voice.category)
        for voice in response.voices
    ]


@mcp.tool(description="Get details of a specific voice")
@_safe_api
def get_voice(voice_id: str) -> McpVoice:
    """Get details of a specific voice."""
    response = _get_client().voices.get(voice_id=voice_id)
    fine_tuning = getattr(response, "fine_tuning", None)
    ft_state = getattr(fine_tuning, "state", None) if fine_tuning else None
    return McpVoice(
        id=response.voice_id,
        name=response.name,
        category=response.category,
        fine_tuning_status=ft_state,
    )


@mcp.tool(
    description="""Clone a voice using provided audio files.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
@_safe_api
def voice_clone(
    name: str, files: list[str], description: str = None
) -> TextContent:
    input_files = []
    response = None
    try:
        for file in files:
            input_files.append(open(str(handle_input_file(file).absolute()), "rb"))
        response = _get_client().voices.ivc.create(
            name=name,
            description=description,
            files=input_files,
        )
    finally:
        for f in input_files:
            f.close()
    if response is None:
        make_error("voice_clone: API call did not return a response")
    logger.info("voice_clone: name=%s voice_id=%s", name, response.voice_id)
    return TextContent(
        type="text",
        text=f"Voice cloned successfully: ID: {response.voice_id}",
    )


@mcp.tool(
    description="""Isolate audio from a file and save the output audio file to a given directory.
    Directory is optional, if not provided, the output file will be saved to $HOME/Desktop.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
@_safe_api
def isolate_audio(
    input_file_path: str, output_directory: str = None
) -> TextContent:
    file_path = handle_input_file(input_file_path)
    output_path = make_output_path(output_directory, base_path)
    output_file = make_output_file("iso", file_path.name, output_path, "mp3")
    with file_path.open("rb") as f:
        audio_bytes = f.read()
    audio_data = _get_client().audio_isolation.convert(
        audio=audio_bytes,
    )
    with open(output_file, "wb") as f:
        for chunk in audio_data:
            f.write(chunk)

    logger.info("isolate_audio: output=%s", output_file)
    return TextContent(
        type="text",
        text=f"Success. File saved as: {output_file}",
    )


@mcp.tool(
    description="Check the current subscription status. Could be used to measure the usage of the API."
)
@_safe_api
def check_subscription() -> TextContent:
    subscription = _get_client().user.subscription.get()
    # Return only usage-relevant fields — exclude billing/account metadata
    import json
    safe_fields = {
        "tier": getattr(subscription, "tier", None),
        "character_count": getattr(subscription, "character_count", None),
        "character_limit": getattr(subscription, "character_limit", None),
        "voice_limit": getattr(subscription, "voice_limit", None),
        "can_extend_character_limit": getattr(subscription, "can_extend_character_limit", None),
        "status": getattr(subscription, "status", None),
        "next_character_count_reset_unix": getattr(subscription, "next_character_count_reset_unix", None),
    }
    return TextContent(type="text", text=json.dumps(
        {k: v for k, v in safe_fields.items() if v is not None}, indent=2))


@mcp.tool(
    description="""Create a conversational AI agent with custom configuration.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        name: Name of the agent
        first_message: First message the agent will say i.e. "Hi, how can I help you today?"
        system_prompt: System prompt for the agent
        voice_id: ID of the voice to use for the agent
        language: ISO 639-1 language code for the agent
        llm: LLM to use for the agent
        temperature: Temperature for the agent. The lower the temperature, the more deterministic the agent's responses will be. Range is 0 to 1.
        max_tokens: Maximum number of tokens to generate.
        asr_quality: Quality of the ASR. `high` or `low`.
        model_id: ID of the ElevenLabsmodel to use for the agent.
        optimize_streaming_latency: Optimize streaming latency. Range is 0 to 4.
        stability: Stability for the agent. Range is 0 to 1.
        similarity_boost: Similarity boost for the agent. Range is 0 to 1.
        turn_timeout: Timeout for the agent to respond in seconds. Defaults to 7 seconds.
        max_duration_seconds: Maximum duration of a conversation in seconds. Defaults to 600 seconds (10 minutes).
        record_voice: Whether to record the agent's voice.
        retention_days: Number of days to retain the agent's data.
    """
)
@_safe_api
def create_agent(
    name: str,
    first_message: str,
    system_prompt: str,
    voice_id: str = DEFAULT_VOICE_ID,
    language: str = "en",
    llm: str = "gemini-2.0-flash-001",
    temperature: float = 0.5,
    max_tokens: int = None,
    asr_quality: str = "high",
    model_id: str = "eleven_turbo_v2",
    optimize_streaming_latency: int = 3,
    stability: float = 0.5,
    similarity_boost: float = 0.8,
    turn_timeout: int = 7,
    max_duration_seconds: int = 300,
    record_voice: bool = True,
    retention_days: int = 730,
) -> TextContent:
    conversation_config = create_conversation_config(
        language=language,
        system_prompt=system_prompt,
        llm=llm,
        first_message=first_message,
        temperature=temperature,
        max_tokens=max_tokens,
        asr_quality=asr_quality,
        voice_id=voice_id,
        model_id=model_id,
        optimize_streaming_latency=optimize_streaming_latency,
        stability=stability,
        similarity_boost=similarity_boost,
        turn_timeout=turn_timeout,
        max_duration_seconds=max_duration_seconds,
    )

    platform_settings = create_platform_settings(
        record_voice=record_voice,
        retention_days=retention_days,
    )

    response = _get_client().conversational_ai.agents.create(
        name=name,
        conversation_config=conversation_config,
        platform_settings=platform_settings,
    )

    return TextContent(
        type="text",
        text=f"""Agent created successfully: Name: {name}, Agent ID: {response.agent_id}, System Prompt: {system_prompt}, Voice ID: {voice_id or "Default"}, Language: {language}, LLM: {llm}, You can use this agent ID for future interactions with the agent.""",
    )


@mcp.tool(
    description="""Add a knowledge base to ElevenLabs workspace. Allowed types are epub, pdf, docx, txt, html.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        agent_id: ID of the agent to add the knowledge base to.
        knowledge_base_name: Name of the knowledge base.
        url: URL of the knowledge base.
        input_file_path: Path to the file to add to the knowledge base.
        text: Text to add to the knowledge base.
    """
)
@_safe_api
def add_knowledge_base_to_agent(
    agent_id: str,
    knowledge_base_name: str,
    url: str = None,
    input_file_path: str = None,
    text: str = None,
) -> TextContent:
    provided_params = [
        param for param in [url, input_file_path, text] if param is not None
    ]
    if len(provided_params) == 0:
        make_error("Must provide either a URL, a file, or text")
    if len(provided_params) > 1:
        make_error("Must provide exactly one of: URL, file, or text")

    file = None
    validated_path = None
    if text is not None:
        text_bytes = text.encode("utf-8")
        text_io = BytesIO(text_bytes)
        text_io.name = "text.txt"
        text_io.content_type = "text/plain"
        file = text_io
    elif input_file_path is not None:
        validated_path = handle_input_file(file_path=input_file_path, audio_content_check=False)

    try:
        if validated_path is not None:
            file = open(validated_path, "rb")

        response = _get_client().conversational_ai.add_to_knowledge_base(
            name=knowledge_base_name,
            url=url,
            file=file,
        )

        # --- Attach the newly-created KB to the agent (atomic block) --------
        # If anything below fails the KB document already exists on the server.
        # We perform a compensating delete so the user is not left with an
        # orphaned, unattached knowledge-base document.
        try:
            agent = _get_client().conversational_ai.agents.get(agent_id)
            conv_cfg = getattr(agent, "conversation_config", None)
            agent_cfg = getattr(conv_cfg, "agent", None) if conv_cfg else None
            prompt_cfg = getattr(agent_cfg, "prompt", None) if agent_cfg else None
            if prompt_cfg is None:
                make_error(
                    "Agent {0} has no prompt configuration — cannot attach knowledge base".format(agent_id))
            kb_list = getattr(prompt_cfg, "knowledge_base", None)
            if not isinstance(kb_list, list):
                kb_list = []
                prompt_cfg.knowledge_base = kb_list
            kb_list.append(
                KnowledgeBaseLocator(
                    type="file" if file else "url",
                    name=knowledge_base_name,
                    id=response.id,
                )
            )
            _get_client().conversational_ai.agents.update(
                agent_id, conversation_config=agent.conversation_config
            )
        except Exception:
            # Compensating rollback: delete the orphaned KB document so it
            # does not accumulate on the server.
            try:
                _get_client().conversational_ai.knowledge_base.delete(
                    documentation_id=response.id,
                )
                logger.info(
                    "Rolled back orphaned KB %s after agent-attach failure",
                    response.id,
                )
            except Exception as cleanup_err:
                logger.warning(
                    "Failed to delete orphaned KB %s during rollback: %s",
                    response.id, cleanup_err,
                )
            raise

        return TextContent(
            type="text",
            text=f"""Knowledge base created with ID: {response.id} and added to agent {agent_id} successfully.""",
        )
    finally:
        if validated_path is not None and file is not None:
            file.close()


@mcp.tool(description="List all available conversational AI agents")
@_safe_api
def list_agents() -> TextContent:
    """List all available conversational AI agents.

    Returns:
        TextContent with a formatted list of available agents
    """
    response = _get_client().conversational_ai.agents.list()

    if not response.agents:
        return TextContent(type="text", text="No agents found.")

    agent_list = ",".join(
        f"{agent.name} (ID: {agent.agent_id})" for agent in response.agents
    )

    return TextContent(type="text", text=f"Available agents: {agent_list}")


@mcp.tool(description="Get details about a specific conversational AI agent")
@_safe_api
def get_agent(agent_id: str) -> TextContent:
    """Get details about a specific conversational AI agent.

    Args:
        agent_id: The ID of the agent to retrieve

    Returns:
        TextContent with detailed information about the agent
    """
    response = _get_client().conversational_ai.agents.get(agent_id)

    # Safely traverse nested attributes that may be None
    cfg = getattr(response, "conversation_config", None)
    tts = getattr(cfg, "tts", None) if cfg else None
    voice_info = f"Voice ID: {tts.voice_id}" if tts and getattr(tts, "voice_id", None) else "None"

    metadata = getattr(response, "metadata", None)
    ts = getattr(metadata, "created_at_unix_secs", None) if metadata else None
    created_at = (
        datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        if ts is not None
        else "Unknown"
    )

    return TextContent(
        type="text",
        text=f"Agent Details: Name: {response.name}, Agent ID: {response.agent_id}, Voice Configuration: {voice_info}, Created At: {created_at}",
    )


@mcp.tool(
    description="""Transform audio from one voice to another using provided audio files.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
@_safe_api
def speech_to_speech(
    input_file_path: str,
    voice_name: str = "Adam",
    output_directory: str = None,
) -> TextContent:
    voices = _get_client().voices.search(search=voice_name)

    if len(voices.voices) == 0:
        make_error("No voice found with that name.")

    voice = next((v for v in voices.voices if voice_name.lower() in v.name.lower()), None)

    if voice is None:
        make_error(f"Voice with name: {voice_name} does not exist.")

    file_path = handle_input_file(input_file_path)
    output_path = make_output_path(output_directory, base_path)
    output_file = make_output_file("sts", file_path.name, output_path, "mp3")

    with file_path.open("rb") as f:
        audio_bytes = f.read()

    audio_data = _get_client().speech_to_speech.convert(
        model_id="eleven_english_sts_v2",
        voice_id=voice.voice_id,
        audio=audio_bytes,
    )

    with open(output_file, "wb") as f:
        for chunk in audio_data:
            f.write(chunk)

    logger.info("speech_to_speech: output=%s", output_file)
    return TextContent(
        type="text", text=f"Success. File saved as: {output_file}"
    )


@mcp.tool(
    description="""Create voice previews from a text prompt. Creates three previews with slight variations. Saves the previews to a given directory. If no text is provided, the tool will auto-generate text.

    Voice preview files are saved as: voice_design_(generated_voice_id)_(timestamp).mp3

    Example file name: voice_design_Ya2J5uIa5Pq14DNPsbC1_20250403_164949.mp3

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
@_safe_api
def text_to_voice(
    voice_description: str,
    text: str = None,
    output_directory: str = None,
) -> TextContent:
    if not voice_description or not voice_description.strip():
        make_error("Voice description is required.")

    previews = _get_client().text_to_voice.create_previews(
        voice_description=voice_description,
        text=text,
        auto_generate_text=True if text is None else False,
    )

    output_path = make_output_path(output_directory, base_path)

    generated_voice_ids = []
    output_file_paths = []

    for preview in previews.previews:
        output_file = make_output_file(
            "voice_design", preview.generated_voice_id, output_path, "mp3", full_id=True
        )
        output_file_paths.append(str(output_file))
        generated_voice_ids.append(preview.generated_voice_id)
        audio_bytes = base64.b64decode(preview.audio_base_64)

        with open(output_file, "wb") as f:
            f.write(audio_bytes)

    return TextContent(
        type="text",
        text=f"Success. Files saved at: {', '.join(output_file_paths)}. Generated voice IDs are: {', '.join(generated_voice_ids)}",
    )


@mcp.tool(
    description="""Add a generated voice to the voice library. Uses the voice ID from the `text_to_voice` tool.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.
    """
)
@_safe_api
def create_voice_from_preview(
    generated_voice_id: str,
    voice_name: str,
    voice_description: str,
) -> TextContent:
    voice = _get_client().text_to_voice.create(
        voice_name=voice_name,
        voice_description=voice_description,
        generated_voice_id=generated_voice_id,
    )

    return TextContent(
        type="text",
        text=f"Success. Voice created: {voice.name} with ID:{voice.voice_id}",
    )


@mcp.tool(
    description="""Make an outbound call via Twilio using an ElevenLabs agent.

    ⚠️ COST WARNING: This tool makes an API call to ElevenLabs which may incur costs. Only use when explicitly requested by the user.

    Args:
        agent_id: The ID of the agent that will handle the call
        agent_phone_number_id: The ID of the phone number to use for the call
        to_number: The phone number to call (E.164 format: +1xxxxxxxxxx)

    Returns:
        TextContent containing information about the call
    """
)
@_safe_api
def make_outbound_call(
    agent_id: str,
    agent_phone_number_id: str,
    to_number: str,
) -> TextContent:
    if not re.match(r'^\+[1-9]\d{1,14}$', to_number):
        make_error("to_number must be in E.164 format (e.g. +1xxxxxxxxxx)")

    response = _get_client().conversational_ai.twilio.outbound_call(
        agent_id=agent_id,
        agent_phone_number_id=agent_phone_number_id,
        to_number=to_number,
    )

    logger.info("make_outbound_call: agent=%s to=***%s", agent_id, to_number[-4:])
    return TextContent(type="text", text=f"Outbound call initiated: {response}.")


@mcp.tool(
    description="""Search for a voice across the entire ElevenLabs voice library.

    Args:
        page: Page number to return (0-indexed)
        page_size: Number of voices to return per page (1-100)
        search: Search term to filter voices by
        
    Returns:
        TextContent containing information about the shared voices
    """
)
@_safe_api
def search_voice_library(
    page: int = 0,
    page_size: int = 10,
    search: str = None,
) -> TextContent:
    if page < 0:
        make_error("page must be >= 0")
    if page_size < 1 or page_size > 100:
        make_error("page_size must be between 1 and 100")
    response = _get_client().voices.get_shared(
        page=page,
        page_size=page_size,
        search=search,
    )

    if not response.voices:
        return TextContent(
            type="text", text="No shared voices found with the specified criteria."
        )

    voice_list = []
    for voice in response.voices:
        language_info = "N/A"
        if hasattr(voice, "verified_languages") and voice.verified_languages:
            languages = []
            for lang in voice.verified_languages:
                accent_info = (
                    f" ({lang.accent})"
                    if hasattr(lang, "accent") and lang.accent
                    else ""
                )
                languages.append(f"{lang.language}{accent_info}")
            language_info = ", ".join(languages)

        details = [
            f"Name: {voice.name}",
            f"ID: {voice.voice_id}",
            f"Category: {getattr(voice, 'category', 'N/A')}",
        ]
        if hasattr(voice, "gender") and voice.gender:
            details.append(f"Gender: {voice.gender}")
        if hasattr(voice, "age") and voice.age:
            details.append(f"Age: {voice.age}")
        if hasattr(voice, "accent") and voice.accent:
            details.append(f"Accent: {voice.accent}")
        if hasattr(voice, "description") and voice.description:
            details.append(f"Description: {voice.description}")
        if hasattr(voice, "use_case") and voice.use_case:
            details.append(f"Use Case: {voice.use_case}")

        details.append(f"Languages: {language_info}")

        if hasattr(voice, "preview_url") and voice.preview_url:
            details.append(f"Preview URL: {voice.preview_url}")

        voice_info = "\n".join(details)
        voice_list.append(voice_info)

    formatted_info = "\n\n".join(voice_list)
    return TextContent(type="text", text=f"Shared Voices:\n\n{formatted_info}")


@mcp.tool(description="List all phone numbers associated with the ElevenLabs account")
@_safe_api
def list_phone_numbers() -> TextContent:
    """List all phone numbers associated with the ElevenLabs account.

    Returns:
        TextContent containing formatted information about the phone numbers
    """
    response = _get_client().conversational_ai.phone_numbers.list()

    if not response:
        return TextContent(type="text", text="No phone numbers found.")

    phone_info = []
    for phone in response:
        assigned_agent = "None"
        if phone.assigned_agent:
            assigned_agent = f"{phone.assigned_agent.agent_name} (ID: {phone.assigned_agent.agent_id})"

        phone_info.append(
            f"Phone Number: {phone.phone_number}\n"
            f"ID: {phone.phone_number_id}\n"
            f"Provider: {phone.provider}\n"
            f"Label: {phone.label}\n"
            f"Assigned Agent: {assigned_agent}"
        )

    formatted_info = "\n\n".join(phone_info)
    return TextContent(type="text", text=f"Phone Numbers:\n\n{formatted_info}")


@mcp.tool(description="Play an audio file. Supports WAV and MP3 formats.")
@_safe_api
def play_audio(input_file_path: str) -> TextContent:
    file_path = handle_input_file(input_file_path)
    with open(file_path, "rb") as f:
        play(f.read(), use_ffmpeg=False)
    return TextContent(type="text", text=f"Successfully played audio file: {file_path}")


def main():
    """Run the MCP server."""
    logger.info("Starting ElevenLabs MCP server")
    mcp.run()


if __name__ == "__main__":
    main() 