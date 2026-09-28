"""Narration: TTS voiceover, word timestamps, script alignment, cue lookup, subtitle chunks.

The script text is the source of truth for spelling; the transcriber only supplies timing.
"""
import difflib, json, os, re, urllib.request, uuid

_TOKEN = re.compile(r"[A-Za-z0-9@$'._+-]+")


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def tts(text, out_wav, key=None, model="gpt-4o-mini-tts", voice="ash", instructions=None):
    """OpenAI text-to-speech → WAV."""
    key = key or os.environ["OPENAI_API_KEY"]
    body = {"model": model, "voice": voice, "input": text, "response_format": "wav"}
    if instructions:
        body["instructions"] = instructions
    req = urllib.request.Request("https://api.openai.com/v1/audio/speech", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with open(out_wav, "wb") as f:
        f.write(urllib.request.urlopen(req, timeout=300).read())
    return out_wav


def transcribe_words(wav, key=None, prompt=None):
    """Whisper word timestamps: returns {"duration": s, "words": [{"word", "start", "end"}]}."""
    key = key or os.environ["OPENAI_API_KEY"]
    b = uuid.uuid4().hex
    fields = [("model", "whisper-1"), ("response_format", "verbose_json"), ("timestamp_granularities[]", "word")]
    if prompt:
        fields.append(("prompt", prompt))
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields]
    with open(wav, "rb") as f:
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="vo.wav"\r\n'
                     f'Content-Type: audio/wav\r\n\r\n'.encode() + f.read() + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request("https://api.openai.com/v1/audio/transcriptions", data=b"".join(parts),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": f"multipart/form-data; boundary={b}"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    return {"duration": r["duration"], "words": r["words"]}


def align(script, words):
    """Give every script token a (start, end) from the transcript. Unmatched tokens are interpolated.

    Returns [{"w": token_as_written, "start", "end", "punct": trailing punctuation}].
    """
    toks = []
    for m in re.finditer(r"(\S+)", script):
        raw = m.group(1)
        core = raw.rstrip(".,!?;:")
        toks.append({"w": core, "punct": raw[len(core):]})
    a = [norm(t["w"]) for t in toks]
    b = [norm(w["word"]) for w in words]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                toks[i1 + k]["start"], toks[i1 + k]["end"] = words[j1 + k]["start"], words[j1 + k]["end"]
        elif tag == "replace" and j2 > j1:            # spread the transcript span over the script tokens
            s, e = words[j1]["start"], words[j2 - 1]["end"]
            n = i2 - i1
            for k in range(n):
                toks[i1 + k]["start"] = s + (e - s) * k / n
                toks[i1 + k]["end"] = s + (e - s) * (k + 1) / n
    known = [i for i, t in enumerate(toks) if "start" in t]
    for i, t in enumerate(toks):                      # interpolate anything still missing
        if "start" not in t:
            lo = max([k for k in known if k < i], default=None)
            hi = min([k for k in known if k > i], default=None)
            s = toks[lo]["end"] if lo is not None else 0.0
            e = toks[hi]["start"] if hi is not None else s + 0.3
            t["start"], t["end"] = s, max(s + 0.05, e)
    return toks


def find(toks, phrase, after=0):
    """Index of the first token where `phrase` (a few words) starts, at or after token `after`."""
    p = [norm(x) for x in phrase.split()]
    for i in range(after, len(toks) - len(p) + 1):
        if [norm(toks[i + k]["w"]) for k in range(len(p))] == p:
            return i
    raise KeyError(f"cue '{phrase}' not found in script after token {after}")


def chunks(toks, max_words=3):
    """Subtitle chunks: split at punctuation into clauses, then each clause into balanced parts of
    ≤ max_words (so no orphaned single words). Returns [(start, end, text)]."""
    clauses, cur = [], []
    for t in toks:
        cur.append(t)
        if t["punct"]:
            clauses.append(cur)
            cur = []
    if cur:
        clauses.append(cur)
    out = []
    for cl in clauses:
        n = len(cl)
        parts = max(1, -(-n // max_words))
        size = -(-n // parts)
        for k in range(0, n, size):
            seg = cl[k:k + size]
            out.append([seg[0]["start"], seg[-1]["end"], " ".join(x["w"] + x["punct"] for x in seg)])
    for k in range(len(out) - 1):                     # hold each chunk until the next one starts (max +0.6 s)
        out[k][1] = min(out[k + 1][0], out[k][1] + 0.6)
    if out:
        out[-1][1] += 0.6
    return [tuple(c) for c in out]
