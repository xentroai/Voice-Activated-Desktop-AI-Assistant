import sys
import subprocess
import json
import webbrowser
from threading import Thread
import threading
import urllib.parse
import datetime
from queue import Queue
from PyQt6 import QtWidgets, QtCore, QtGui
import vosk
import pyaudio
import os
import platform
import tempfile
import time

MODEL_NAME = "gemma:2b"
WAKE_WORD = "jarvis"
HIDE_COMMANDS = ["close", "hide yourself", "minimize"]
WAKE_PHRASES = ["wake", "wake up", "wake jarvis", "wake me", "wake work jarvis"]

def get_ollama_path():
    system = platform.system()
    if system == "Windows":
        possible_paths = [
            r"C:\Program Files\Ollama\ollama.exe",
            r"C:\Users\{}\AppData\Local\Programs\Ollama\ollama.exe".format(os.getenv('USERNAME')),
            "ollama.exe",
            "ollama"
        ]
    else:
        possible_paths = ["ollama", "/usr/local/bin/ollama"]

    for path in possible_paths:
        if os.path.exists(path):
            return path
        try:
            if system == "Windows":
                result = subprocess.run(f"where {path}", shell=True, capture_output=True, text=True)
            else:
                result = subprocess.run(f"which {path}", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                return path
        except:
            continue
    return "ollama"

OLLAMA_PATH = get_ollama_path()
print(f"[SYSTEM] Using Ollama path: {OLLAMA_PATH}")

BASE_PATH = os.path.dirname(os.path.abspath(__file__))

speech_queue = Queue()

class GuaranteedTTS:
    def __init__(self):
        self.methods = [
            self.windows_tts_method,
            self.powershell_tts_method,
            self.edge_tts_method,
            self.print_only_method
        ]

    def windows_tts_method(self, text):
        """Method 1: Windows built-in TTS using SAPI"""
        try:
            import comtypes.client
            speaker = comtypes.client.CreateObject("SAPI.SpVoice")
            speaker.Speak(text)
            return True
        except Exception as e:
            print(f"[TTS] Windows SAPI failed: {e}")
            return False

    def powershell_tts_method(self, text):
        """Method 2: PowerShell TTS (most reliable)"""
        try:
            clean_text = text.replace('"', '`"').replace("'", "`'")
            ps_script = f'''
Add-Type -AssemblyName System.speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.Volume = 100
$speak.Rate = 1
$speak.Speak("{clean_text}")
'''
            result = subprocess.run([
                "powershell", "-Command", ps_script
            ], capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception as e:
            print(f"[TTS] PowerShell failed: {e}")
            return False

    def edge_tts_method(self, text):
        """Method 3: Use edge-tts (online)"""
        try:
            import asyncio
            import edge_tts

            async def generate_speech():
                communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                    tmp_path = tmp_file.name

                await communicate.save(tmp_path)

                if os.name == 'nt':
                    os.system(f'start wmplayer "{tmp_path}" /play /close')
                else:
                    os.system(f'ffplay -autoexit -nodisp "{tmp_path}"')

                time.sleep(2)
                os.unlink(tmp_path)

            import threading
            def run_async():
                asyncio.new_event_loop().run_until_complete(generate_speech())

            thread = threading.Thread(target=run_async)
            thread.daemon = True
            thread.start()
            thread.join(timeout=10)
            return True

        except Exception as e:
            print(f"[TTS] Edge-TTS failed: {e}")
            return False

    def print_only_method(self, text):
        """Method 4: Final fallback - just print"""
        print(f"[SPEECH]: {text}")
        return True

    def speak(self, text):
        """Try all methods until one works"""
        if not text or not text.strip():
            return False

        print(f"[ASSISTANT]: {text}")

        for method in self.methods:
            if method(text):
                return True
        return False

tts_engine = GuaranteedTTS()

def tts_worker():
    """TTS worker thread"""
    while True:
        text = speech_queue.get()
        if text is None:
            break
        tts_engine.speak(text)
        speech_queue.task_done()

tts_thread = Thread(target=tts_worker, daemon=True)
tts_thread.start()

def speak(text):
    """Safely add text to speech queue"""
    if text and text.strip():
        speech_queue.put(text)
        return True
    return False

vosk_model_path = os.path.join(BASE_PATH, "vosk-model-small-en-us-0.15")

if not os.path.exists(vosk_model_path):
    print(f"CRITICAL ERROR: Vosk model not found at {vosk_model_path}")
    print("Please download it from https://alphacephei.com/vosk/models and extract it here.")
    sys.exit(1)

model = vosk.Model(vosk_model_path)
print("[SYSTEM] Vosk model loaded successfully")

class ListenerThread(QtCore.QThread):
    wake = QtCore.pyqtSignal()
    text = QtCore.pyqtSignal(str)

    def run(self):
        try:
            self.audio = pyaudio.PyAudio()

            for i in range(self.audio.get_device_count()):
                dev_info = self.audio.get_device_info_by_index(i)
                if dev_info['maxInputChannels'] > 0:
                    print(f"Microphone: {dev_info['name']}")

            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=4096
            )
            self.stream.start_stream()

            recognizer = vosk.KaldiRecognizer(model, 16000)

            print("[SYSTEM] Voice listener started...")
            print(f"[SYSTEM] Say '{WAKE_WORD}' to activate")

            while True:
                data = self.stream.read(4096, exception_on_overflow=False)
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text_data = result.get("text", "").lower().strip()

                    if text_data:
                        print(f"[USER]: {text_data}")
                        if WAKE_WORD in text_data:
                            self.wake.emit()
                        else:
                            self.text.emit(text_data)
        except Exception as e:
            print(f"[LISTENER ERROR]: {e}")

class GemmaSignal(QtCore.QObject):
    finished = QtCore.pyqtSignal(str)

class GemmaWorker(QtCore.QRunnable):
    def __init__(self, prompt, signal_obj):
        super().__init__()
        self.prompt = prompt
        self.signal_obj = signal_obj

    def run(self):
        try:
            print(f"[AI] Processing: {self.prompt}")

            result = subprocess.run(
                [OLLAMA_PATH, "run", MODEL_NAME, self.prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            response = result.stdout.strip()
            if not response:
                response = "I heard you, but didn't get a response. Please try again."

            print(f"[AI RESPONSE]: {response}")

        except subprocess.TimeoutExpired:
            response = "The request took too long to process. Please try again."
        except FileNotFoundError:
            response = "Error: Ollama not found. Please make sure Ollama is installed and running."
        except Exception as e:
            response = f"Error processing request: {str(e)}"

        self.signal_obj.finished.emit(response)

class GlowUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.glow = 0
        self.increasing = True
        self.active_mode = False

        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.updateGlow)
        timer.start(20)

    def set_active(self, active):
        self.active_mode = active

    def updateGlow(self):
        step = 2 if self.active_mode else 1
        max_glow = 180 if self.active_mode else 120

        if self.increasing:
            self.glow += step
            if self.glow >= max_glow:
                self.increasing = False
        else:
            self.glow -= step
            if self.glow <= 40:
                self.increasing = True
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        center = QtCore.QPointF(rect.center().x(), rect.center().y())

        if self.active_mode:
            color = QtGui.QColor(100, 255, 200, self.glow)
        else:
            color = QtGui.QColor(100, 200, 255, self.glow)

        gradient = QtGui.QRadialGradient(center.x(), center.y(), 300.0)
        gradient.setColorAt(0, color)
        gradient.setColorAt(1, QtGui.QColor(0, 0, 0, 0))

        painter.setBrush(QtGui.QBrush(gradient))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 300, 300)

class JarvisApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = GlowUI()
        self.setCentralWidget(self.ui)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.showFullScreen()

        self.is_listening = False
        self.sleep_mode = False
        self.notes_process = None
        self.notes_path = None
        self.is_writing_notes = False

        self.setup_tray()

        self.listener = ListenerThread()
        self.listener.wake.connect(self.onWake)
        self.listener.text.connect(self.onText)
        self.listener.start()

        # Startup announcement: run every time the app initializes.
        def _startup_notify():
            try:
                speak("Jarvis is ready, say Jarvis to activate")
            except Exception as e:
                print(f"[STARTUP] Notify failed: {e}")

        QtCore.QTimer.singleShot(1500, _startup_notify)

    def test_tts_methods(self):
        print("\n" + "="*60)
        print("TESTING TTS METHODS...")
        print("="*60)

        methods = [
            ("Windows SAPI", "Testing Windows built-in speech"),
            ("PowerShell TTS", "Testing PowerShell speech synthesis"),
            ("Edge TTS", "Testing online speech service")
        ]

        for i, (method_name, test_text) in enumerate(methods):
            print(f"\nTesting {method_name}...")
            QtCore.QTimer.singleShot(i * 3000, lambda m=method_name, t=test_text: self.test_method(m, t))

        QtCore.QTimer.singleShot(len(methods) * 3000 + 2000, self.final_ready)

    def test_method(self, method_name, test_text):
        print(f"🎧 {method_name}: '{test_text}'")
        speak(test_text)

    def open_chrome_search(self, query=None):
        try:
            if query:
                url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            else:
                url = "https://www.google.com"
            subprocess.Popen(f'start chrome "{url}"', shell=True)
            speak("Opening browser")
        except Exception:
            webbrowser.open(url)
            speak("Opening browser")

    def close_chrome(self):
        try:
            subprocess.run(['taskkill', '/IM', 'chrome.exe', '/F'], shell=True, capture_output=True)
            speak("Closed Chrome")
        except Exception:
            speak("Could not close Chrome")

    def open_spotify(self, query=None):
        try:
            if query:
                url = f"https://open.spotify.com/search/{urllib.parse.quote_plus(query)}"
                webbrowser.open(url)
                speak(f"Searching Spotify for {query}")
            else:
                try:
                    subprocess.Popen(["spotify"], shell=True)
                except Exception:
                    webbrowser.open("https://open.spotify.com")
                speak("Opening Spotify")
        except Exception:
            speak("Couldn't open Spotify")

    def close_spotify(self):
        try:
            subprocess.run(['taskkill', '/IM', 'spotify.exe', '/F'], shell=True, capture_output=True)
            speak("Closed Spotify")
        except Exception:
            speak("Could not close Spotify")

    def open_notes(self):
        try:
            name = f"notes_{int(time.time())}.txt"
            path = os.path.join(BASE_PATH, name)
            open(path, 'a', encoding='utf-8').close()
            p = subprocess.Popen(["notepad.exe", path], shell=True)
            self.notes_process = p
            self.notes_path = path
            self.is_writing_notes = True
            speak("Notes opened. Start speaking and I will write. Say close notes when finished.")
        except Exception:
            speak("Couldn't open notes")

    def append_notes(self, text):
        try:
            if not self.notes_path:
                self.open_notes()
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.notes_path, 'a', encoding='utf-8') as f:
                f.write(f"[{ts}] {text}\n")
            speak("Noted")
        except Exception:
            speak("Failed to write note")

    def close_notes(self):
        try:
            if self.notes_process and self.notes_process.poll() is None:
                try:
                    self.notes_process.terminate()
                except Exception:
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.notes_process.pid)], shell=True)
            self.is_writing_notes = False
            speak("Notes closed")
        except Exception:
            speak("Failed to close notes")

    def tell_time(self):
        now = datetime.datetime.now()
        speak(f"The time is {now.strftime('%I:%M %p')}")

    def take_screenshot(self):
        try:
            import mss

            try:
                was_visible = self.isVisible()
                if was_visible:
                    self.hide()
                    QtWidgets.QApplication.processEvents()
                    time.sleep(0.15)
            except Exception:
                pass

            out = os.path.join(BASE_PATH, f"screenshot_{int(time.time())}.png")
            with mss.mss() as sct:
                sct.shot(output=out)

            try:
                if was_visible:
                    self.showFullScreen()
                    QtWidgets.QApplication.processEvents()
            except Exception:
                pass

            speak("Screenshot saved")
        except Exception:
            speak("Screenshot feature requires the mss package")

    def final_ready(self):
        speak("All systems operational. Jarvis is ready. Say Jarvis to begin.")
        print("✓ System fully ready - Say 'Jarvis' to activate!")

    def setup_tray(self):
        icon_path = os.path.join(BASE_PATH, "jarvis.ico")
        if os.path.exists(icon_path):
            icon = QtGui.QIcon(icon_path)
        else:
            pixmap = QtGui.QPixmap(32, 32)
            pixmap.fill(QtGui.QColor(100, 200, 255))
            icon = QtGui.QIcon(pixmap)

        self.tray = QtWidgets.QSystemTrayIcon(icon)
        self.tray.activated.connect(self.tray_activated)

        menu = QtWidgets.QMenu()
        show_action = menu.addAction("Show")
        show_action.triggered.connect(self.show_window)
        wake_action = menu.addAction("Wake")
        wake_action.triggered.connect(self.wake_from_tray)
        test_audio_action = menu.addAction("Test Audio")
        test_audio_action.triggered.connect(self.test_audio)
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.exit_app)

        self.tray.setContextMenu(menu)
        self.tray.setVisible(True)
        self.tray.showMessage("JARVIS", "Assistant is running in system tray", icon, 2000)

    def test_audio(self):
        speak("This is a manual audio test. Can you hear me clearly?")

    def tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):
        self.sleep_mode = False
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def onWake(self):
        if getattr(self, 'sleep_mode', False):
            # Wake up when wake word detected even while sleeping
            try:
                self.sleep_mode = False
                self.showFullScreen()
                self.activateWindow()
                self.ui.set_active(True)
                self.is_listening = True
                speak("Waking up. I'm ready.")
                print('[SYSTEM] Woken by wake word while sleeping')
            except Exception:
                pass
            return

        self.showFullScreen()
        self.activateWindow()
        self.ui.set_active(True)
        self.is_listening = True
        speak("Yes sir? I'm listening and ready for your commands.")

    def onText(self, text):
        text = text.lower().strip()
        if getattr(self, 'sleep_mode', False):
            for phrase in WAKE_PHRASES:
                if phrase in text:
                    try:
                        self.sleep_mode = False
                        self.showFullScreen()
                        self.activateWindow()
                        self.ui.set_active(True)
                        self.is_listening = True
                        speak("Waking up. I'm ready.")
                        print('[SYSTEM] Woken by voice command')
                    except Exception:
                        pass
                    return
            print(f"[IGNORED WHILE SLEEPING]: {text}")
            return

        if not self.is_listening:
            return

        print(f"[COMMAND]: {text}")

        if len(text) < 2:
            return

        if "stop listening" in text or "go to sleep" in text:
            speak("Going to sleep mode. Say Jarvis to wake me up.")
            self.is_listening = False
            self.ui.set_active(False)
            self.hide()
            return

        if self.is_writing_notes:
            if "close notes" in text or "finish notes" in text or "stop notes" in text:
                self.close_notes()
            else:
                self.append_notes(text)
            return

        if text.startswith("search for ") or text.startswith("search ") or text.startswith("google "):
            for prefix in ("search for ", "search ", "google "):
                if text.startswith(prefix):
                    query = text[len(prefix):].strip()
                    break
            else:
                query = text
            self.open_chrome_search(query)
            self.ui.set_active(True)
            return

        if text in ("new tab", "open tab", "open new tab"):
            self.open_chrome_search(None)
            return

        if "open chrome" in text or text == "chrome" or text == "open browser":
            self.open_chrome_search(None)
            self.ui.set_active(True)
            return

        if "close chrome" in text or text == "close browser":
            self.close_chrome()
            return

        if "youtube" in text:
            webbrowser.open("https://www.youtube.com")
            speak("Opening YouTube")
            self.ui.set_active(True)
            return

        if text.startswith("search spotify for ") or text.startswith("spotify search ") or (text.startswith("play ") and " on spotify" in text):
            if " on spotify" in text:
                query = text.replace("play ", "").replace(" on spotify", "").strip()
            else:
                for prefix in ("search spotify for ", "spotify search "):
                    if text.startswith(prefix):
                        query = text[len(prefix):].strip()
                        break
            self.open_spotify(query)
            self.ui.set_active(True)
            return

        if "open spotify" in text or text == "spotify":
            self.open_spotify(None)
            self.ui.set_active(True)
            return

        if "close spotify" in text:
            self.close_spotify()
            return

        if "open notes" in text or "start notes" in text or "take notes" in text:
            self.open_notes()
            return

        if "what time" in text or "tell me the time" in text or text == "time":
            self.tell_time()
            return

        if "screenshot" in text or "take screenshot" in text:
            self.take_screenshot()
            return

        if any(cmd in text for cmd in HIDE_COMMANDS):
            speak("Minimizing to system tray")
            self.hide()
            self.sleep_mode = True
            self.is_listening = False
            self.ui.set_active(False)
            return

        print(f"[AI QUERY]: {text}")
        signal_obj = GemmaSignal()
        signal_obj.finished.connect(self.handleGemmaResponse)
        worker = GemmaWorker(text, signal_obj)
        QtCore.QThreadPool.globalInstance().start(worker)

    def wake_from_tray(self):
        try:
            self.sleep_mode = False
            self.showFullScreen()
            self.activateWindow()
            self.ui.set_active(True)
            self.is_listening = True
            speak("Waking up. I'm ready.")
        except Exception:
            pass

    def handleGemmaResponse(self, response):
        if response:
            clean_response = response.replace("*", "").replace("**", "").replace("__", "").strip()
            speak(clean_response)

        self.is_listening = True
        self.ui.set_active(True)
        print("[SYSTEM] Continuing to listen for commands...")

    def exit_app(self):
        speak("Shutting down")
        QtCore.QTimer.singleShot(1000, self.force_quit)

    def force_quit(self):
        speech_queue.put(None)
        if hasattr(self, 'listener') and self.listener.isRunning():
            self.listener.terminate()
            self.listener.wait(2000)
        self.tray.hide()
        QtWidgets.QApplication.quit()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = JarvisApp()
    window.hide()

    sys.exit(app.exec())