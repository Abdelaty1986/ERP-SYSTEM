#!/usr/bin/env python3
"""Test ElevenLabs TTS with Arabic text.

Usage:
    export ELEVENLABS_API_KEY=your_key_here
    python tests/test_elevenlabs_tts.py "النص العربي الذي تريد سماعه"
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jarvis.voice.elevenlabs_tts_provider import ElevenLabsTTSProvider


def main():
    text = " ".join(sys.argv[1:]) or "مرحبا بكم في نظام جارفيس. أنا جاهز للعمل."
    print(f"[TTS] Speaking: {text}")

    provider = ElevenLabsTTSProvider()

    if not os.environ.get("ELEVENLABS_API_KEY"):
        print("[TTS] No ELEVENLABS_API_KEY set — will use termux-tts-speak fallback")

    result = provider.speak(text)
    print(f"[TTS] Result: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
