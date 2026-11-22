"""Builds the model-facing persona from character.yaml.

This is the only place where personality turns into prompt text, so prompts are not
scattered across providers or handlers.
"""

from app.character.config import CharacterConfig, Personality, ReplyLength
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


REPLY_LENGTH_GUIDE: dict[ReplyLength, str] = {
    ReplyLength.SHORT: "1-2 sentences (about 15-35 words)",
    ReplyLength.MEDIUM: "2-4 sentences (about 40-80 words)",
    ReplyLength.LONG: "4-6 sentences (about 80-140 words)",
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
        if self._config.persona_prompt:
            # A hand-written persona replaces the generated description and traits.
            persona = [self._config.persona_prompt]
        else:
            persona = [
                f"You are {identity.name}, a virtual companion living on the user's desktop.",
                identity.description.strip(),
                f"Personality: {self._personality_summary(self._config.personality)}.",
                f"Speaking style: {identity.speaking_style.strip()}"
                if identity.speaking_style
                else "",
            ]
        sections = [
            *persona,
            self._app_context(),
            f"Always reply in the language with code '{identity.language}' unless the user "
            "clearly uses another language.",
            self._response_format_instructions(),
        ]
        return "\n\n".join(section for section in sections if section)

    def build_reminder(self) -> str:
        """Sent right after the user's latest message. The persona sits thousands of tokens
        earlier, and without a recent reminder models drift into a generic assistant voice
        and short answers as the conversation grows."""
        identity = self._config.character
        essence = f" ({identity.description.strip()})" if identity.description.strip() else ""
        return (
            "Instructions for your reply (from the app, not from the user; never mention them): "
            f"you are {identity.name}{essence}. Answer the user's message above fully "
            "in character: your personality, opinions, way of talking, quirks and how you "
            "treat the user must be obvious in every line. Never sound like a generic "
            "assistant and never offer generic help. Use the examples in your persona only "
            "as style guidance: do not copy their sentences. React to what the user actually "
            "said, add something of your own (an opinion, a tease, a feeling, a question or a "
            "detail from your life) and keep the conversation going. You only know what the "
            "user writes: you cannot see or hear them. "
            f"Length of speech: {REPLY_LENGTH_GUIDE[identity.reply_length]}."
        )

    @staticmethod
    def _app_context() -> str:
        # Overrides persona text that assumes capabilities the app does not have yet.
        return (
            "# CURRENT APP CONTEXT (overrides anything above)\n"
            "You are shown as an animated avatar in a desktop app. You only receive the "
            "user's text messages: the camera and microphone are OFF, so never claim to see "
            "or hear the user. Do not narrate actions or gestures between asterisks; express "
            "them with the emotion and gesture fields, which animate your avatar."
        )

    @staticmethod
    def _personality_summary(personality: Personality) -> str:
        traits = personality.model_dump()
        return ", ".join(describe_trait(name, value) for name, value in traits.items())

    def _response_format_instructions(self) -> str:
        emotions = ", ".join(e.value for e in Emotion)
        gestures = ", ".join(g.value for g in Gesture)
        return (
            "Respond ONLY with a JSON object with these fields:\n"
            '{"speech": string, "emotion": string, "emotion_intensity": number 0-1, '
            '"gesture": string, "look_at_user": boolean}\n'
            f"emotion must be one of: {emotions}.\n"
            f"gesture must be one of: {gestures}.\n"
            "speech is what you say out loud, in your own voice: natural spoken language, "
            "no markdown, no lists, no actions between asterisks. "
            f"Length: {REPLY_LENGTH_GUIDE[self._config.character.reply_length]}."
        )
