# Jarvis — Local Voice Assistant

This repository contains a local, offline-capable voice assistant built with Python. The main application is `main.py`, which listens for a wake word (default: "jarvis"), accepts voice commands, and responds using multiple TTS methods. It uses the Vosk speech recognition model included in the repo for offline ASR and integrates with Ollama to run an LLM locally.

**Project Overview**
- **Main script**: `main.py` — GUI + listener + command handling + TTS.
- **Vosk model**: `vosk-model-small-en-us-0.15/` — included in the workspace and required for offline speech recognition.
- **Ollama**: External binary used to run the chosen model (`gemma:2b` by default). The app calls `ollama run <model> <prompt>`.

**What it does**
- Listens continuously for audio via your microphone and recognizes speech using Vosk.
- Awakes on the wake word (`jarvis`) and processes spoken commands.
- Executes common actions (open/close Chrome, Spotify, take notes, screenshots, tell time, etc.).
- Sends complex prompts to Ollama to get richer AI responses and speaks them using multiple TTS fallbacks.

**Key files**
- `main.py`: Application code (listener, UI, TTS, commands).
- `vosk-model-small-en-us-0.15/`: Offline ASR model (must remain next to `main.py`).
- `README.md`: This file.
- `requirements.txt`: Python dependencies for the project.

**Requirements**
- OS: Windows (best-tested). Some features may work on other OSes but file paths and TTS methods are Windows-centric.
- Python 3.9+ recommended.
- The project uses these Python packages (see `requirements.txt`): `PyQt6`, `vosk`, `PyAudio`, `comtypes`, `edge-tts`, `mss`.
- External: `Ollama` (https://ollama.ai) should be installed separately and available on your PATH or at a path the script can detect.

**Installation (Windows)**
1. Create and activate a virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

3. PyAudio on Windows may require a binary wheel. If `pip install PyAudio` fails, try:

```powershell
pip install pipwin
pipwin install pyaudio
```

4. Install Ollama separately (follow instructions on https://ollama.ai). Ensure `ollama.exe` is installable and accessible in one of the usual locations (e.g., `C:\Program Files\Ollama\ollama.exe`). The script will try common locations and `where/which` to find it.

5. Make sure the included Vosk model directory `vosk-model-small-en-us-0.15` is present next to `main.py`. The app will abort if it cannot find the model.

**Configuration**
- Edit `main.py` top-level constants:
  - `MODEL_NAME` — Model name passed to Ollama (default: `gemma:2b`).
  - `WAKE_WORD` — Wake word (default: `jarvis`).
  - `HIDE_COMMANDS` / `WAKE_PHRASES` — Customize supported commands/phrases.

**How to run**
- From the repo root (where `main.py` lives):

```powershell
python main.py
```

- The app runs a full-screen translucent UI and a system tray icon. It will announce when it’s ready.

**Common voice commands (examples)**
- "Jarvis" — wake the assistant (uses `WAKE_WORD`).
- "Search for <query>" or "Google <query>" — open Chrome with a Google search.
- "Open Spotify" / "Search Spotify for <query>" — open Spotify or search.
- "Open notes" / "Take notes" — opens a timestamped notes file in Notepad and saves spoken lines.
- "Close notes" — stops note-taking.
- "Take screenshot" — saves a screenshot in the project folder (requires `mss`).
- "What time is it" — tells the current time.
- "Close" / "Hide yourself" / "Minimize" — minimizes to tray and sleeps until reawakened.

**TTS (Text-to-Speech) behavior**
The app tries multiple TTS methods in order, falling back if one fails:
1. **Windows SAPI** (`comtypes` + `SAPI.SpVoice`) — local and fast.
2. **PowerShell TTS** — spawns PowerShell with `System.Speech` (very reliable on Windows).
3. **edge-tts** — uses Microsoft Edge neural voices (async, requires internet for downloads).
4. **Print fallback** — prints text to console when TTS fails.

If you want a particular TTS method prioritized/disabled, edit the `GuaranteedTTS.methods` list in `main.py`.

**Ollama integration**
- `main.py` calls the local `ollama` executable to run the model in `GemmaWorker`:

```python
subprocess.run([OLLAMA_PATH, "run", MODEL_NAME, self.prompt], ...)
```

- If Ollama is not installed or not on PATH, the app will return a helpful error message.

**Troubleshooting**
- "Vosk model not found": Ensure `vosk-model-small-en-us-0.15` is present next to `main.py`.
- Microphone not detected or no audio: Verify microphone is enabled in Windows, and that your account allows mic access. You can also inspect console output for listed microphones.
- PyAudio install errors on Windows: use `pipwin` to install the prebuilt wheel.
- Ollama not found: install Ollama and ensure `ollama.exe` is discoverable. The script attempts several default locations.
- TTS not producing sound: try switching to PowerShell TTS (should work if Windows `System.Speech` is available). Edge-TTS requires internet and properly installed `edge-tts` package.

**Security & Privacy**
- Speech recognition using Vosk is performed locally using the included model — no cloud ASR is used by default.
- Ollama runs model inference locally if you configure and run local models. If you point the app to a remote model/service, be aware of privacy implications.

**Extending / Customizing**
- Add commands by editing `JarvisApp.onText()` in `main.py`.
- Replace the Vosk model with a different one: download and place it next to `main.py`, then update `vosk_model_path` if you change the folder name.
- Use a different language model by changing `MODEL_NAME` (and ensuring Ollama has that model available).

**Useful paths**
- `main.py` — application entry point.
- `vosk-model-small-en-us-0.15/` — included Vosk model directory.

**License**
- This project contains third-party models (Vosk, Ollama models) which have their own licenses. Check each vendor's license before redistribution.

Enjoy! If you'd like, I can:
- Add example unit tests or a small launcher script, or
- Create a `launch` task for VS Code, or
- Help package the app into an executable for Windows (PyInstaller).

