# Third-Party Notices

This file records only attribution and versions verified from repository files.
It is not a substitute for the upstream licence texts.

## Verified Project Dependencies

- `audio-separator 0.47.0` — separation library; project:
  <https://github.com/nomadkaraoke/python-audio-separator>.
- `PySide6 6.11.2` — Qt Python bindings; project:
  <https://www.qt.io/qt-for-python>.
- `soundfile 0.14.0` — direct audio I/O dependency recorded in
  `requirements/macos-arm64.lock`.

The version file above is a direct pinned inventory, not a complete transitive
hash lock. This notice does not infer licence terms from package names or URLs.

## Pending Redistribution Information

- Selected UVR models: payloads, sources, sizes and SHA-256 are inventoried;
  licences of the weights still require verification.
- ffmpeg / ffprobe: Homebrew ffmpeg formula currently states GPL-3.0-or-later
  and depends on x264 and x265 (GPL-2.0-or-later). Installed versions and hashes
  are recorded by the macOS build. This is **not** a completed GPL source/notice
  compliance assessment; the binaries remain non-distributable publicly here.
- Homebrew dylibs: the personal build records individual formula source,
  version, licence, byte size and SHA-256 after relocation into the `.app`.
- Transitive macOS arm64 dependencies: pending a complete lock with verified
  hashes generated on macOS arm64.

No public release is permitted until model licences and GPL obligations for
the complete binary dependency closure have been handled and all gates pass.
