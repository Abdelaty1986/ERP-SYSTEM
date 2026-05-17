import json
import os
import tempfile
import urllib.request
import urllib.error


class TranscriptionProvider:
    def __init__(self):
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.deepgram_key = os.environ.get("DEEPGRAM_API_KEY")

    def transcribe(self, audio_path):
        if self.openai_key:
            try:
                return self._whisper_transcribe(audio_path)
            except Exception as exc:
                print(f"[Whisper] API error: {exc}")
        if self.deepgram_key:
            try:
                return self._deepgram_transcribe(audio_path)
            except Exception as exc:
                print(f"[Deepgram] API error: {exc}")
        return self._typed_fallback()

    def _whisper_transcribe(self, audio_path):
        boundary = "----JarvisFormBoundary"
        filename = os.path.basename(audio_path)

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: audio/mpeg\r\n\r\n"
        ).encode("utf-8") + audio_data + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="model"\r\n\r\n'
            f"whisper-1\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="language"\r\n\r\n'
            f"ar\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=body,
            method="POST",
        )
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"Whisper API error {e.code}: {e.read().decode(errors='replace')}"
            ) from e

        text = (result.get("text") or "").strip()
        if not text:
            raise RuntimeError("Whisper returned empty transcription")
        return text

    def _deepgram_transcribe(self, audio_path):
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        url = "https://api.deepgram.com/v1/listen?model=nova-2&language=ar&smart_format=true"

        req = urllib.request.Request(url, data=audio_data, method="POST")
        req.add_header("Authorization", f"Token {self.deepgram_key}")
        req.add_header("Content-Type", "audio/mpeg")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"Deepgram API error {e.code}: {e.read().decode(errors='replace')}"
            ) from e

        transcript = (
            result.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
        ).strip()

        if not transcript:
            raise RuntimeError("Deepgram returned empty transcription")
        return transcript

    def _typed_fallback(self):
        print("[INPUT] اكتب أمرك (أو Enter للخروج):")
        text = input().strip()
        return text


def transcribe_audio(audio_path):
    provider = TranscriptionProvider()
    return provider.transcribe(audio_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        text = transcribe_audio(sys.argv[1])
    else:
        text = TranscriptionProvider()._typed_fallback()
    print(json.dumps({"transcription": text}, ensure_ascii=False))
