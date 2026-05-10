from jarvis.voice.voice_manager import VoiceManager
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.intent_detector import IntentDetector


def generate_chat_response(text):
    lowered = text.strip().lower()

    if "انت مين" in lowered or "انت ايه" in lowered:
        return (
            "أنا جارفيس، مساعدك الهندسي الذكي. "
            "مهمتي مساعدتك في تطوير المشاريع وإدارة الأنظمة بأمان."
        )

    if "عامل ايه" in lowered:
        return "أعمل بكفاءة كاملة يا هاني."

    return "تم استلام رسالتك."


def main():
    voice = VoiceManager()
    orchestrator = Orchestrator()
    detector = IntentDetector()

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

        if voice_result.get("response"):
            print(f"Jarvis: {voice_result['response']}")

        if voice.listening and not voice_result.get("wake_detected"):

            intent = detector.detect(text)

            if intent == IntentDetector.GENERAL_CHAT:
                print(
                    f"Jarvis: "
                    f"{generate_chat_response(text)}"
                )

            elif intent == IntentDetector.DEVELOPMENT_TASK:
                report = orchestrator.process_task(text)

                decision = report["decision"]

                print("Jarvis Report:")
                print(f"- Decision: {decision['status']}")
                print(f"- Can Apply: {decision['can_apply']}")
                print(f"- Reason: {decision['reason']}")

            elif intent == IntentDetector.STOP_COMMAND:
                print("Jarvis: تم تنفيذ أمر الإيقاف.")


if __name__ == "__main__":
    main()
