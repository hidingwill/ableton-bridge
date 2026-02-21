import os
import json
import logging
from pathlib import Path
import sys
from dotenv import load_dotenv
import argparse

logger = logging.getLogger("ElevenLabs-MCP")

load_dotenv()


def get_claude_config_path() -> Path | None:
    """Get the Claude config directory based on platform.

    Returns the expected path even if the directory doesn't exist yet
    (first-time users). The caller is responsible for creating it.
    """
    if sys.platform == "win32":
        path = Path(Path.home(), "AppData", "Roaming", "Claude")
    elif sys.platform == "darwin":
        path = Path(Path.home(), "Library", "Application Support", "Claude")
    elif sys.platform.startswith("linux"):
        path = Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"), "Claude"
        )
    else:
        return None

    return path


def get_python_path():
    return sys.executable


def generate_config(api_key: str | None = None):
    module_dir = Path(__file__).resolve().parent
    server_path = module_dir / "server.py"
    python_path = get_python_path()

    final_api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    if not final_api_key:
        print("Error: ElevenLabs API key is required.")
        print("Please either:")
        print("  1. Pass the API key using --api-key argument, or")
        print("  2. Set the ELEVENLABS_API_KEY environment variable, or")
        print("  3. Add ELEVENLABS_API_KEY to your .env file")
        sys.exit(1)

    config = {
        "mcpServers": {
            "ElevenLabs": {
                "command": python_path,
                "args": [
                    str(server_path),
                ],
                "env": {"ELEVENLABS_API_KEY": final_api_key},
            }
        }
    }

    return config


def _redact_config(config: dict) -> dict:
    """Return a deep copy of config with secret values replaced by a placeholder."""
    import copy
    redacted = copy.deepcopy(config)
    for _server_name, server_cfg in redacted.get("mcpServers", {}).items():
        env = server_cfg.get("env", {})
        for key in env:
            if "KEY" in key.upper() or "SECRET" in key.upper() or "TOKEN" in key.upper():
                env[key] = "***REDACTED***"
    return redacted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print config to screen instead of writing to file",
    )
    parser.add_argument(
        "--api-key",
        help="ElevenLabs API key (alternatively, set ELEVENLABS_API_KEY environment variable)",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        help="Custom path to the directory containing claude_desktop_config.json",
    )
    args = parser.parse_args()

    config = generate_config(args.api_key)

    if args.print:
        print(json.dumps(_redact_config(config), indent=2))
    else:
        claude_path = args.config_path if args.config_path else get_claude_config_path()
        if claude_path is None:
            print(
                "Could not find Claude config path automatically. Please specify it "
                "using --config-path argument. The argument should be the directory "
                "containing claude_desktop_config.json."
            )
            sys.exit(1)

        # If user passed a file path, resolve to its parent directory
        if claude_path.suffix == ".json":
            claude_path = claude_path.parent

        claude_path.mkdir(parents=True, exist_ok=True)
        config_file = claude_path / "claude_desktop_config.json"

        # Merge into existing config instead of clobbering
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read %s (%s), starting fresh", config_file, exc)
                existing = {}
        else:
            existing = {}

        if "mcpServers" not in existing:
            existing["mcpServers"] = {}
        # Merge our server entries into the existing mcpServers
        for server_name, server_cfg in config.get("mcpServers", {}).items():
            existing["mcpServers"][server_name] = server_cfg

        print("Writing config to", config_file)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
