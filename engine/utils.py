import re


def clean(s):
    s = str(s).lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    s = re.sub(r"\b(feat|ft|featuring)\b.*", "", s)
    s = re.sub(r"^the\s+", "", s)
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tag_value(audio, keys):
    for key in keys:
        val = audio.tags.get(key) if audio and audio.tags else None
        if val:
            if isinstance(val, list):
                return str(val[0])
            return str(val)
    return ""
