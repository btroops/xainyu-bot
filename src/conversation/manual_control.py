import time

class ManualControl:
    def __init__(self, timeout: int = 3600):
        self.sessions = {}
        self.timeout = timeout

    def is_manual(self, chat_id: str) -> bool:
        if chat_id in self.sessions:
            if time.time() - self.sessions[chat_id] > self.timeout:
                del self.sessions[chat_id]
                return False
            return True
        return False

    def enter(self, chat_id: str):
        self.sessions[chat_id] = time.time()

    def exit(self, chat_id: str):
        self.sessions.pop(chat_id, None)

    def toggle(self, chat_id: str) -> str:
        if self.is_manual(chat_id):
            self.exit(chat_id)
            return "auto"
        else:
            self.enter(chat_id)
            return "manual"