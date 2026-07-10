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


def _compose_text_explanation(text: str, toxicity: float, bias: float, disallowed: float, debug: Dict) -> str:
    parts: List[str] = []
    scores = {"toxicity": toxicity, "bias": bias, "disallowed": disallowed}
    dominant = max(scores, key=scores.get)
    # Plain-language headline
    if scores[dominant] >= 0.35:
        parts.append(f"The main concern is {dominant}.")
    else:
        parts.append("No single strong concern; there are several low-to-moderate signals.")

    # Short, human-friendly evidence line
    evidence: List[str] = []
    if debug.get("toxicity_kw"):
        evidence.append(f"{debug['toxicity_kw']} rude word(s)")
    if debug.get("insult_kw"):
        evidence.append(f"{debug['insult_kw']} insult(s)")
    if debug.get("disallowed_kw"):
        evidence.append(f"{debug['disallowed_kw']} risky term(s)")
    if debug.get("threat_matches"):
        evidence.append(f"{debug['threat_matches']} threat phrase(s)")

    if evidence:
        parts.append("What we saw: " + ", ".join(evidence) + ".")
    else:
        parts.append("What we saw: no obvious bad words; judgement came from patterns in the text.")

    parts.append("Suggested action: review the text and remove or flag if it seems harmful.")
    return "\n".join(parts)


def _compose_image_explanation(features: Dict[str, float]) -> str:
    parts: List[str] = []
    if features.get("red_ratio", 0) > 0.6:
        parts.append("The image has strong red/dark tones, which can indicate graphic content.")
    if features.get("avg_saturation", 0) > 0.6:
        parts.append("The image is very colorful/intense, increasing visual risk signals.")
    if features.get("brightness", 1) < 0.45:
        parts.append("The image is quite dark, which raises the risk score.")
    if not parts:
        parts.append("The image looks visually benign by simple checks.")
    parts.append("Suggested action: inspect the image and remove or flag if it appears harmful.")
    return "\n".join(parts)


def _compose_video_explanation(debug: Dict) -> str:
    parts: List[str] = []
    dur = debug.get("duration_seconds")
    frames = debug.get("frame_scores", [])
    motion = debug.get("motion_score", 0.0)

    # Average frame metrics
    if frames:
        avg_graphic = sum(f.get("graphic", 0) for f in frames) / len(frames)
        avg_violence = sum(f.get("violence", 0) for f in frames) / len(frames)
    else:
        avg_graphic = avg_violence = 0.0

    # Plain-language summary lines (3-4 short lines)
    if avg_graphic >= 0.5:
        parts.append("Sampled frames show strong red/dark visual cues that often match graphic images.")
    elif avg_violence >= 0.35:
        parts.append("Sampled frames contain visual cues that may indicate violence.")
    else:
        parts.append("Sampled frames look visually benign.")

    # Motion description
    if motion > 0.4:
        motion_desc = "high"
    elif motion > 0.15:
        motion_desc = "moderate"
    else:
        motion_desc = "low"
    parts.append(f"Motion in the clip is {motion_desc}, which affects how we interpret the visuals.")

    parts.append("Suggested action: review the clip and remove or flag if it seems harmful.")
    return "\n".join(parts)


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
        "explanation": _compose_text_explanation(text, toxicity, bias, disallowed, debug),
    }


def _image_feature_scores(image_bytes: bytes) -> Dict[str, float]:
    from io import BytesIO
    from PIL import Image, ImageStat

    try:
        image = Image.open(BytesIO(image_bytes))
    except Exception as exc:
        raise ValueError(f"Unable to decode image: {exc}")

    image = image.convert("RGB")
    width, height = image.size
    rgb_stats = ImageStat.Stat(image)
    avg_r, avg_g, avg_b = [val / 255.0 for val in rgb_stats.mean]

    hsv_image = image.convert("HSV")
    hsv_stats = ImageStat.Stat(hsv_image)
    avg_h = hsv_stats.mean[0] * 360.0 / 255.0
    avg_s = hsv_stats.mean[1] / 255.0
    avg_v = hsv_stats.mean[2] / 255.0

    red_dist = min(avg_h, 360.0 - avg_h)
    redness = max(0.0, 1.0 - red_dist / 45.0)
    red_ratio = avg_r / max(avg_r + avg_g + avg_b, 1e-6)
    darkness = max(0.0, 0.4 - avg_v) / 0.4
    small_image_bonus = 0.2 if width * height < 160_000 else 0.0

    graphic = min(1.0, redness * avg_s * 1.5 + darkness * 0.7 + small_image_bonus)

    red_component = max(0.0, red_ratio - 0.32) * 0.35
    redness_component = max(0.0, redness - 0.15) * 0.25
    darkness_component = max(0.0, darkness - 0.1) * 0.35
    violence = min(1.0, red_component + redness_component + darkness_component)

    if avg_v > 0.6 and avg_s > 0.3:
        violence *= 0.55
    if avg_v > 0.75:
        violence *= 0.7
    if red_ratio < 0.45 and avg_s < 0.7 and avg_v > 0.6:
        violence *= 0.7

    nsfw = min(1.0, avg_s * 0.6 + darkness * 0.4)

    return {
        "graphic": round(graphic, 3),
        "violence": round(violence, 3),
        "nsfw": round(nsfw, 3),
        "red_ratio": round(red_ratio, 3),
        "avg_saturation": round(avg_s, 3),
        "brightness": round(avg_v, 3),
        "size": width * height,
    }


