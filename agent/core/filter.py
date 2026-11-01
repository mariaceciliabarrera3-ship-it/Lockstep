class TopicFilter:
    ALLOWED_TOPICS = ["software", "code", "architecture", "testing", "bug", "refactor", "doc"]

    def validate_topic(self, user_prompt: str) -> bool:
        """
        Fail-closed topic filter mock.
        Returns True if allowed technical keywords are present.
        """
        if not user_prompt or not isinstance(user_prompt, str):
            return False
        
        prompt_lower = user_prompt.lower()
        return any(topic in prompt_lower for topic in self.ALLOWED_TOPICS)