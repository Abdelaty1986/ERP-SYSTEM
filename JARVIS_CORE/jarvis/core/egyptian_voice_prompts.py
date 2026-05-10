class EgyptianVoicePrompts:
    def start(self, task):
        return f"تمام يا هاني. بدأت تنفيذ المهمة: {task}"

    def planning(self):
        return "بحلل المشروع وبجهز خطة التنفيذ."

    def validation(self):
        return "براجع التعديلات وبفحص الأمان."

    def tests_passed(self):
        return "الاختبارات نجحت، وكل حاجة مستقرة."

    def tests_failed(self):
        return "في اختبار فشل. هوقف التنفيذ عشان الأمان."

    def simulation_mode(self):
        return "الوضع الحالي محاكاة فقط. مش هلمس ملفات المشروع الحقيقية."

    def gated_mode(self):
        return "تم تفعيل التنفيذ الحقيقي الآمن بعد موافقتك."

    def completed(self):
        return "تم التنفيذ بنجاح يا هاني."

    def blocked(self, reason):
        return f"وقفت التنفيذ لحماية المشروع. السبب: {reason}"
