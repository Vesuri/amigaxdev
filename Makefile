# Shared Amiga development environment.  `make setup` installs everything; see README.md.
#
#   make setup TOSEC=<path or URL> AMIGA_OS=<path or URL>
#
# TOSEC and AMIGA_OS are only needed while a Kickstart or Workbench file is missing or wrong.

PREFIX      ?= $(HOME)/.local
AMIGA_SHARE ?= $(PREFIX)/share/amiga
CACHE       ?= $(CURDIR)/tmp/cache
BUILD       ?= $(CURDIR)/tmp/build
export PREFIX AMIGA_SHARE CACHE BUILD TOSEC AMIGA_OS

SETUP = scripts/setup.sh

# Order matters: python provides xdftool for os; brew provides unar, uv and the build tools.
CORE   = host brew python toolchain whdload ndk installer rtb kalms lha roms os share
EXTRAS = brew-extras fsuae-arm fsuae-aprof

.PHONY: help setup core extras check pull-shared $(CORE) $(EXTRAS)

help:
	@echo 'make setup         install everything (core + extras), then check'
	@echo 'make core          only what every project needs'
	@echo 'make check         verify the installed environment against the manifests'
	@echo 'make pull-shared   copy shared files edited in place back into this repo'
	@echo 'components:        $(CORE) $(EXTRAS)'
	@echo 'variables:         TOSEC, AMIGA_OS (sources), PREFIX=$(PREFIX), CACHE, BUILD'

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
