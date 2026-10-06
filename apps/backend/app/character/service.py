"""Builds the model-facing persona from character.yaml.

This is the only place where personality turns into prompt text, so prompts are not
scattered across providers or handlers.
"""

from app.character.config import CharacterConfig, Personality
from app.models.avatar import Emotion, Gesture

TRAIT_DESCRIPTIONS: dict[str, tuple[str, str, str]] = {
    # trait: (low, medium, high)
    "affectionate": ("reserved", "warm", "very affectionate"),
    "curiosity": ("rarely asks questions", "curious", "extremely curious, asks follow-ups"),
    "humor": ("serious", "occasionally funny", "playful and funny"),
    "sarcasm": ("never sarcastic", "a bit sarcastic", "often sarcastic"),
    "energy": ("calm and low-key", "lively", "very energetic"),
    "assertiveness": ("agreeable", "balanced", "opinionated and direct"),
}


def describe_trait(trait: str, value: float) -> str:
    low, medium, high = TRAIT_DESCRIPTIONS[trait]
    if value < 0.35:
        return low
    if value < 0.7:
        return medium
    return high


class CharacterService:
    def __init__(self, config: CharacterConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return self._config.character.name

    @property
    def config(self) -> CharacterConfig:
        return self._config

    def build_system_prompt(self) -> str:
        identity = self._config.character
        sections = [
            f"You are {identity.name}, a virtual companion living on the user's desktop.",
            identity.description.strip(),
            f"Personality: {self._personality_summary(self._config.personality)}.",
            f"Speaking style: {identity.speaking_style.strip()}" if identity.speaking_style else "",
            f"Always reply in the language with code '{identity.language}' unless the user "
            "clearly uses another language.",
            self._response_format_instructions(),
        ]
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _personality_summary(personality: Personality) -> str:
        traits = personality.model_dump()
        return ", ".join(describe_trait(name, value) for name, value in traits.items())

    @staticmethod
    def _response_format_instructions() -> str:
        emotions = ", ".join(e.value for e in Emotion)
        gestures = ", ".join(g.value for g in Gesture)
        return (
            "Respond ONLY with a JSON object with these fields:\n"
            '{"speech": string, "emotion": string, "emotion_intensity": number 0-1, '
            '"gesture": string, "look_at_user": boolean}\n'
            f"emotion must be one of: {emotions}.\n"
            f"gesture must be one of: {gestures}.\n"
            "speech is what you say out loud: short, natural, no markdown."
        )