def score_image_bytes(image_bytes: bytes) -> Dict[str, object]:
    features = _image_feature_scores(image_bytes)
    overall = round((features["graphic"] + features["violence"] + features["nsfw"]) / 3.0, 3)
    label = _overall_label(overall)
    return {
        "graphic": features["graphic"],
        "violence": features["violence"],
        "nsfw": features["nsfw"],
        "overall_score": overall,
        "label": label,
        "debug": {
            "red_ratio": features["red_ratio"],
            "avg_saturation": features["avg_saturation"],
            "brightness": features["brightness"],
            "size": features["size"],
        },
        "explanation": _compose_image_explanation(features),
    }


def score_video_bytes(video_bytes: bytes) -> Dict[str, object]:
    import os
    import tempfile
    from io import BytesIO
    from PIL import Image
    import numpy as np

    try:
        from moviepy import VideoFileClip  # type: ignore
    except Exception:
        try:
            from moviepy.video.io.VideoFileClip import VideoFileClip  # type: ignore
        except Exception as exc:
            raise ValueError(f"MoviePy is required to score videos: {exc}")

    temp_path = None
    frames = []
    frame_scores = []
    duration = 1.0
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_file.write(video_bytes)
            temp_path = tmp_file.name

        clip = VideoFileClip(temp_path)
        duration = max(clip.duration, 1.0)

        # choose up to 3 sample times spread across the clip
        sample_times = [duration / 2.0]
        if duration > 1.0:
            sample_times = [max(0.1, duration * 0.25), duration / 2.0, min(duration - 0.1, duration * 0.75)]

        for t in sample_times:
            try:
                f = clip.get_frame(t)
            except Exception:
                f = None
            if f is not None:
                frames.append(f)
                img = Image.fromarray(f)
                b = BytesIO()
                img.save(b, format="PNG")
                b.seek(0)
                frame_scores.append(score_image_bytes(b.getvalue()))

        clip.close()
    except Exception as exc:
        raise ValueError(f"Unable to decode video: {exc}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

    if not frame_scores:
        raise ValueError("Unable to extract usable frames from the video")

    # Aggregate frame-level metrics
    avg_violence = float(sum(f["violence"] for f in frame_scores) / len(frame_scores))
    avg_graphic = float(sum(f["graphic"] for f in frame_scores) / len(frame_scores))
    avg_nsfw = float(sum(f["nsfw"] for f in frame_scores) / len(frame_scores))

    # motion score: mean pixel difference between consecutive frames
    motion_score = 0.0
    if len(frames) > 1:
        diffs = []
        for a, b in zip(frames, frames[1:]):
            arr_a = np.asarray(a).astype(float)
            arr_b = np.asarray(b).astype(float)
            diffs.append(float(np.mean(np.abs(arr_a - arr_b)) / 255.0))
        motion_score = min(1.0, float(sum(diffs) / len(diffs)) * 1.5)

    duration_score = min(1.0, duration / 10.0)

    # Blend signals: give weight to frame violence, motion, and duration
    violence = round(min(1.0, avg_violence * 0.65 + motion_score * 0.2 + duration_score * 0.15), 3)
    nsfw = round(min(1.0, avg_nsfw * 0.7 + duration_score * 0.2), 3)
    graphic = round(min(1.0, avg_graphic * 0.8 + duration_score * 0.1), 3)
    overall = round((graphic + violence + nsfw) / 3.0, 3)
    label = _overall_label(overall)

    return {
        "graphic": graphic,
        "violence": violence,
        "nsfw": nsfw,
        "overall_score": overall,
        "label": label,
        "debug": {
            "duration_seconds": round(duration, 2),
            "sample_times": [round(float(t), 2) for t in (sample_times if 'sample_times' in locals() else [duration / 2.0])],
            "frame_scores": frame_scores,
            "motion_score": round(float(motion_score), 3),
        },
        "explanation": _compose_video_explanation({
            "duration_seconds": round(duration, 2),
            "frame_scores": frame_scores,
            "motion_score": round(float(motion_score), 3),
        }),
    }
