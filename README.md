# Gnome Council Chatbot

This repository turns an Ubuntu workstation into a whimsical, local-friendly chat
terminal for the "Council of Tricklebranch Hollow"—a five-gnome chorus that
responds using OpenAI's Chat Completions API (or any compatible endpoint).

## Prerequisites

1. **System packages** (Ubuntu 20.04+):
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip git sox ffmpeg portaudio19-dev
   ```
2. **Working directory**:
   ```bash
   mkdir -p ~/gnome_chatbot
   cd ~/gnome_chatbot
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **API credentials**: store your key locally and keep it private.
   ```bash
   echo "export OPENAI_API_KEY='sk-your-key'" >> ~/.bashrc
   source ~/.bashrc
   ```

## Usage

1. Copy `gnome_chat.py` and `system_prompt.txt` into your working directory, or
   clone this repository directly and run from its root.
2. Activate your virtual environment and start the chatbot:
   ```bash
   source venv/bin/activate
   python gnome_chat.py --speak
   ```
3. Type questions into the console. Enter `exit` or `quit` to close the chat.

### Voice Output

Passing `--speak` attempts to create a "gnomish chorus" by saving several
slightly different TTS renderings (via `pyttsx3`) and layering them with SoX.
If SoX or an audio player (`play` or `ffplay`) is unavailable, the script falls
back to sequential playback or silent mode with a warning.

### Configuration Flags

- `--model`: override the default model (`gpt-4o-mini`).
- `--prompt-file`: use a custom system prompt file.
- `--temperature`: adjust sampling temperature (defaults to 0.9).
- `--max-tokens`: cap response length (defaults to 800 tokens).
- `--no-history`: disable conversation memory between turns.
- `--quiet`: suppress console output (useful with voice playback).

## Optional Enhancements

- **Speech recognition**: install `SpeechRecognition` and `pyaudio` to capture
  microphone input, then extend `gnome_chat.py` to convert spoken words into the
  `user_input` field.
- **GUI**: wrap the chat loop in a Tkinter or Flask interface and title it
  *Tricklebranch Console* for a cozier desktop experience.
- **Ambient audio**: play a looping forest track with
  `ffplay -nodisp -autoexit -loop 0 forest.wav &` while you chat.

Have fun chatting with Muggy, Bud, Timbo, Snortz, and Lieutenant Chuckle!
