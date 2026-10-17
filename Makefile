# Shared Amiga development environment.  `make setup` installs everything; see README.md.
#
#   make setup TOSEC=<path or URL> AMIGA_OS=<path or URL> DEVCD=<path or URL>
#
# TOSEC, AMIGA_OS and DEVCD are only needed while a Kickstart, Workbench file or the Developer
# CD's manuals are missing or wrong.

PREFIX      ?= $(HOME)/.local
AMIGA_SHARE ?= $(PREFIX)/share/amiga
CACHE       ?= $(CURDIR)/tmp/cache
BUILD       ?= $(CURDIR)/tmp/build
export PREFIX AMIGA_SHARE CACHE BUILD TOSEC AMIGA_OS DEVCD

SETUP = scripts/setup.sh

# Order matters: python provides xdftool for os; brew provides unar, uv and the build tools.
CORE   = host brew python toolchain whdload ndk installer rtb kalms lha roms os devcd aga-guide share
EXTRAS = brew-extras fsuae-arm fsuae-aprof unicorn

.PHONY: help setup core extras check pull-shared $(CORE) $(EXTRAS)

help:
	@echo 'make setup         install everything (core + extras), then check'
	@echo 'make core          only what every project needs'
	@echo 'make check         verify the installed environment against the manifests'
	@echo 'make pull-shared   copy shared files edited in place back into this repo'
	@echo 'components:        $(CORE) $(EXTRAS)'
	@echo 'variables:         TOSEC, AMIGA_OS, DEVCD (sources), PREFIX=$(PREFIX), CACHE, BUILD'

setup: core extras check

core:
	@$(SETUP) $(CORE)

extras:
	@$(SETUP) $(EXTRAS)

$(CORE) $(EXTRAS):
	@$(SETUP) $@

pull-shared:
	@$(SETUP) pull-shared

check:
	@scripts/check.sh

.PHONY: test-mac-runtime
test-mac-runtime:
	@mkdir -p tmp/tests
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_slot_ranges.cpp -o tmp/tests/mac-slot-ranges
	@tmp/tests/mac-slot-ranges
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_deadline_beam.cpp -o tmp/tests/mac-deadline-beam
	@tmp/tests/mac-deadline-beam
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_audio_reuse.cpp -o tmp/tests/mac-audio-reuse
	@tmp/tests/mac-audio-reuse
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_heap_lock.cpp -o tmp/tests/mac-heap-lock
	@tmp/tests/mac-heap-lock
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_heap_state.cpp -o tmp/tests/mac-heap-state
	@tmp/tests/mac-heap-state
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined scripts/test_dirty_bands.cpp -o tmp/tests/dirty-bands
	tmp/tests/dirty-bands
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_blitter_completion.cpp -o tmp/tests/blitter-completion
	@tmp/tests/blitter-completion
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined scripts/test_heap_search.cpp -o tmp/tests/heap-search
	./tmp/tests/heap-search
	@mkdir -p tmp/tests
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_bitmap_region.cpp -o tmp/tests/mac-bitmap-region
	@tmp/tests/mac-bitmap-region
	@mkdir -p tmp/tests
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_runtime.cpp -o tmp/tests/mac-runtime
	@tmp/tests/mac-runtime
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_fonts.cpp -o tmp/tests/mac-fonts
	@tmp/tests/mac-fonts
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_graphics.cpp -o tmp/tests/mac-graphics
	@tmp/tests/mac-graphics
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_rgb_cache.cpp -o tmp/tests/mac-rgb-cache
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_pen_rect.cpp -o tmp/tests/mac-pen-rect
	@tmp/tests/mac-pen-rect
	@tmp/tests/mac-rgb-cache
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -DAMIGAXDEV_REGION_UNION -Ishare/mac-runtime scripts/test_mac_graphics.cpp -o tmp/tests/mac-graphics-union
	@tmp/tests/mac-graphics-union
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_memory.cpp -o tmp/tests/mac-memory
	@tmp/tests/mac-memory
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_code_ranges.cpp -o tmp/tests/mac-code-ranges
	@tmp/tests/mac-code-ranges
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_pcm.cpp -o tmp/tests/mac-pcm
	@tmp/tests/mac-pcm
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_vbl_passes.cpp -o tmp/tests/mac-vbl-passes
	@tmp/tests/mac-vbl-passes
	$(CXX) -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -Ishare/mac-runtime scripts/test_mac_video_ticks.cpp -o tmp/tests/mac-video-ticks
	@tmp/tests/mac-video-ticks
