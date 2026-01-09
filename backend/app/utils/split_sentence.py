import re

def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    sentences = re.split(r'(?<=[\.\!\?…])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]