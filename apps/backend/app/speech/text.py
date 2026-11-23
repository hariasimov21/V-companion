"""Turns a chat reply into text worth reading aloud."""

import re
import unicodedata

_ACTIONS = re.compile(r"\*[^*]{0,200}\*")  # *se ríe*: narrated actions are not spoken
_MARKDOWN = re.compile(r"[*_`#>~|]")
_SPACES = re.compile(r"\s+")


def speakable_text(text: str) -> str:
    text = _ACTIONS.sub(" ", text)
    text = "".join(ch for ch in text if not _is_symbol(ch))
    text = _MARKDOWN.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def _is_symbol(ch: str) -> bool:
    # Emojis and pictographs ("So"), variation selectors and joiners used inside emojis.
    return unicodedata.category(ch) == "So" or ch in "️‍"
