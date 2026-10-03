# Licensing

Callback is Apache-2.0 (see `LICENSE`). The Silero VAD model bundled for voice
activity detection is MIT-licensed (see `NOTICE`). The report embeds a subset of the
Bricolage Grotesque typeface for its headings, licensed under the SIL Open Font License 1.1
(see `NOTICE` and `src/callback_voice/report/assets/display-font-OFL.txt`).

The local speech models are an optional extra, `pip install "callback-voice[local]"`:

| Package | Used for | License |
|---|---|---|
| faster-whisper | speech recognition | MIT |
| kokoro-onnx | the caller's and reference agent's voice | MIT |
| espeak-ng (system package) | turns text into phonemes for Kokoro | GPL-3.0 |

espeak-ng is not installed by pip: it is a separate program (`brew install espeak-ng`,
`sudo apt install espeak-ng`). Because it is GPL-3.0, the voice stays an opt-in extra
and Callback itself does not depend on it. `callback doctor` checks for it, and
`callback demo` tells you how to install it if it is missing.

The Piper extra (`callback-voice[piper]`) is GPL-3.0 as well and equally optional.
