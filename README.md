# Jarvis: A Voice-Enabled AI Desktop Assistant

A personal AI assistant for the terminal, inspired by Tony Stark's JARVIS. It chats with a personality you define, speaks its replies out loud, and can take real actions on your computer, like opening apps, checking system stats, and searching the web.

Built with Python and free-tier models through [OpenRouter](https://openrouter.ai), so it costs nothing to run.

<!-- Add a screenshot or demo video link here -->

## Features

- **Tool use:** the model decides when to call a tool, your code runs it, and the result goes back to the model.
  - Open whitelisted desktop apps and websites
  - Show CPU, RAM, disk, and battery status
  - Tell the date and time
  - Search Google
- **Voice output:** replies are converted to speech with OpenRouter's text-to-speech API and played automatically.
- **Custom personality:** the assistant's name, how it addresses you, and its tone are set in one system prompt.
- **Model fallback:** if a free model is busy or unavailable, it automatically tries the next one.
- **Safe by design:** it can only open apps and sites from an allowlist you control.

## How it works

```
You type  ->  LLM (OpenRouter)  ->  needs a tool?  ->  Python runs it  ->  result back to LLM
                                         |
                                         v
                                  final reply  ->  printed + spoken
```

The agent loop sends the conversation to the model, runs any tool calls it requests, feeds the results back, and repeats until the model gives a final answer (capped at 5 rounds so it can't loop forever).

## Setup

**Requirements:** Python 3.10+ and a free [OpenRouter API key](https://openrouter.ai/keys).

1. Clone the repo and enter the folder:
   ```
   git clone https://github.com/YOUR-USERNAME/jarvis.git
   cd jarvis
   ```
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # Mac/Linux
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and add your key:
   ```
   OPENROUTER_API_KEY=your-key-here
   ```
5. Run it:
   ```
   python jarvis.py
   ```

## Usage

Try things like:

- "How's my system doing?"
- "Open VS Code"
- "Open YouTube"
- "Search for Java polymorphism examples"
- "What time is it?"

Commands: `mute` / `voice off` silences the voice, `unmute` / `voice on` brings it back, and `exit` quits.

## Customize

Everything is configured at the top of `jarvis.py`:

| Setting | What it does |
|---|---|
| `ASSISTANT_NAME`, `USER_NAME` | Names used in the prompt and terminal |
| `SYSTEM_PROMPT` | The personality and rules |
| `FALLBACK_MODELS` | Chat models, tried in order |
| `TTS_MODEL`, `VOICE_ENABLED` | Voice model and on/off switch |
| `APPS`, `WEBSITES` | The allowlist of things it can open |

Free model names on OpenRouter change often, so check [openrouter.ai/models](https://openrouter.ai/models) if a model returns an error. The `openrouter/free` router picks an available free model that supports tool calling.

## Security

- Your API key lives in `.env`, which is git-ignored. Never commit it.
- Jarvis can only open apps and websites listed in `APPS` and `WEBSITES`. It cannot run arbitrary commands.

## Roadmap

- [ ] Voice input (speech-to-text)
- [ ] Wake word ("Hey Jarvis")
- [ ] Long-term memory (SQLite)
- [ ] Reminders and a to-do list
- [ ] Calendar and email integrations
- [ ] HUD-style graphical interface

## Tech stack

Python, OpenRouter API (OpenAI-compatible), `openai`, `psutil`, `python-dotenv`, `requests`

## Notes

- App launching is configured for Windows, macOS, and Linux, but it has mainly been tested on Windows.
- Voice playback uses the built-in Windows player, `afplay` on macOS, and `ffplay` on Linux.
