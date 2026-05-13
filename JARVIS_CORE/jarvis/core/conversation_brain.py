from jarvis.core.intent_detector import IntentDetector
from jarvis.core.conversation_memory import ConversationMemory

from jarvis.agents.gemini_agent import GeminiAgent
from jarvis.agents.groq_agent import GroqAgent
from jarvis.agents.openrouter_agent import OpenRouterAgent

from jarvis.runtime.runtime_aggregator import RuntimeAggregator
from jarvis.runtime.runtime_visibility import RuntimeVisibility
from jarvis.runtime.runtime_audit import RuntimeAudit


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
            response = "فهمت. هتعامل مع ده كمهمة تطوير آمنة داخل Live Safe Mode."
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

        for agent in agents:
            result = agent.think(prompt)
            if result.get("enabled") and result.get("analysis"):
                return result["analysis"].strip()

        local = self.local_runtime_response(text)
        if local:
            return local

        return (
            "أنا سامعك. المخ الخارجي مش متاح حاليًا، "
            "لكن أقدر أرد بناءً على حالة الـ Runtime المحلية "
            "وأشغل Live Safe Mode و Sandbox بدون تعديل حقيقي."
        )

    def local_runtime_response(self, text):
        lowered = text.strip().lower()

        try:
            RuntimeAggregator().aggregate()
            visibility = RuntimeVisibility().build_visibility_summary()
            audit = RuntimeAudit().run()
        except Exception as exc:
            return f"حاولت أقرأ حالتي الداخلية لكن حصل خطأ: {exc}"

        security = audit.get("security", {})
        audit_summary = visibility.get("audit_summary", {})

        asks_status = any(word in lowered for word in [
            "حالتك", "وصلت لفين", "فين", "نسبة", "امن", "أمان",
            "شغال", "صاحي", "جاهز", "status", "safe", "runtime",
        ])

        asks_what_next = any(word in lowered for word in [
            "فاضل", "الخطوة", "نعمل ايه", "بعد كده", "next",
        ])

        if asks_status:
            return (
                "أنا شغال محليًا في Live Safe Mode.\n"
                f"حالة الـ Runtime: {visibility.get('global_runtime_state')}\n"
                f"حالة الأمان: {security.get('security_state')}\n"
                f"عدد الطبقات المرئية: {visibility.get('visible_runtime_count')}\n"
                f"ذاكرة ناقصة: {audit_summary.get('missing_memory_count')}\n"
                f"موديولات ناقصة: {audit_summary.get('missing_modules_count')}\n"
                "التنفيذ الحقيقي مازال مقفول، وأي مراجعة بتتم داخل Sandbox فقط."
            )

        if asks_what_next:
            return (
                "الخطوة العملية الجاية: ربط اللوب التفاعلي بالصوت أو بالـ HUD.\n"
                "الأساس الآمن شغال: Sandbox، Audit، Visibility، Sessions.\n"
                "مش محتاجين نبني Layers جديدة دلوقتي؛ نربط الموجود ونختبره."
            )

        return None


if __name__ == "__main__":
    brain = ConversationBrain()

    tests = [
        "يا جارفيس انت وصلت لفين؟",
        "حالتك ايه دلوقتي؟",
        "فاضل ايه بعد كده؟",
    ]

    for item in tests:
        print("You:", item)
        print("Jarvis:", brain.respond(item))
        print("-" * 40)
