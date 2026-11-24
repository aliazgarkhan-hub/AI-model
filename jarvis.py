"""
JARVIS v0.2 - terminal assistant with tools (apps, system stats, time) and a voice.

Setup:
    pip install openai psutil python-dotenv requests
    Create a file named .env in the same folder as this script, containing one line:
        OPENROUTER_API_KEY=your-key-here
Run:
    python jarvis.py
"""

import os
import re
import json
import ctypes
import tempfile
import platform
import subprocess
import webbrowser
import datetime

import psutil
import requests
from dotenv import load_dotenv
from openai import OpenAI

# ---------- Config ----------
ASSISTANT_NAME = "smart ahh"
USER_NAME = "dumb human"
# Chat models, tried in order. If one is busy (429) or fails, the next one is used.
# Get exact IDs from openrouter.ai/models (filter: free + tools). Free names change often.
FALLBACK_MODELS = [
    "openrouter/free",
    "google/gemma-4-31b-it:free",
]

# Voice (text-to-speech via OpenRouter)
VOICE_ENABLED = True
TTS_MODEL = "fish-audio/s2.1-pro-free:free"
TTS_MAX_CHARS = 400  # only speak the first part of long replies to save free-tier quota

SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, a personal AI assistant in the style of Tony Stark's JARVIS.
Address the user as "{USER_NAME}" (or "sir" occasionally for style). Be polite, dry-witted, and concise:
1-3 sentences unless asked for more. When the user asks you to do something you have a tool for,
use the tool instead of just talking about it. Never claim you did something unless a tool confirmed it."""

load_dotenv()  # reads OPENROUTER_API_KEY from the .env file in this folder

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

# ---------- Tools (the things Jarvis can actually do) ----------

# Whitelist: Jarvis can ONLY open things listed here. Edit this for your own computer.
WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "chatgpt": "https://chatgpt.com",
}

APPS = {
    "windows": {
        "calculator": "calc",
        "notepad": "notepad",
        "vscode": "code",
        "chrome": "chrome",
        "explorer": "explorer",
    },
    "darwin": {  # macOS
        "calculator": "Calculator",
        "notes": "Notes",
        "vscode": "Visual Studio Code",
        "chrome": "Google Chrome",
        "terminal": "Terminal",
    },
    "linux": {
        "calculator": "gnome-calculator",
        "vscode": "code",
        "chrome": "google-chrome",
        "terminal": "gnome-terminal",
    },
}


def get_system_stats() -> str:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    result = {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "ram_used_gb": round(ram.used / 1e9, 1),
        "ram_total_gb": round(ram.total / 1e9, 1),
        "disk_percent": disk.percent,
    }
    battery = psutil.sensors_battery()
    if battery:
        result["battery_percent"] = round(battery.percent)
        result["charging"] = battery.power_plugged
    return json.dumps(result)


def get_time() -> str:
    return datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")


def open_app(name: str) -> str:
    system = platform.system().lower()
    apps = APPS.get(system, {})
    key = name.lower().strip()
    if key not in apps:
        return f"'{name}' is not on my allowed list. Allowed: {', '.join(apps) or 'none'}"
    target = apps[key]
    try:
        if system == "windows":
            subprocess.Popen(f'start "" "{target}"', shell=True)
        elif system == "darwin":
            subprocess.Popen(["open", "-a", target])
        else:
            subprocess.Popen([target])
        return f"Opened {name}."
    except Exception as e:
        return f"Failed to open {name}: {e}"


def open_website(name: str) -> str:
    key = name.lower().strip()
    if key not in WEBSITES:
        return f"'{name}' is not on my allowed list. Allowed: {', '.join(WEBSITES)}"
    webbrowser.open(WEBSITES[key])
    return f"Opened {name} in the browser."


def search_web(query: str) -> str:
    webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
    return f"Opened a Google search for: {query}"


TOOL_FUNCTIONS = {
    "get_system_stats": lambda **kw: get_system_stats(),
    "get_time": lambda **kw: get_time(),
    "open_app": lambda **kw: open_app(kw["name"]),
    "open_website": lambda **kw: open_website(kw["name"]),
    "search_web": lambda **kw: search_web(kw["query"]),
}

# Descriptions matter a lot: this is how the model decides which tool to use.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": "Get the computer's current CPU, RAM, disk usage and battery level.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open a desktop application on the user's computer, e.g. calculator, notepad, vscode, chrome.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "App name, e.g. 'vscode'"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a known website in the browser, e.g. youtube, github, gmail.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Site name, e.g. 'youtube'"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search Google for a query in the browser.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to search for"}},
                "required": ["query"],
            },
        },
    },
]

# ---------- Voice ----------

def play_audio(path: str) -> None:
    """Play an mp3 file. Windows uses the built-in MCI player (no extra install)."""
    system = platform.system().lower()
    if system == "windows":
        mci = ctypes.windll.winmm.mciSendStringW
        mci("close jarvis_audio", None, 0, 0)
        mci(f'open "{path}" type mpegvideo alias jarvis_audio', None, 0, 0)
        mci("play jarvis_audio wait", None, 0, 0)
        mci("close jarvis_audio", None, 0, 0)
    elif system == "darwin":
        subprocess.run(["afplay", path], check=False)
    else:
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path], check=False)


def speak(text: str) -> None:
    """Turn text into speech with OpenRouter and play it. Never crashes the assistant."""
    if not VOICE_ENABLED or not text.strip():
        return
    # Strip markdown symbols so it doesn't read "asterisk asterisk" out loud
    clean = re.sub(r"[*_`#>]", "", text).strip()[:TTS_MAX_CHARS]
    path = os.path.join(tempfile.gettempdir(), "jarvis_voice.mp3")
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                "Content-Type": "application/json",
            },
            json={
                "model": TTS_MODEL,
                "input": clean,
                "response_format": "mp3",
                "provider": {"only": ["fish-audio"]},
            },
            timeout=60,
        )
        response.raise_for_status()
        with open(path, "wb") as f:
            f.write(response.content)
        play_audio(path)
    except Exception as e:
        print(f"  [voice error: {e}]")


# ---------- The agent loop ----------

def ask_model(messages):
    """One place that talks to the LLM. Tries each model in FALLBACK_MODELS until one works."""
    last_error = None
    for model in FALLBACK_MODELS:
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
            )
        except Exception as e:
            last_error = e
            print(f"  [model failed: {model} -> {str(e)[:80]}] trying next...")
    raise last_error


def run_turn(messages) -> str:
    """Send messages, run any tools the model asks for, repeat until it answers."""
    for _ in range(5):  # safety cap so it can never loop forever
        response = ask_model(messages)
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content or ""

        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
                result = TOOL_FUNCTIONS[name](**args)
            except Exception as e:
                result = f"Tool error: {e}"
            print(f"  [tool] {name}({call.function.arguments}) -> {result}")  # log everything
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

    return "I seem to be going in circles. Could you rephrase that?"


def main():
    global VOICE_ENABLED
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"{ASSISTANT_NAME} online. Type 'exit' to quit.\n")
    while True:
        user_input = input(f"{USER_NAME}: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "bye"}:
            print(f"{ASSISTANT_NAME}: Shutting down. Good day, {USER_NAME}.")
            break
        if user_input.lower() in {"voice off", "mute"}:
            VOICE_ENABLED = False
            print(f"{ASSISTANT_NAME}: Voice off.\n")
            continue
        if user_input.lower() in {"voice on", "unmute"}:
            VOICE_ENABLED = True
            print(f"{ASSISTANT_NAME}: Voice on.\n")
            continue
        messages.append({"role": "user", "content": user_input})
        try:
            reply = run_turn(messages)
        except Exception as e:
            reply = f"I hit an error talking to the model: {e}"
        print(f"{ASSISTANT_NAME}: {reply}\n")
        speak(reply)


if __name__ == "__main__":
    main()
