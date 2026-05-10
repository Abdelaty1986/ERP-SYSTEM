from jarvis.core.intent_detector import IntentDetector
from jarvis.core.conversation_memory import ConversationMemory


class ConversationBrain:
    def __init__(self):
        self.detector = IntentDetector()
        self.memory = ConversationMemory()

    def respond(self, text):
        self.memory.add("user", text)

        intent = self.detector.detect(text)

        if intent == IntentDetector.STOP_COMMAND:
            response = "تم إيقاف وضع الاستماع."
            self.memory.add("assistant", response)
            return {
                "intent": intent,
                "response": response,
                "should_process_task": False
            }

        if intent == IntentDetector.DEVELOPMENT_TASK:
            response = "فهمت. سأتعامل مع هذا كطلب تطوير وأراجعه بأمان."
            self.memory.add("assistant", response)
            return {
                "intent": intent,
                "response": response,
                "should_process_task": True
            }

        response = self.general_response(text)
        self.memory.add("assistant", response)

        return {
            "intent": intent,
            "response": response,
            "should_process_task": False
        }

    def general_response(self, text):
        lowered = text.strip().lower()

        if "انت مين" in lowered or "انت ايه" in lowered:
            return (
                "أنا جارفيس، مساعدك الهندسي الذكي. "
                "أقدر أناقشك، أراجع مشروعك، وأساعدك تطور بأمان."
            )

        if "تقدر تعمل ايه" in lowered:
            return (
                "أقدر أفهم المهام، أوزعها على Agents مجانية، "
                "أحلل المخاطر، وأجهز خطة تنفيذ قبل أي تعديل."
            )

        if "عامل ايه" in lowered:
            return "جاهز للعمل يا هاني."

        return "فاهمك. كمل، وأنا هتابع معاك."


if __name__ == "__main__":
    brain = ConversationBrain()

    tests = [
        "انت تعرف انت ايه",
        "تقدر تعمل ايه",
        "راجع المشروع",
        "اسكت"
    ]

    for item in tests:
        print("You:", item)
        print("Jarvis:", brain.respond(item))
        print("-" * 40)
