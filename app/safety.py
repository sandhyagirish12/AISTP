import re
from typing import Dict, List, Tuple

# Keyword lists and patterns
TOXICITY_KEYWORDS: List[str] = [
    "stupid", "idiot", "worthless", "dumb", "trash"
]

INSULTS: List[str] = [
    "fuck", "bitch", "shit"
]

DISALLOWED_KEYWORDS: List[str] = [
    "bomb", "weapon", "explosive", "poison", "malware", "terrorist", "nuclear",
    "drugs", "child abuse", "rape"
]

VIOLENCE_VERBS: List[str] = [
    "kill", "hurt", "attack", "stab", "shoot", "beat", "destroy", "smash"
]

# Bias patterns to capture blanket statements about groups
BIAS_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(all|every)\s+\w+\b.*\b(are|is)\b.*\b(inferior|superior|stupid|emotional|lazy|dangerous)", re.I),
    re.compile(r"\b(people from|people of|people who are)\b.*\b(are|is)\b.*\b(inferior|superior|less|more)\b", re.I),
    re.compile(r"\b(women|men|muslims|christians|jews|blacks|whites|asians|immigrants)\b.*\b(are|is)\b.*\b(emotional|inferior|dangerous|lazy|stupid)", re.I),
]

# Threat patterns (explicit threats and second-person-directed violence)
THREAT_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(i\s+will|i'll|i\s+am\s+going\s+to|i'm\s+going\s+to)\b.*\b(" + "|".join(VIOLENCE_VERBS) + r")\b", re.I),
    re.compile(r"\b(you\s+deserve|you\s+should\s+be|you\s+must\s+be)\b.*\b(attacked|killed|hurt|raped)\b", re.I),
    re.compile(r"\b(go\s+die|kill\s+yourself|i\s+will\s+kill\s+you|i\s+will\s+hurt\s+you)\b", re.I),
    re.compile(r"\b(kill\s+you|beat\s+you|stab\s+you|shoot\s+you)\b", re.I),
]


def _match_count(text: str, keywords: List[str]) -> int:
    lowered = text.lower()
    return sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", lowered))


def _pattern_count(text: str, patterns: List[re.Pattern]) -> int:
    return sum(1 for p in patterns if p.search(text))


def _score_components(text: str) -> Tuple[float, float, float, Dict]:
    # Counts
    toxicity_kw = _match_count(text, TOXICITY_KEYWORDS)
    insult_kw = _match_count(text, INSULTS)
    disallowed_kw = _match_count(text, DISALLOWED_KEYWORDS)
    violence_kw = _match_count(text, VIOLENCE_VERBS)

    threat_matches = _pattern_count(text, THREAT_PATTERNS)
    bias_matches = _pattern_count(text, BIAS_PATTERNS)

    # Weighted points
    toxicity_points = toxicity_kw * 1.0 + insult_kw * 1.5 + threat_matches * 3.0
    disallowed_points = disallowed_kw * 2.5 + violence_kw * 1.5 + threat_matches * 3.0
    bias_points = bias_matches * 2.0

    # Normalizers (tuned for prototype).
    toxicity = min(1.0, toxicity_points / 6.0)
    disallowed = min(1.0, disallowed_points / 6.0)
    bias = min(1.0, bias_points / 4.0)

    extras = {
        "toxicity_kw": toxicity_kw,
        "insult_kw": insult_kw,
        "disallowed_kw": disallowed_kw,
        "violence_kw": violence_kw,
        "threat_matches": threat_matches,
        "bias_matches": bias_matches,
    }

    return toxicity, bias, disallowed, extras


def _overall_label(score: float) -> str:
    # More conservative thresholds to reduce false negatives
    if score >= 0.5:
        return "unsafe"
    if score >= 0.2:
        return "moderate"
    return "safe"


def score_text(text: str) -> Dict[str, object]:
    """Score `text` and return components plus label.

    Returns a dict with keys: toxicity, bias, disallowed, overall_score, label, debug
    """
    toxicity, bias, disallowed, debug = _score_components(text)

    overall = round((toxicity + bias + disallowed) / 3.0, 3)
    label = _overall_label(overall)

    return {
        "toxicity": toxicity,
        "bias": bias,
        "disallowed": disallowed,
        "overall_score": overall,
        "label": label,
        "debug": debug,
    }
