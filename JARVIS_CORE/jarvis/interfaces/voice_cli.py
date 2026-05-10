from jarvis.voice.voice_manager import VoiceManager

from jarvis.core.conversation_brain import ConversationBrain
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.output_formatter import OutputFormatter


def main():
    voice = VoiceManager()

    brain = ConversationBrain()
    orchestrator = Orchestrator()
    formatter = OutputFormatter()

    print("Jarvis Voice CLI")
    print("اكتب: جارفيس")
    print("اكتب: اسكت للخروج من وضع الاستماع")
    print("اكتب: خروج لإنهاء البرنامج")
    print("=" * 40)

    while True:
        text = input("You: ").strip()

        if text == "خروج":
            print("Jarvis: تم إنهاء الجلسة.")
            break

        voice_result = voice.process_input(text)

        if voice_result.get("wake_detected"):
            print(f"Jarvis: {voice_result['response']}")
            continue

        if not voice.listening:
            continue

        brain_result = brain.respond(text)

        print(f"Jarvis: {brain_result['response']}")

        if brain_result["should_process_task"]:

            report = orchestrator.process_task(text)

            formatted = formatter.format_report(report)

            print("")
            print(formatted)
            print("")


if __name__ == "__main__":
    main()
