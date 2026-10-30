"""The modes HomeAI can have. A fresh install has General and Coding; everything else is added later with
"+ Add mode" (in the HomeAI window or with the setup script). Each mode = a preset button in HomeAI, a routing
profile + rule, and (usually) a model chosen for it by the Hugging Face search."""
from __future__ import annotations

BASE_PARAMS = {"temperature": 0.7, "top_p": 0.9, "top_k": 40, "min_p": 0.05, "max_tokens": 0, "repeat_penalty": 1.0, "seed": -1}

RESEARCH_SYSTEM = ("You are a careful research assistant. Cite a source (author/title/URL) for every factual claim you make. "
                   "Clearly separate established fact, scholarly consensus, minority views and speculation. If you are unsure "
                   "or no source is available, say so plainly instead of guessing. Prefer primary sources and peer-reviewed scholarship.")

UNC = ["abliterated", "uncensored", "heretic"]

# search: list of (search text, author or None). {u} is replaced by each uncensored keyword.
# prefer / avoid: regex on the repo id (lower case). vision: needs an mmproj (image encoder) file.
MODES = {
    "general": {
        "label": "General", "color": "#6366f1", "icon": "globe", "category": "general", "thinking": "off",
        "desc": "Everyday chat, questions, explanations and ideas.",
        "system": "You are HomeAI, a helpful, knowledgeable and concise assistant running locally. Use Markdown (headings, lists, tables, LaTeX with $...$) when it improves clarity.",
        "params": dict(BASE_PARAMS),
        "search_uncensored": [("{u}", None), ("instruct {u}", None), ("it {u}", None)],
        "search_standard": [("instruct", "unsloth"), ("instruct", "bartowski"), ("it-GGUF", "unsloth"), ("instruct", "lmstudio-community"), ("", "ggml-org")],
        "prefer": r"instruct|-it[-_.]|chat",
        "avoid": r"coder|code-|caption|embed|rerank|guard|math-|-vl-|vision|ocr|tts|audio|whisper|base-gguf|-base[-_.]",
        "rules": {"temperature": 0.7, "top_p": 0.9, "thinking": "off"},
    },
    "coding": {
        "label": "Coding", "color": "#10b981", "icon": "code", "category": "coding", "thinking": "auto",
        "desc": "Code, scripts, refactors and debugging.",
        "system": "You are an expert software engineer. Write correct, idiomatic, production-quality code. Always use fenced code blocks with a language tag. Briefly explain the approach, then show the code. Point out edge cases and pitfalls.",
        "params": dict(BASE_PARAMS, temperature=0.2, repeat_penalty=1.05),
        "search_uncensored": [("coder {u}", None), ("code {u}", None), ("devstral {u}", None), ("{u}", None)],
        "search_standard": [("coder", "unsloth"), ("coder", "bartowski"), ("coder", "lmstudio-community"), ("devstral", None), ("coder", "ggml-org")],
        "prefer": r"coder|code|devstral|starcoder|codestral",
        "avoid": r"caption|embed|rerank|guard|-vl-|vision|ocr|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.6, "top_p": 0.95, "thinking": "auto"},
    },
    "writing": {
        "label": "Writing", "color": "#ec4899", "icon": "feather", "category": "writing", "thinking": "off",
        "desc": "Stories, emails, essays, rewrites and role-play.",
        "system": "You are a skilled writer and editor. Match the requested tone and format, write vividly and naturally, and keep characters and facts consistent.",
        "params": dict(BASE_PARAMS, temperature=0.85, top_p=0.95),
        "search_uncensored": [("{u}", None), ("creative {u}", None), ("roleplay", None), ("writer", None)],
        "search_standard": [("instruct", "unsloth"), ("instruct", "bartowski"), ("writer", None)],
        "prefer": r"creative|writer|story|roleplay|rp[-_]|instruct|-it[-_.]",
        "avoid": r"coder|code-|caption|embed|rerank|guard|math-|-vl-|ocr|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.85, "top_p": 0.95, "thinking": "off"},
    },
    "vision": {
        "label": "Vision", "color": "#f59e0b", "icon": "eye", "category": "vision", "thinking": "off", "vision": True,
        "desc": "Ask about images, screenshots and documents (reads text in pictures).",
        "system": "You are a precise visual assistant. Answer questions about the provided images accurately; transcribe text exactly when asked.",
        "params": dict(BASE_PARAMS, temperature=0.5),
        "search_uncensored": [("vl {u}", None), ("vision {u}", None), ("gemma {u}", None), ("{u}", None)],
        "search_standard": [("vl", "unsloth"), ("vl", "bartowski"), ("gemma", "unsloth"), ("vl", "ggml-org"), ("gemma", "ggml-org")],
        "prefer": r"-vl|vl-|vision|gemma|pixtral|llava|minicpm-v|multimodal|omni",
        "avoid": r"coder|embed|rerank|guard|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.5, "top_p": 0.9, "thinking": "off"},
    },
    "reasoning": {
        "label": "Reasoning", "color": "#ef4444", "icon": "brain", "category": "reasoning", "thinking": "on",
        "desc": "Maths, logic and hard problems (thinks before answering, slower).",
        "system": "You are a world-class expert problem solver. Think carefully, check your work, and give a clear, well-justified final answer.",
        "params": dict(BASE_PARAMS, temperature=0.6, top_p=0.95, min_p=0.0),
        "search_uncensored": [("thinking {u}", None), ("reasoning {u}", None), ("{u}", None)],
        "search_standard": [("thinking", "unsloth"), ("reasoning", "bartowski"), ("thinking", "bartowski"), ("", "ggml-org")],
        "prefer": r"think|reason|r1|qwq|magistral|gpt-oss",
        "avoid": r"caption|embed|rerank|guard|-vl-|ocr|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.6, "top_p": 0.95, "thinking": "on"},
    },
    "research": {
        "label": "Research", "color": "#0ea5e9", "icon": "sparkles", "category": "research", "thinking": "on",
        "desc": "Careful answers that cite sources (works best with Web search on).",
        "system": RESEARCH_SYSTEM,
        "params": dict(BASE_PARAMS, temperature=0.6, top_p=0.95),
        "search_uncensored": [("{u}", None), ("thinking {u}", None)],
        "search_standard": [("instruct", "unsloth"), ("thinking", "unsloth"), ("instruct", "bartowski")],
        "prefer": r"instruct|think|-it[-_.]",
        "avoid": r"coder|caption|embed|rerank|guard|-vl-|ocr|tts|audio|whisper|roleplay|-base[-_.]",
        "rules": {"temperature": 0.6, "top_p": 0.95, "thinking": "on", "system": RESEARCH_SYSTEM},
        "min_ctx": 32768,
    },
    "long": {
        "label": "Long documents", "color": "#14b8a6", "icon": "layers", "category": "long", "thinking": "off",
        "desc": "Big documents, long chats and large code files (needs a long memory).",
        "system": "You are a careful assistant for long documents. Quote the relevant passage when you answer and say where it is.",
        "params": dict(BASE_PARAMS, temperature=0.5),
        "search_uncensored": [("a3b {u}", None), ("moe {u}", None), ("{u}", None)],
        "search_standard": [("a3b", "unsloth"), ("instruct", "unsloth"), ("instruct", "bartowski")],
        "prefer": r"a\d+b|moe|instruct|1m|128k",
        "avoid": r"caption|embed|rerank|guard|-vl-|ocr|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.5, "top_p": 0.9, "thinking": "off"},
        "min_ctx": 65536,
    },
    "imageprompt": {
        "label": "Image prompts", "color": "#a855f7", "icon": "image", "category": "imageprompt", "thinking": "off",
        "desc": "Prompts for image and video generators (Stable Diffusion, Flux, ComfyUI...).",
        "system": "You write prompts for text-to-image and text-to-video models. Give one ready-to-paste prompt (and a negative prompt when useful), then a one-line note on settings.",
        "params": dict(BASE_PARAMS, temperature=0.9, top_p=0.95),
        "search_uncensored": [("{u}", None), ("creative {u}", None)],
        "search_standard": [("instruct", "unsloth"), ("instruct", "bartowski")],
        "prefer": r"creative|instruct|-it[-_.]",
        "avoid": r"coder|caption|embed|rerank|guard|-vl-|ocr|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.9, "top_p": 0.95, "thinking": "off"},
    },
    "caption": {
        "label": "Captions", "color": "#06b6d4", "icon": "image", "category": "caption", "thinking": "off", "vision": True,
        "desc": "Drop in an image, get a detailed description or tags.",
        "system": "You are a helpful image captioner. Describe the image in detail: subjects, clothing, pose, setting, lighting, style and composition.",
        "starter": "Write a long descriptive caption for this image.",
        "params": dict(BASE_PARAMS, temperature=0.6, max_tokens=512),
        "search_uncensored": [("caption", None), ("captioner", None), ("vl {u}", None)],
        "search_standard": [("caption", None), ("vl", "unsloth"), ("gemma", "ggml-org")],
        "prefer": r"caption|tagger|-vl|vision|llava",
        "avoid": r"coder|embed|rerank|guard|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.6, "top_p": 0.9, "thinking": "off", "max_tokens": 512},
    },
    "music": {
        "label": "Music", "color": "#f97316", "icon": "zap", "category": "music", "thinking": "off",
        "desc": "Lyrics, song ideas, chords, tempo and prompts for music generators.",
        "system": "You are a songwriter and music producer. Help with lyrics, structure, chords, tempo and sound design; give prompts for music generators when asked.",
        "params": dict(BASE_PARAMS, temperature=0.9, top_p=0.95),
        "search_uncensored": [("{u}", None), ("creative {u}", None)],
        "search_standard": [("instruct", "unsloth"), ("instruct", "bartowski")],
        "prefer": r"creative|writer|instruct|-it[-_.]",
        "avoid": r"coder|caption|embed|rerank|guard|-vl-|ocr|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.9, "top_p": 0.95, "thinking": "off"},
    },
    "android": {
        "label": "App building", "color": "#22c55e", "icon": "cpu", "category": "android", "thinking": "auto",
        "desc": "Android / mobile app development (Kotlin, Compose, Gradle).",
        "system": "You are an expert mobile app developer (Android, Kotlin, Jetpack Compose, Gradle). Give complete, working code and exact steps.",
        "params": dict(BASE_PARAMS, temperature=0.3),
        "search_uncensored": [("coder {u}", None), ("{u}", None)],
        "search_standard": [("coder", "unsloth"), ("coder", "bartowski")],
        "prefer": r"coder|code|devstral",
        "avoid": r"caption|embed|rerank|guard|-vl-|ocr|tts|audio|whisper|-base[-_.]",
        "rules": {"temperature": 0.6, "top_p": 0.95, "thinking": "auto"},
    },
}

STARTER_MODES = ("general", "coding")
OPTIONAL_MODES = [k for k in MODES if k not in STARTER_MODES]


def preset_for(key):
    m = MODES[key]
    return {"id": key, "name": m["label"], "color": m["color"], "icon": m["icon"], "model": "@" + key,
            "thinking": m.get("thinking", "auto"), "starter": m.get("starter", ""), "desc": m["desc"],
            "system": m["system"], "params": dict(m["params"])}


def catalog():
    return [{"key": k, "label": v["label"], "desc": v["desc"], "vision": bool(v.get("vision")), "starter": k in STARTER_MODES}
            for k, v in MODES.items()]
