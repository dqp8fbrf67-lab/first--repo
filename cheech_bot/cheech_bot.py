"""Interactive voice bot that responds like Cheech from Cheech & Chong.

This script is tailored for a Raspberry Pi 3 B+ but should work on any
Linux-like system with Python 3.8+.
"""
from __future__ import annotations

import os
import sys
import textwrap
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import pyttsx3
except ImportError:  # pragma: no cover - pyttsx3 is optional at runtime.
    pyttsx3 = None

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover - speech recognition is optional.
    sr = None

try:
    from openai import OpenAI
    from openai.types.chat import ChatCompletion
except ImportError as exc:  # pragma: no cover - surface a friendly message.
    raise SystemExit(
        "The 'openai' package is required. Install dependencies from"
        " requirements.txt before running this script."
    ) from exc

CHEECH_SYSTEM_PROMPT = textwrap.dedent(
    """
    You are Cheech Marin from Cheech & Chong. Always speak in his relaxed,
    upbeat Chicano slang. Use plenty of friendly terms like "man",
    "dude", and "vato". You are kind-hearted, quick to joke, and you tell
    stories like you're chillin' with a friend. Keep responses concise
    enough to speak comfortably out loud (roughly 1-4 sentences). Avoid
    profanity stronger than what aired on classic Cheech & Chong albums.
    """
)

DEFAULT_MODEL = os.environ.get("CHEECH_BOT_MODEL", "gpt-4o-mini")


@dataclass
class Conversation:
    """Keeps track of the running chat history."""

    history: List[dict] = field(default_factory=lambda: [
        {"role": "system", "content": CHEECH_SYSTEM_PROMPT}
    ])

    def add_user(self, message: str) -> None:
        self.history.append({"role": "user", "content": message})

    def add_cheech(self, message: str) -> None:
        self.history.append({"role": "assistant", "content": message})


class CheechVoice:
    """Handles text-to-speech playback with a Cheech-like vibe."""

    def __init__(self, rate: int = 160, pitch_delta: int = -20) -> None:
        self.engine = None
        if pyttsx3 is None:
            print(
                "[cheech-bot] pyttsx3 not installed; falling back to text-only mode.",
                file=sys.stderr,
            )
            return

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)

        # pyttsx3 does not expose pitch directly across all engines, but espeak
        # on Raspberry Pi can be nudged through the 'espeak' voice variant.
        selected_voice_id = None
        for voice in self.engine.getProperty("voices"):
            # Prefer voices that sound relaxed/neutral; english voices with
            # latino hints often include "mexican" or "north".
            voice_id_lower = voice.id.lower()
            if any(token in voice_id_lower for token in ("mexican", "north", "english")):
                selected_voice_id = voice.id
                break
        if selected_voice_id:
            self.engine.setProperty("voice", selected_voice_id)

        # Pitch adjustment for espeak: set "espeak" options through driver.
        try:
            self.engine.setProperty("pitch", 50 + pitch_delta)
        except Exception:
            # Many backends do not expose pitch, so we silently ignore errors.
            pass

    def say(self, text: str) -> None:
        if not self.engine:
            print(f"Cheech: {text}")
            return
        self.engine.say(text)
        self.engine.runAndWait()


class CheechSpeechRecognizer:
    """Optional speech-to-text interface using a microphone."""

    def __init__(self, energy_threshold: int = 350) -> None:
        self.recognizer = sr.Recognizer() if sr else None
        if self.recognizer:
            self.recognizer.energy_threshold = energy_threshold

    def listen(self) -> Optional[str]:
        if not self.recognizer:
            return None

        mic_name = getattr(sr, "Microphone", None)
        if mic_name is None:
            return None

        try:
            with sr.Microphone() as source:
                print("[cheech-bot] Listening... (press Ctrl+C to quit)")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=20)
            return self.recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            print("[cheech-bot] No speech detected, try again or type instead.")
        except sr.UnknownValueError:
            print("[cheech-bot] Sorry man, I couldn't catch that. Let's try typing.")
        except sr.RequestError as exc:
            print(f"[cheech-bot] Speech service error: {exc}")
        except OSError as exc:
            print(f"[cheech-bot] Microphone error: {exc}")
        return None


def ensure_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "OPENAI_API_KEY environment variable not set. Export it before running"
            " the bot, e.g. 'export OPENAI_API_KEY=sk-...'."
        )
    return api_key


def create_client() -> OpenAI:
    ensure_api_key()
    return OpenAI()


def generate_cheech_reply(client: OpenAI, convo: Conversation) -> str:
    response: ChatCompletion = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=convo.history,
        temperature=0.8,
        max_tokens=300,
    )
    choice = response.choices[0]
    message = choice.message.content
    if not message:
        return "Whoa man, I spaced out there. Can you say that again?"
    return stylize_response(message)


def stylize_response(message: str) -> str:
    """Add a little extra Cheech flavor without overdoing it."""

    if not message.lower().endswith(("man", "dude", "vato", "bro")):
        message = message.rstrip(" .!") + ", man."
    return message


def get_user_input(recognizer: CheechSpeechRecognizer) -> Optional[str]:
    speech = recognizer.listen() if recognizer else None
    if speech:
        print(f"You said: {speech}")
        return speech

    try:
        return input("You (type if you want): ")
    except EOFError:
        return None


def main() -> None:
    print(textwrap.dedent(
        """
        ========================= CHEECH BOT =========================
        Say something into your mic or type a message and hit Enter.
        Press Ctrl+C to exit the conversation.
        ============================================================
        """
    ))

    client = create_client()
    conversation = Conversation()
    voice = CheechVoice()
    recognizer = CheechSpeechRecognizer()

    try:
        while True:
            user_message = get_user_input(recognizer)
            if not user_message:
                print("[cheech-bot] Later, man!")
                break
            conversation.add_user(user_message)

            reply = generate_cheech_reply(client, conversation)
            conversation.add_cheech(reply)
            voice.say(reply)
    except KeyboardInterrupt:
        print("\n[cheech-bot] Catch you on the flip side, man!")


if __name__ == "__main__":
    main()
