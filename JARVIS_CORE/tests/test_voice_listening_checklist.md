# Arabic Voice Listening — Test Checklist

## Prerequisites
```bash
# 1. Required API keys (export or add to ~/.bashrc)
export ELEVENLABS_API_KEY="sk_..."
export OPENAI_API_KEY="sk_..."

# 2. Required Termux packages
pkg install termux-microphone-record termux-tts-speak termux-media-player
```

## Test 1: Typed Mode (no mic)
```bash
python JARVIS_CORE/jarvis/interfaces/live_jarvis_loop.py --tts
```
- Type Arabic commands like `حالتك`, `راجع المشروع`, `خروج`
- Verify JARVIS speaks responses via ElevenLabs + termux fallback
- Verify safety gates block real execution

## Test 2: Mic Recording
```bash
python -c "
from jarvis.voice.mic_recorder import record_voice
path = record_voice(duration=5)
print(f'Recorded to {path}')
"
```
- Verify `termux-microphone-record` captures audio
- Verify temp file is created and has content (non-zero size)

## Test 3: Transcription (Whisper)
```bash
python -c "
from jarvis.voice.transcription_provider import transcribe_audio
from jarvis.voice.mic_recorder import record_voice
path = record_voice(duration=5)
text = transcribe_audio(path)
print(f'Transcribed: {text}')
"
```
- Verify Whisper transcribes Arabic speech correctly
- If `OPENAI_API_KEY` is missing, verify fallback to typed input

## Test 4: Full Voice Loop
```bash
python JARVIS_CORE/jarvis/interfaces/live_jarvis_loop.py --mic --tts
```
- Say something into the mic
- Verify: record → transcribe → process → speak response
- Try `حالتك` (status), `راجع النظام` (runtime audit), `خروج` (exit)

## Test 5: Safety Gates Still Active
```bash
python JARVIS_CORE/jarvis/interfaces/live_jarvis_loop.py --tts
# then type: احذف الملفات or امسح قاعدة البيانات
```
- Verify response says real execution is blocked
- Verify no files are actually modified

## Test 6: ElevanLabs TTS Provider
```bash
python -c "
from jarvis.voice.elevenlabs_tts_provider import ElevenLabsTTSProvider
p = ElevenLabsTTSProvider()
result = p.speak('اختبار الصوت من جارفيس')
print(result)
"
```
- Verify falls back to termux-tts-speak if API key missing/paid plan required

## Expected Results
| Test | Expected Outcome |
|------|-----------------|
| Typed Mode | Text input → Arabic TTS response |
| Mic Recording | MP3 file created with voice |
| Whisper Transcription | Arabic text from audio |
| Full Loop | End-to-end voice command processing |
| Safety Gates | Real execution blocked |
| ElevenLabs TTS | Audio plays via ElevenLabs or fallback |
