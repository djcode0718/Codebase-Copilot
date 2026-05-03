from typing import List, Dict


class ChatMemory:
    """
    Simple in-memory chat history.
    Each message: {"role": "user" | "assistant", "content": "..."}
    """

    def __init__(self, max_turns: int = 6):
        self.history: List[Dict[str, str]] = []
        self.max_turns = max_turns  # keep last N turns (user+assistant pairs)

    def add_user(self, message: str):
        self.history.append({"role": "user", "content": message})
        self._trim()

    def add_assistant(self, message: str):
        self.history.append({"role": "assistant", "content": message})
        self._trim()

    def get_history(self) -> List[Dict[str, str]]:
        return self.history

    def clear(self):
        self.history = []

    def _trim(self):
        """
        Keep only the last `max_turns * 2` messages (user+assistant pairs)
        """
        max_msgs = self.max_turns * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]