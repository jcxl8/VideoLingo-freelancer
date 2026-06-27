# macOS LaunchAgent auto-start

This guide shows how to start VideoLingo-Freelancer automatically after a macOS user logs in. It is useful for an always-on Mac mini, Mac Studio, or desktop machine where you want the Streamlit interface ready without opening Terminal.

This is optional and not required for normal use. If you are unsure, start the app manually instead:

```bash
.venv/bin/python -m streamlit run st.py
```

LaunchAgent files are machine-local operational configuration. Adjust paths for your own checkout and do not commit personal absolute paths, private log locations, cookies, API keys, or `.plist` files containing local-only settings.

## Before you start

Confirm the app starts manually first:

```bash
cd /absolute/path/to/VideoLingo-freelancer
.venv/bin/python -m streamlit run st.py
```

Create local log directories outside the repository or under an ignored runtime path:

```bash
mkdir -p "$HOME/Library/Logs/VideoLingo-freelancer"
```

## Streamlit LaunchAgent

Create `~/Library/LaunchAgents/com.jcxl8.videolingo-freelancer.streamlit.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.jcxl8.videolingo-freelancer.streamlit</string>

  <key>ProgramArguments</key>
  <array>
    <string>/absolute/path/to/VideoLingo-freelancer/.venv/bin/python</string>
    <string>-m</string>
    <string>streamlit</string>
    <string>run</string>
    <string>st.py</string>
    <string>--server.address</string>
    <string>127.0.0.1</string>
    <string>--server.port</string>
    <string>8501</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/absolute/path/to/VideoLingo-freelancer</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <false/>

  <key>StandardOutPath</key>
  <string>/Users/your-user/Library/Logs/VideoLingo-freelancer/streamlit.out.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/your-user/Library/Logs/VideoLingo-freelancer/streamlit.err.log</string>
</dict>
</plist>
```

Replace every `/absolute/path/to/VideoLingo-freelancer` and `/Users/your-user` value before loading the agent.

Load it:

```bash
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.jcxl8.videolingo-freelancer.streamlit.plist"
launchctl kickstart -k "gui/$(id -u)/com.jcxl8.videolingo-freelancer.streamlit"
```

Open the interface:

```bash
open http://127.0.0.1:8501
```

Unload it:

```bash
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.jcxl8.videolingo-freelancer.streamlit.plist"
```

## Optional Hy-MT2 local translator service

If you also run a local Hy-MT2 model server, start and verify it manually first. This repository includes portable helper scripts that avoid hard-coded user paths:

```bash
HYMT2_MODEL="/absolute/path/to/Hy-MT2-7B-or-gguf-model" \
LLAMA_SERVER="/absolute/path/to/llama-server" \
HYMT2_PORT=8765 \
scripts/start_hymt2_8765.sh
```

You can wrap the same command in a separate LaunchAgent. Keep it separate from Streamlit so one service can restart without hiding failures from the other.

Minimal template:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.jcxl8.videolingo-freelancer.hymt2</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd /absolute/path/to/VideoLingo-freelancer &amp;&amp; HYMT2_MODEL=/absolute/path/to/model.gguf LLAMA_SERVER=/absolute/path/to/llama-server HYMT2_PORT=8765 scripts/start_hymt2_8765.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/absolute/path/to/VideoLingo-freelancer</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>/Users/your-user/Library/Logs/VideoLingo-freelancer/hymt2.out.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/your-user/Library/Logs/VideoLingo-freelancer/hymt2.err.log</string>
</dict>
</plist>
```

Do not commit this file after replacing the placeholders. It will contain personal model paths and hardware-specific launch settings.

## Troubleshooting

Check whether an agent is loaded:

```bash
launchctl print "gui/$(id -u)/com.jcxl8.videolingo-freelancer.streamlit"
```

Watch logs:

```bash
tail -f "$HOME/Library/Logs/VideoLingo-freelancer/streamlit.err.log"
```

Common issues:

- The `.venv/bin/python` path is wrong or the environment was not created.
- `WorkingDirectory` points to an old checkout.
- Port `8501` or `8765` is already used.
- The local model service started, but `translator_api.base_url` in `config.yaml` points to a different port.
- A plist copied from another Mac still contains that machine's absolute paths.

When changing paths or environment variables, unload and bootstrap the agent again. `kickstart` alone may not reload a changed plist.
