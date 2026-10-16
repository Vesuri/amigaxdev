# Standalone installer helpers

Canonical LGPL-2.1-or-later bounded StuffIt 13/Arsenic decoder, SHA-256,
platform I/O and startup extracted from Vette! and Alone in the Dark.
Game-specific archive manifests, layout and publication policy stay in adapters.
`decode.inc` uses the adapter's static buffers, error pointer and REQUIRE/TRY
macros. `install_config.h` supplies INSTALL_VERSION and INSTALL_USAGE.
Consumers vendor identical sources and pin hashes before compiling.
Existing donor trees are not changed by introducing this shared source.
