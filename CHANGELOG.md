# Changelog

## 2026-11-10

- **OpenHands** now uses the official Agent Canvas image `ghcr.io/openhands/agent-canvas:1.38.0` (was 1.33.0). Re-run setup, or pull the new image and recreate the container, to switch an existing install.
- **Stop a running OpenHands task** without stopping the container or the AI engine: `python openhands_ctl.py stop-task`, or the new `Stop-OpenHands-Task.ps1` / `stop-openhands-task.sh` helpers in `extras/openhands`. These call the OpenHands interrupt API.
- **16,384-token reply cap.** New installs write `n-predict = 16384` in the `[*]` section of `engine/models.ini`. A client's `max_tokens` still overrides this. OpenHands `max_output_tokens` now uses `min(16384, max(1024, ctx // 2))`, so a 32k-context model can use the full 16,384-token cap (it was previously limited to `ctx // 4`). Existing `models.ini` files are not rewritten until you add a mode or re-run setup; you can add the `n-predict` line yourself.
- **llama.cpp:** setup still installs the newest matching official build when you update the engine. A newer build is not always faster. In testing, b12244 was slower than b11840 on Vulkan (prompt about 485–617 vs 1138 tokens/s, generation 62–64 vs 73 tokens/s, and about 0.75 GB more shared memory). If a new build feels slower, keep the known-good copy; setup only replaces the engine when you run it again.
- HomeAI's model picker already unloads a loaded model with `POST /models/unload` and leaves the llama-server router running. There is no separate "Release AI Models" script in this kit.
