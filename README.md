# 🤖 Voice-Activated Desktop AI Assistant

Unleash the power of local AI with your voice.  
This project brings a fast, secure, and entirely offline-capable voice assistant to your desktop. Say goodbye to cloud dependencies—all speech recognition, command execution, and AI inference happen right on your machine.

---

## ✨ Demo & Showcase

Watch the assistant in action! See how it handles voice commands, integrates with local apps, and responds using a powerful, self-hosted LLM.

<p align="center">
  "AI Assistant Jarvis.mp4"
  <br>
  Watch the AI Assistant Jarvis Demo Video
  </a>
</p>

---

## 🚀 Key Features

| Feature | Description | Status |
|--------|-------------|--------|
| 🔒 100% Offline Capable | Uses Vosk for local Speech Recognition (ASR) and Ollama for local LLM inference. No internet needed for core function. | CORE |
| 🗣️ Continuous Listening | Always on, low-resource listening for the Jarvis wake word. | ACTIVE |
| 🧠 Local AI Power | Integrates with Ollama to run models like `gemma:2b` locally, providing rich, complex responses. | INTEGRATED |
| 💻 Desktop Automation | Execute common tasks: search, open apps (Spotify, Chrome), take notes, and screenshots. | COMPLETE |
| 🔊 Robust Text-to-Speech (TTS) | Multiple Windows-centric TTS fallbacks (SAPI, PowerShell, Edge-TTS) for guaranteed audio responses. | RELIABLE |

---

## ⚙️ Architecture Overview

The system runs on a simple, yet robust, pipeline:

1. **Microphone Input:** Continuous audio stream.  
2. **Vosk Listener (`vosk-model-small-en-us-0.15/`):** Listens locally for the WAKE_WORD (`jarvis`).  
3. **Command Handling (`main.py`):**  
   - **Simple Command:** Execute local actions (e.g., "Take screenshot").  
   - **Complex Prompt:** Pass question to the Gemma Worker.  
4. **Ollama Worker:** Executes `ollama run <model> <prompt>` locally.  
5. **TTS Fallbacks:** The AI response is spoken back using the first successful method (`SAPI → PowerShell → Edge-TTS`).

---
