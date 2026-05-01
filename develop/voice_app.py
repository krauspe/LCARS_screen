#!/usr/bin/env python3
"""
Standalone Speech Recognition Application
Listens for voice commands containing the word "computer"
"""

import speech_recognition as sr
import sys


class SpeechRecognitionApp:
    """Simple speech recognition engine that listens for voice commands."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self._running = False

    def start(self):
        """Begin listening for voice commands."""
        self._running = True
        print("🎤 Speech Recognition Started")
        print('   Say "COMPUTER ..." to issue a command')
        print("   Press Ctrl+C to exit\n")

        try:
            with sr.Microphone() as source:
                print("Adjusting for ambient noise (please wait)...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("✓ Ready to listen\n")

                while self._running:
                    try:
                        print("Listening...", end="", flush=True)
                        audio = self.recognizer.listen(
                            source, timeout=5, phrase_time_limit=5
                        )
                        print("\r            ", end="\r", flush=True)

                        text = self.recognizer.recognize_google(audio).lower()
                        print(f"Recognized: {text}")

                        if "computer" in text:
                            command = text.split("computer")[-1].strip()
                            print(f"✓ Command received: {command}\n")
                        else:
                            print("  (no command trigger detected, try again)\n")

                    except sr.WaitTimeoutError:
                        print("\r            ", end="\r", flush=True)
                        continue
                    except sr.UnknownValueError:
                        print("\r            ", end="\r", flush=True)
                        print("⚠ Could not understand audio")
                        continue
                    except Exception as e:
                        print(f"\n✗ Error: {e}")
                        continue

        except Exception as e:
            print(f"\n✗ Microphone Error: {e}", file=sys.stderr)
            sys.exit(1)

    def stop(self):
        """Stop listening."""
        self._running = False
        print("\n🛑 Speech Recognition Stopped")


def main():
    """Main entry point."""
    app = SpeechRecognitionApp()
    try:
        app.start()
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    main()
