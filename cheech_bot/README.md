# Cheech Voice Bot

Turn your Raspberry Pi 3 B+ into a laid-back conversational buddy that talks like Cheech from **Cheech & Chong**. The bot listens through a microphone, sends your message to OpenAI for a response, and speaks the answer back using `pyttsx3` (which leverages `espeak` on Raspberry Pi).

> **Heads-up:** You need an OpenAI API key with access to chat models such as `gpt-4o-mini` or better.

## 1. Prepare Your Pi

1. Update your system:

   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. Install audio tooling and portaudio headers (needed for PyAudio):

   ```bash
   sudo apt install -y python3-pyaudio portaudio19-dev espeak
   ```

3. Clone this repository (or copy the `cheech_bot` folder) onto your Pi and install Python dependencies:

   ```bash
   cd /path/to/repo/cheech_bot
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   > If PyAudio fails to build, ensure `portaudio19-dev` and `python3-dev` are installed, then retry `pip install pyaudio`.

4. Export your OpenAI API key (replace the value with your key):

   ```bash
   export OPENAI_API_KEY="sk-your-key"
   ```

## 2. Run the Bot

Activate your virtual environment if it's not already active:

```bash
source /path/to/repo/cheech_bot/.venv/bin/activate
```

Launch the bot:

```bash
python cheech_bot.py
```

Speak into your microphone or type responses when prompted. Cheech will answer back in his signature style. Press **Ctrl+C** to exit.

## 3. Configuration Tips

- **Model:** Set `CHEECH_BOT_MODEL` to try a different OpenAI chat model, e.g.:
  ```bash
  export CHEECH_BOT_MODEL="gpt-4.1-mini"
  ```
- **Voice:** To swap to another `pyttsx3` voice, edit the selection logic inside `CheechVoice` in `cheech_bot.py`.
- **No microphone?** The bot automatically falls back to manual text input.
- **Text-only mode:** If `pyttsx3` isn't available, Cheech's replies still print to the terminal.

## 4. Troubleshooting

- If audio playback sounds choppy, try lowering the rate inside `CheechVoice(rate=...)`.
- When speech recognition misfires, type your message manually.
- Network hiccups or API quota issues will raise an exception from the OpenAI client; check your key and connectivity.

Enjoy cruising through conversations, man! ✌️
