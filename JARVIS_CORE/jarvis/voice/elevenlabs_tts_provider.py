import json
import os
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path


def load_config():
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "voice_config.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


class ElevenLabsTTSProvider:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        self.eleven_config = self.config.get("elevenlabs", {})
        self.fallback_config = self.config.get("fallback", {})
        self.disable_termux = self.config.get("disable_termux_tts_when_elevenlabs", False)

    def speak(self, text):
        if self.api_key:
            try:
                return self._elevenlabs_speak(text)
            except Exception as exc:
                print(f"[ElevenLabs] API error: {exc}")
                if self.disable_termux:
                    raise
        if self.fallback_config.get("enabled", True):
            return self._fallback_speak(text)
        raise RuntimeError("No TTS provider available")

    def _elevenlabs_speak(self, text):
        voice_id = self.eleven_config.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
        model_id = self.eleven_config.get("model_id", "eleven_multilingual_v2")
        stability = self.eleven_config.get("stability", 0.5)
        similarity_boost = self.eleven_config.get("similarity_boost", 0.75)
        style = self.eleven_config.get("style", 0.0)
        use_speaker_boost = self.eleven_config.get("use_speaker_boost", True)
        latency = self.eleven_config.get("optimize_streaming_latency", 0)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        if latency:
            url += f"?optimize_streaming_latency={latency}"

        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": use_speaker_boost,
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("xi-api-key", self.api_key)
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                audio_data = resp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"ElevenLabs API error {e.code}: {e.read().decode(errors='replace')}") from e

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            audio_path = tmp.name

        try:
            subprocess.run(
                ["termux-media-player", "play", audio_path],
                check=True, timeout=30,
            )
        finally:
            os.unlink(audio_path)

        return {"provider": "elevenlabs", "text": text}

    def _fallback_speak(self, text):
        engine = self.fallback_config.get("engine", "termux-tts-speak")
        lang = self.fallback_config.get("language", "ar")
        subprocess.run(
            [engine, "-l", lang, text],
            check=True, timeout=30,
        )
        return {"provider": "fallback", "text": text, "engine": engine}


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "مرحبا بكم في نظام جارفيس"
    provider = ElevenLabsTTSProvider()
    result = provider.speak(text)
    print(json.dumps(result, ensure_ascii=False))
