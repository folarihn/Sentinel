# Licensing and bundled material

Sentinel's own source code is MIT licensed. LICENSE contains the complete grant
with Copyright (c) 2026 folarihn. Bundled IBM Plex Sans, IBM Plex Mono, and Space
Grotesk fonts are unmodified third-party works under the SIL Open Font License
1.1. The package license expression is MIT AND OFL-1.1 to account for both.

Font copyright notices and complete licenses accompany the binaries under
sentinel/web/fonts/. [Third-party notices](../THIRD_PARTY_NOTICES.md) identify
the immutable upstream sources. Fonts are served locally; no external font
service is contacted while the Control Room runs. Reliable system fallbacks
remain available while fonts load or if a local asset cannot be loaded.

The runtime declares no mandatory third-party Python dependencies. No vendored
JavaScript library, icon pack or third-party audio is bundled. Interface icons
use text and CSS. Documentation screenshots are genuine interface captures.
Build/test tools and Hermes are separately installed software with their own
licenses. Sentinel's MIT grant does not relicense those works or the font assets.
