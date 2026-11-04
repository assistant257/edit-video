# GitHub Actions video review

Manual workflow: Render captioned video review. Requires an accessible Drive URL and explicit consent for repository readers to download the artifact. A public repository does not provide a private delivery channel: signed-in GitHub readers may download artifacts. Do not commit source videos, transcript, credentials or private download tokens. Artifacts expire after three days. No release or social publishing is configured.

The first output is a full-length, natural-speed H.264/AAC MP4 with Vietnamese phrase captions from real ASR timing, plus SRT/ASS/JSON and review flags. It retains the original aspect ratio and audio; it does not invent B-roll, music, quotes, logos, or cut speech based only on a guessed transcript. Automatic subtitles and placement require human audiovisual review before publication. This workflow is preparation, not proof that a render has succeeded.

A source accessible only to a connected Drive account cannot be fetched by an unauthenticated GitHub runner. Keep Drive permissions unchanged unless the owner explicitly authorizes another access method.

Local: install FFmpeg, Noto Sans, faster-whisper 1.2.1, then `python scripts/render_video.py --source input.mov --output output`. The cloud workflow also uses gdown 5.2.0. Model download and render require network and compute. No paid API is configured.
