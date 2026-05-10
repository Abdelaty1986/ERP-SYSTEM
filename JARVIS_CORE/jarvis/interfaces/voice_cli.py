from jarvis.voice.voice_manager import VoiceManager
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.conversation_brain import ConversationBrain


def main():
    voice = VoiceManager()
    brain = ConversationBrain()
    orchestrator = Orchestrator()

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
            decision = report["decision"]

            print("Jarvis Report:")
            print(f"- Decision: {decision['status']}")
            print(f"- Can Apply: {decision['can_apply']}")
            print(f"- Reason: {decision['reason']}")


if __name__ == "__main__":
    main()
