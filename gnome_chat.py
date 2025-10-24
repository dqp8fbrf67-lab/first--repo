#!/usr/bin/env python3
"""Gnome Council chatbot CLI.

This script provides a local chat interface that talks to an OpenAI-compatible
chat-completions endpoint using the whimsical "Council of Tricklebranch Hollow"
persona.  It optionally layers text-to-speech output to create a gnomish chorus
if `pyttsx3` and SoX are available.

Environment variables:
    OPENAI_API_KEY   – API key for OpenAI or compatible service (required).
    OPENAI_API_BASE  – Optional alternate base URL for self-hosted gateways.

Example usage::

    $ python3 gnome_chat.py --speak

"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, List, Optional

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "The 'openai' package is required. Install it with 'pip install openai'."
    ) from exc

SYSTEM_PROMPT_FILENAME = "system_prompt.txt"
DEFAULT_MODEL = "gpt-4o-mini"


def read_system_prompt(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise SystemExit(
            f"System prompt file not found at {path}. Create it before running."
        ) from exc

    if not text:
        raise SystemExit(f"System prompt file {path} is empty.")
    return text


def build_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "OPENAI_API_KEY is not set. Add it to your environment before running."
        )
    client_kwargs = {"api_key": api_key}
    api_base = os.getenv("OPENAI_API_BASE")
    if api_base:
        client_kwargs["base_url"] = api_base
    return OpenAI(**client_kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Chat with the Council of Tricklebranch Hollow over an OpenAI-compatible API."
        )
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model identifier for chat.completions (default: %(default)s)",
    )
    parser.add_argument(
        "--prompt-file",
        default=SYSTEM_PROMPT_FILENAME,
        type=Path,
        help="Path to the system prompt file (default: system_prompt.txt)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.9,
        help="Sampling temperature for the model (default: %(default)s)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=800,
        help="Maximum tokens to request from the API (default: %(default)s)",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Do not preserve conversation context between turns.",
    )
    parser.add_argument(
        "--speak",
        action="store_true",
        help="Render replies using a layered gnomish chorus when possible.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress printed assistant replies (useful for voice-only runs).",
    )
    return parser


class ChorusSpeaker:
    """Layered speech synthesis using pyttsx3 and SoX when available."""

    VOICE_PRESETS = (
        {"id_hint": "english+f3", "rate": 185},
        {"id_hint": "english+m3", "rate": 170},
        {"id_hint": "english+croak", "rate": 165},
        {"id_hint": "english_rp", "rate": 180},
        {"id_hint": "english+whisper", "rate": 190},
    )

    def __init__(self) -> None:
        try:  # Import lazily so the script still works without pyttsx3 installed.
            import pyttsx3  # type: ignore
        except ImportError:  # pragma: no cover - runtime fallback only
            self._engine_cls = None
            self.available = False
            return

        self._engine_cls = pyttsx3.init
        self.available = True
        self._sox = shutil.which("sox")
        self._player = shutil.which("play") or shutil.which("ffplay")

    def speak(self, text: str) -> None:
        if not self.available:
            print("[Voice disabled] Install pyttsx3 for speech output.", file=sys.stderr)
            return

        if not text.strip():
            return

        try:
            self._speak_impl(text)
        except Exception as exc:  # pragma: no cover - best-effort audio support
            print(f"[Voice playback failed: {exc}]", file=sys.stderr)

    def _speak_impl(self, text: str) -> None:
        assert self._engine_cls is not None

        segments = [line.strip() for line in text.splitlines() if line.strip()]
        if not segments:
            return

        # Collapse back into a single chunk for synthesis, then apply layering.
        payload = " \n".join(segments)
        with TemporaryDirectory() as temp_dir:
            temp_paths = []
            for idx, preset in enumerate(self.VOICE_PRESETS):
                path = Path(temp_dir) / f"gnome_{idx}.wav"
                engine = self._engine_cls()
                voice_id = self._select_voice(engine, preset["id_hint"])
                if voice_id:
                    engine.setProperty("voice", voice_id)
                engine.setProperty("rate", preset["rate"])
                engine.save_to_file(payload, str(path))
                engine.runAndWait()
                temp_paths.append(path)

            if not temp_paths:
                return

            if self._sox and self._player and len(temp_paths) > 1:
                layered_path = Path(temp_dir) / "chorus.wav"
                cmd = [self._sox, "-m"]
                for p in temp_paths:
                    cmd.extend(["-v", "0.4", str(p)])
                cmd.append(str(layered_path))
                subprocess.run(cmd, check=True)  # noqa: S603, S607 - trusted args
                self._play(layered_path)
            elif self._player:
                for path in temp_paths:
                    self._play(path)
            else:
                # Fallback to pyttsx3 direct playback if play command missing.
                engine = self._engine_cls()
                engine.say(payload)
                engine.runAndWait()

    def _select_voice(self, engine, fragment: str) -> Optional[str]:
        for voice in engine.getProperty("voices"):
            if fragment.lower() in voice.id.lower():
                return voice.id
        return None

    def _play(self, path: Path) -> None:
        assert self._player is not None
        if Path(self._player).name == "ffplay":
            subprocess.run(  # noqa: S603, S607 - trusted args
                [self._player, "-nodisp", "-autoexit", str(path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run([self._player, str(path)], check=True)  # noqa: S603, S607


def start_chat(args: argparse.Namespace) -> None:
    client = build_client()
    system_prompt = read_system_prompt(args.prompt_file)

    history: List[dict[str, str]] = []
    if not args.no_history:
        history.append({"role": "system", "content": system_prompt})

    speaker = ChorusSpeaker() if args.speak else None

    print("🌿  Gnome Council ready.  Type 'exit' to leave the Hollow.\n")

    while True:
        try:
            user_input = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nFarewell from the Council!")
            break

        if user_input.strip().lower() in {"exit", "quit"}:
            print("The council scurries back into the moss. Farewell!")
            break

        if not user_input.strip():
            continue

        messages: List[dict[str, str]] = []
        if history:
            messages.extend(history)
        else:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_input})

        try:
            completion = client.chat.completions.create(
                model=args.model,
                messages=messages,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
        except Exception as exc:  # pragma: no cover - relies on remote service
            print(f"[API error: {exc}]", file=sys.stderr)
            continue

        reply_content = completion.choices[0].message.content or ""
        reply = reply_content.strip()

        if not args.quiet:
            print(reply)
            print()

        if speaker:
            speaker.speak(reply)

        if not args.no_history:
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    start_chat(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
