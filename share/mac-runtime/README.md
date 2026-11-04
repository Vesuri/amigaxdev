# Shared Macintosh runtime helpers

Canonical services for Macintosh ports, including several reusable Amiga display,
audio and memory helpers. Choose the relevant group; read only its contracts and source.
Game-specific trap ABI, ownership checks and publication remain in the consumer.

| Need | Helpers (contracts) |
|---|---|
| Rectangles, fonts, drawing and regions | [RectBounds](catalogue.md#rectboundsh), [BitmapFont / BitmapText8](catalogue.md#bitmapfonth), [GWorld8 / CopyBits8 / FillRect8 / regions](catalogue.md#gworld8h), [PenRect8](catalogue.md#penrect8h), [BitmapRegion](catalogue.md#bitmapregionh) |
| Changed-row copies and C2P planning | [CopyChangedRows](catalogue.md#copychangedrowsinc), [DirtyBands](catalogue.md#dirtybandsh), [namespace adapters](catalogue.md#dirtybandsaligninc) |
| QuickDraw caches | [RegionResultCache](catalogue.md#regionresultcacheh), [RGBColorCache](catalogue.md#rgbcolorcacheh), [region validation](catalogue.md#region-validation-cache) |
| Memory access and bounds | [BigEndianMemory](catalogue.md#bigendianmemoryh), [AddressSpan](catalogue.md#addressspanh); `BlockMoveBytes.h`, `BlockMoveChecks.h`, `ForwardLongCopy.inc` document copy contracts in source |
| CODE, resource and identity lookup | [CodeRangeCache](catalogue.md#coderangecacheh), [ResourceDirectory](catalogue.md#resourcedirectoryh), [ResourceWriter / ResourceStage](catalogue.md#resourcewriterinc), [IdentityIndexCache](catalogue.md#identityindexcacheh) |
| Native high-pointer regression | [StripAddressChecks](catalogue.md#stripaddresschecksh) |
| Heap allocation and handles | [HeapMoveHigh](catalogue.md#heapmovehighinc), [HeapClearLow](catalogue.md#heapclearlowinc), [HeapResize](catalogue.md#heapresizeinc), [HeapFindSpace](catalogue.md#heapfindspaceinc), [HandleCopy](catalogue.md#handlecopyh), [HeapLockHandle](catalogue.md#heaplockhandleinc), [HeapReadHandleState](catalogue.md#heapreadhandlestateinc), [PinnedSlotRanges](catalogue.md#pinnedslotrangesh) |
| VBL callbacks and clocks | [VBLPasses](catalogue.md#vblpassesh), [VideoTicks](catalogue.md#videoticksh), [PAL deadlines](catalogue.md#pal-beam-deadlines) |
| Audio conversion, reuse and DMA lifecycle | [PcmDma](catalogue.md#pcmdmainc), [UnsignedDivide](catalogue.md#unsigneddivideinc), [PaulaChannelState](catalogue.md#paulachannelstateh), [ImmutablePcmCache](catalogue.md#immutablepcmcacheh) |
| Blitter completion and copper palette reuse | [BlitterCompletion](catalogue.md#blittercompletionh); `CopperPaletteCache.h` documents invalidation in source |
| Guarded native OS dispatch | [QuickOSWarm](catalogue.md#quickoswarminc); `LineAVector.h` and `RectUnion68k.h` document their checked-caller contracts in source |

## Updating a consumer

`make share` installs this directory under `$AMIGA_SHARE/mac-runtime`. Consumers
vendor byte-identical files under `src/mac/` and pin them in
`manifest/shared-runtime.sha256`. Build and host-test entry points verify those pins.
Change the canonical source, install it, then update clean consumers together and
validate their callers. Do not maintain independent per-game implementations.
Installed edits must return through `make pull-shared` before installation.

Run `make test-mac-runtime` for the portable synthetic edge and alias checks.
