# Third-party notices

The repository contains **no executables and no model files**. Programs and models are downloaded at install time
from their official sources, after you type yes, and are checked against a SHA-256 (or Hugging Face git hash).
Each keeps its own licence; you accept those licences when you install them.

## Included in this repository (web assets of the HomeAI app)

Licence texts are in `payload/homeai/static/vendor/licenses/`.

| Component | Use | Licence |
|---|---|---|
| marked | Markdown rendering | MIT |
| DOMPurify | HTML sanitising | Apache-2.0 or MPL-2.0 (dual) |
| highlight.js | Code highlighting | BSD-3-Clause |
| KaTeX (JS, CSS, fonts) | Maths rendering | MIT |
| Inter font | UI font | SIL Open Font License 1.1 |
| JetBrains Mono font | Code font | SIL Open Font License 1.1 |
| SearXNG compose file and settings template (`payload/searxng/`) | Configuration for the SearXNG container | Written for this kit (MIT). SearXNG itself is AGPL-3.0 (see below) |
| Sysmon rule additions (`payload/security/sysmon-override.template.xml`) | Extra logging rules | Written for this kit (MIT) |

## Downloaded at install time (not redistributed)

| Component | Source | Licence |
|---|---|---|
| llama.cpp (`llama-server` and libraries; CPU, Vulkan or CUDA build) | github.com/ggml-org/llama.cpp releases | MIT |
| NVIDIA CUDA runtime DLLs (Windows CUDA build only, `cudart-*.zip` from the same llama.cpp release) | github.com/ggml-org/llama.cpp releases | NVIDIA CUDA Toolkit EULA (redistributable runtime) |
| Python 3.12 for Windows (NuGet `python` / `pythonarm64` package) | nuget.org | Python Software Foundation License 2.0 (includes components under their own licences, e.g. OpenSSL Apache-2.0, zlib, libffi MIT) |
| AI models (GGUF files you choose) | huggingface.co | Each model's own licence (e.g. Apache-2.0, MIT, Llama, Gemma, Qwen licences) - shown on the model page linked during setup. **Check it before use.** |
| **Voice (optional)** faster-whisper | PyPI | MIT |
| CTranslate2 (dependency of faster-whisper) | PyPI | MIT |
| Whisper small.en model, CTranslate2 conversion (`Systran/faster-whisper-small.en`) | huggingface.co | MIT (OpenAI Whisper weights are MIT) |
| kokoro-onnx | PyPI | MIT |
| Kokoro-82M model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`, from the kokoro-onnx `model-files-v1.0` release) | github.com/thewh1teagle/kokoro-onnx | Apache-2.0 (hexgrad/Kokoro-82M) |
| espeak-ng (bundled inside the `espeakng-loader` package used by kokoro-onnx) | PyPI | GPL-3.0-or-later |
| phonemizer-fork, onnxruntime, numpy and other pip dependencies | PyPI | Their own licences (mostly MIT / BSD / Apache-2.0) |
| **Web search (optional)** SearXNG container image `searxng/searxng` | Docker Hub | AGPL-3.0. Runs unmodified, locally, for your own use |
| **Coding agent (optional)** OpenHands Agent Canvas image `ghcr.io/openhands/agent-canvas:1.33.0` | GitHub Container Registry | MIT (OpenHands core; see the OpenHands repository for any separately licensed parts) |
| Docker Desktop / Docker Engine (installed by you, not by the kit) | docker.com | Docker's own terms (Docker Desktop has a subscription agreement for larger companies) |
| **Security Monitor (optional, Windows)** Sysmon | download.sysinternals.com (Microsoft) | Sysinternals Software License Terms. Downloaded by `Install-All.cmd` and installed only if Microsoft's signature is valid; never redistributed |
| sysmon-modular configuration (pinned release, SHA-256 checked) | github.com/olafhartong/sysmon-modular | MIT |
| DB-IP "IP to Country Lite" and "IP to ASN Lite" databases | download.db-ip.com | CC BY 4.0 - **IP geolocation by [DB-IP](https://db-ip.com)** |

## Attribution required by CC BY 4.0

The Security Monitor shows country and network-owner information from the free DB-IP Lite databases:
IP Geolocation by DB-IP (https://db-ip.com), licensed under the Creative Commons Attribution 4.0 International
License (https://creativecommons.org/licenses/by/4.0/).
