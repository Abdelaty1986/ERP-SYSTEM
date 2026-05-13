from jarvis.core.intent_detector import IntentDetector
from jarvis.core.conversation_memory import ConversationMemory
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent


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
        prompt = (
            "أنت جارفيس، مساعد هندسي تفاعلي داخل مشروع JARVIS CORE. "
            "رد على هاني باللهجة المصرية بشكل مختصر وعملي. "
            "لا تدّعي أنك طبقت تعديلات. "
            "لو السؤال عن تنفيذ أو تعديل، وضّح أن التنفيذ الحقيقي مقفول "
            "وأن الوضع المتاح هو Live Safe Mode و Sandbox فقط.\n\n"
            f"رسالة هاني: {text}"
        )

        agents = [
            GeminiAgent(),
            GroqAgent(),
            OpenRouterAgent(),
        ]

        skipped = []

        for agent in agents:
            result = agent.think(prompt)
            if result.get("enabled") and result.get("analysis"):
                return result["analysis"].strip()

            skipped.append(result.get("analysis", ""))

        return (
            "أنا سامعك، لكن المخ الحواري الخارجي غير متصل حاليًا "
            "لأن مفاتيح GEMINI/GROQ/OPENROUTER غير مفعلة. "
            "أقدر أشغل أوامر Live Safe Mode والـ Sandbox، "
            "لكن النقاش الذكي الحر محتاج API key مفعّل."
        )


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
