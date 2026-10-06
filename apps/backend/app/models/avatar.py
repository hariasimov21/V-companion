from enum import StrEnum


class Emotion(StrEnum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    EXCITED = "excited"
    SAD = "sad"
    ANNOYED = "annoyed"
    EMBARRASSED = "embarrassed"
    CURIOUS = "curious"
    THINKING = "thinking"
    SLEEPY = "sleepy"
    SURPRISED = "surprised"


class Gesture(StrEnum):
    NONE = "none"
    NOD = "nod"
    SHAKE_HEAD = "shake_head"
    WAVE = "wave"
    LAUGH = "laugh"
    SIGH = "sigh"
    LOOK_LEFT = "look_left"
    LOOK_RIGHT = "look_right"
    STRETCH = "stretch"
