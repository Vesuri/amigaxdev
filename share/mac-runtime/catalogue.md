# Macintosh runtime helper contracts

Read the relevant helper section after choosing it in the [index](README.md).
Caller preconditions and validation limits are part of each contract.

## RectBounds.h

`RectBounds.h` combines the rectangle helper and OffsetRect/InsetRect operations.
EqualRect additionally compares all four coordinates without normalizing empty or
inverted bounds; pair its Boolean result with System 7.5.5 in the consumer.
Union/intersection accept explicit load/store template arguments, like adjustment.
Native callers can select shared `BigEndianMemory` word accesses while retaining
the same signed comparisons, empty handling and full-input-before-output rule.
The default overloads retain byte accesses; consumers opt in per call.
## BitmapFont.h

`BitmapFont.h` shares the existing compatibility-font parser and a bounded reader
for original one-bit FOND/NFNT resources. `BitmapText8.h` adapts the clipping and
pixel addressing of an 8-bit text renderer to NFNT glyphs with integer
advances and bearings; it contains no game-specific font tables.

## GWorld8.h

`GWorld8.h`, `CopyBits8.h`, `FillRect8.h`, `WindowGeometry.h`, `RegionRows.h`
and `RegionOps.h` hold the 8-bit QuickDraw drawing helpers. Define `AMIGAXDEV_REGION_UNION` to add region union to the parity-region
operations. Consumers that do not use it retain the existing operation set and
compiled dispatch; both configurations have sanitizer checks. Trap ownership and
current-port selection remain consumer responsibilities.

`CopyBits8::Changes` optionally reports changed row spans through a caller-supplied
copy callback for distinct, unscaled, unmasked identity copies. Missing callbacks
or insufficient report capacity retain the ordinary copy and report `valid=false`;
overlap, mapped and scaled forms retain their existing paths. Row bounds may
conservatively include unchanged edge bytes. The caller owns publication,
viewport invalidation and palette changes.

## CopyChangedRows.inc

`CopyChangedRows.inc` supplies the 68020 C-ABI `copy_changed_rows` body for
0–640 pixels and 0–480 rows. It compares row ends and copies the differing
middle without a second framebuffer. The macro preserves callee-saved registers;
its declared scratch registers/CCR follow the C ABI. Its original native
1,665-case fixture covered pixels, row bounds, padding, source preservation and
registers; the macro assembles identically to that tested body. Native
performance still requires a matched consumer workload; this helper alone does
not establish any game's frame cadence.

## BigEndianMemory.h

`BigEndianMemory.h` supplies explicit 68020 word/longword
accesses, including unaligned addresses and alias-safe memory operands. Its host
fallback preserves big-endian byte order; callers remain responsible for bounds.
The native `AMIGAXDEV_MEMORY_PRIMITIVES_ONLY` mode exposes those same instruction
macros to legacy adapters without adding inline function nodes to their compiler
graph, so an existing consumer keeps its function order and executable.

## CodeRangeCache.h

`CodeRangeCache.h` uses a 256-slot page-indexed cache of original CODE ranges. It rechecks
the current base and size on every hit and retains the full search on misses;
callers supply disjoint ranges and retain their own unknown-caller handling.

## AddressSpan.h

`AddressSpan.h` checks integer address windows after their owner validates the
non-wrapping exclusive end once at allocation. The unsigned offset rejects
addresses below the base as well as overlong requests; zero-length endpoint
queries remain valid. Do not use `contains` before `valid` succeeds.

## UnsignedDivide.inc

`UnsignedDivide.inc` supplies an exact 64-bit-to-32-bit quotient
with the audio adapters. Include it inside their namespace. Only significant
quotient bits are examined; division by zero and quotient overflow return false.
Independent host division checks bit boundaries and one million input pairs.

## FillRect8 native spans

`FillRect8::fillSpan` keeps its native sixteen-byte block counter inside the
assembly loop, with unchanged alignment prefix and exact longword/byte tails.

## PcmDma.inc

`PcmDma.inc` supplies signed PCM conversion for Paula DMA.
Include it inside a namespace after defining `Dma` with `layout` and `stride`.
It preserves decimated loop phase and word padding while copying uninterrupted
source spans; the 68020 path converts eight longwords per loop with a register
XOR mask, then exact longword/byte tails. Decimated spans retain their byte path.

## ResourceDirectory.h

`ResourceDirectory.h` and `ResourceDirectory.cpp` hold mutable
resource metadata, stable identities and streamed publication. Define
`AMIGAXDEV_RESOURCE_DIRECTORY_INDEXED` consistently across a consumer to enable
binary lookup over a lazily rebuilt sorted index. Identity breaks ties
so the oldest surviving duplicate wins even after slot reuse. Successful opens,
closes, additions, replacements and removals invalidate that index. The default
configuration retains the existing linear implementation. Define
`AMIGAXDEV_RESOURCE_DIRECTORY_MAP_LIMIT` to enforce the parser's per-map resource
limit before mutation.

## ResourceWriter.inc

`ResourceWriter.inc` serializes a resource fork from an immutable recipe through a
caller's sink, with the consumer's `ResourceWriter.h` and `ResourceForks.h` (as
`ResourceDirectory.h` uses them; `scripts/fixtures/mac-resource/` shows the
interface). Types follow first appearance and each type's references keep recipe
order, including duplicate type/ID pairs. Unchanged payloads are read from their
sources in at most `chunkBytes` per transfer; the layout lives on the heap, since
4096 entries need 49 KB. `measure` validates without reading payloads. A failed
write calls `finish(false)` and publishes nothing.

`ResourceStage.h` and `ResourceStage.inc` are the DOS sink. The adapter supplies
`FileAccess` (`resloadActive`, `resloadStat`, `resloadReplace`),
`RESOURCE_STAGE_SYSTEM_WINDOW` and the staging suffixes `RESOURCE_STAGE_NEW_SUFFIX`
and `RESOURCE_STAGE_OLD_SUFFIX`. Native DOS writes the new file, renames the old one
to the backup, renames the new one into place and deletes the backup, restoring the
old file if a step fails. Existing staging or backup files are recovery evidence:
`begin` refuses with `recoveryRequired` rather than overwrite them. Under resload
the fork is buffered (at most 2 MB) and replaced in place. `RESOURCE_STAGE_FAULT_PROBE`
exposes `g_resourceStageFault` to inject rename and delete failures.

## VBLPasses.h

`VBLPasses.h` holds queued virtual-retrace bookkeeping. Each elapsed Macintosh tick starts a separate queue pass; callbacks
resume the same pass after returning. Consumers retain task records, countdown
semantics, ownership checks and user-mode trampolines. Synthetic tests exercise
tick conservation, task removal, in-flight arrivals and wraparound.

System 7.5.5 fixtures establish that counts decrement modulo 16 bits, and only
reaching zero dispatches. A callback leaving zero is removed; VRemove then returns
qErr (-1). The original fixtures also verify that automatic and explicit removal leave the removed record's
qLink intact. Keep these policies in the consumer adapter; check membership before
reading a returned callback's record, since it may have removed itself. Removing
one callback must adjust the pass iterator without skipping its next neighbour.

## VideoTicks.h

`VideoTicks.h` supplies PAL/NTSC field conversion and
within-field PAL TickCount calculation. The platform must supply a coherent field
epoch and beam position; callback scheduling and hardware sampling stay outside
the helper. Tests include repeated five-tick deadlines that field-only ticks miss. Keep direct
low-memory Ticks reads and TickCount coherent, including the virtual time exposed to
queued callbacks. Paired isolated waits confirm PAL quantization, not a reached
gameplay slowdown; a field-updated production clock is still valid. See
[clock resolution and loading stalls](../../docs/reference/measurement-method.md#clock-resolution-and-loading-stalls)
for the measurement limits and pending-interrupt/rollover controls.

## HeapMoveHigh.inc

`HeapMoveHigh.inc` supplies `MacHeap::moveHigh` for the common arena/master-block
allocator. Include it at file
scope after the class declaration; the adapter supplies its existing block layout,
copy helpers, validation and result publication. A fitting free tail before the
next pinned block permits target-only relocation. Interior holes and insufficient
tail space require the original compaction fallback. Payloads, handle flags and
pinned addresses remain intact. Pair a consumer's adoption with an original
System 7.5.5 placement fixture and sanitizer heap tests.

## HeapResize.inc

`HeapResize.inc` supplies in-place resizing for the same allocator adapters.
The zone must have no adjacent free blocks on entry. A split or growth can only
create a free/free pair at the resized allocation's tail, so merge that pair
locally instead of rescanning the zone. Logical sizes, allocation placement,
free-byte accounting and the adapter's compaction/failure paths stay unchanged.
Sanitizer tests should combine resizing with thousands of fragmented-heap
operations and check that no adjacent free blocks survive.

## RegionResultCache.h

`RegionResultCache.h` retains successful, pure QuickDraw record transformations
in a 32 KiB FIFO arena with 32 metadata slots. The operation tag and exact input
record bytes are the key; callers validate/compute misses and only insert
successful results. Handles and pixel buffers are not cached. It is optional
caller-owned storage; its sanitizer fixtures cover mutation, relocation and
eviction.

## RGBColorCache.h

`RGBColorCache.h` memoizes successful RGB-to-index lookups per port. Keys include
both dereferenced table addresses, their QuickDraw seeds, format headers and all
48 RGB bits. Relocation, seed or header changes invalidate the entries. The
adapter must also invalidate on port disposal and any same-seed table rebuild;
QuickDraw table edits must publish a new seed. Misses use `GWorld8::colorIndex`,
including its collision-ring validation and first-entry tie rule. This caches
indices, never pixels, and requires no allocation or per-call table copy.

## PenRect8.h

`PenRect8.h` draws a solid zero-displacement QuickDraw pen as a directly clipped
half-open rectangle. It validates map capacity, signed pen extents and all four
clipping bounds before writing. Small spans avoid general rectangle setup;
large spans reuse the aligned fill primitive. The caller supplies a current
allocation capacity; no handle or framebuffer cache is retained by the helper.

## Region validation cache

`RegionRows::ValidationCache` retains fully validated region encodings in a
32 KiB FIFO byte arena with 32 slots (maximum 4096 bytes per record). Keys include
every byte; capacity checks precede lookup, and arena reuse evicts overlapping
entries. `CopyBits8` validates the whole mask before rejecting a disjoint
rectangle, then clips by coordinates and streams rows. Thumbnail scaling uses
a separate routine; no pixel snapshots or handle-address keys are retained.

## HandleCopy.h

`HandleCopy.h` duplicates owned handle data through a heap adapter, protects
the source from purging during allocation and restores its state on success or
failure. The new handle retains its allocator default state. Measure HandToHand
against System 7.5.5 and test the helper with the consumer's real heap;
trap-register and error contracts remain the caller's responsibility.

## BitmapRegion.h

`BitmapRegion.h` converts MSB-first one-bit masks with `RegionOps::Writer`,
using caller-owned staging storage. Region edge storage accommodates thirty-two
transitions, including intermediate XOR states of smaller adjacent rows. Invalid
extents or capacity exhaustion reject before a caller publishes the result.

## HeapLockHandle.inc

`HeapLockHandle.inc` consolidates HLock into one validated master-slot lookup,
using the existing query error policy without rewriting unchanged zone headers. It preserves
resource/purge flags and never moves payloads or changes the free list. Consumers
declare `int16_t lockHandle(Handle)` and include the method beside their state
accessors. Check whole-arena equality against state/setState composition for
all 256 state inputs, plus disposed/null/interior rejection.

## HeapReadHandleState.inc

`HeapReadHandleState.inc` reads HGetState with one validated master-slot lookup.
It preserves allocated-slot rejection, high state bits, query MemError and the
read-only zone-header policy. Its controls cover all 256 slot-byte values and
null handles; consumers also exercise their real master-block ownership guards.

## PinnedSlotRanges.h

`PinnedSlotRanges.h` retains sixteen recently validated immutable master-block
ranges behind a caller's last-range fast path. Membership and slot alignment
are checked on every lookup; allocation flags and pointees are never cached.
Its optional power-of-two template parameter sizes the validated slot-address
to flag-address hints (32 by default). Hits still read current flag bytes;
disposal and slot reuse do not cache a live-state decision. Call `clear()` whenever
the arena resets. It is unsuitable for blocks that can move, shrink or be freed
during an arena's lifetime.

## PAL beam deadlines

`VideoTicks::deadlinePALBeam` inverts the nominal PAL beam-to-microsecond
conversion for due/not-due checks. It retains the 19,999-microsecond clamp and
requires a stable beam snapshot with HP below 227. Tests cover both sides of
every microsecond boundary and every valid PAL beam position. It changes no
deadline or clock epoch.

## PaulaChannelState.h

`PaulaChannelState.h` factors settled-channel and conservative
period-ceiling bookkeeping out of a hardware wrapper. Reset it at takeover;
mark a channel quiet only after the DMA-off and DAC-zero waits complete. It does
not replace those waits or infer quietness from a zero volume.
After the DMA-off wait, `disabled()` also permits an immediate replacement to
avoid repeating that wait. This is not a quiet DAC: an actual stop still needs
the DAT-zero handshake, as do error cleanup and hardware handoff.

## ImmutablePcmCache.h

`ImmutablePcmCache.h` retains immutable song variants
with bounded memory and explicit users. The caller supplies the plan comparison,
conversion and allocation policies. Every conversion-affecting field belongs in
the comparison; period may be excluded when only sample stride affects bytes.
Sources must remain owned and immutable throughout retention. Stop DMA before
releasing its entry, and release every user before clearing at shutdown. Mutable
effect descriptors/data need a different policy. Exhaustion returns null for an
uncached fallback; it never evicts samples still used by DMA.

## DirtyBands.h

`DirtyBands.h` is a coordinate-only disjoint C2P planner.
Callers supply viewport dimensions and input capacity; it clips before alignment,
coalesces adjacent equal bands and falls back to a complete bounding rectangle
on output exhaustion. Synthetic controls cover both 320×200 and 512×384 views.

## BlitterCompletion.h

`BlitterCompletion.h` supplies the completion policy for AmigaHardware’s existing
blitter queue. Its hardware adapter is template-injected for latency/race tests.
The platform owns INTB_BLIT, excludes producers while advancing the queue, bounds
the batch to queue capacity, and drains before CPU access, OS handback or teardown.
It acknowledges completion before starting the next blit, including zero-latency
completion; synchronous consumers do not change.

## HeapFindSpace.inc

`HeapFindSpace.inc` retains the first-fit allocation policy while skipping a
known occupied prefix. The adapter owns a mutable `searchStart_` block boundary,
initially `headerBytes`. Split rewinds it to the modified block; coalescing records
the first free block or zone end; compaction resets it. MoveHHi must finish through
release/coalesce. The full-heap invariant must reject an interior hint or a free
block preceding it. No fitting-size cache or placement change is permitted.
A consumer's mixed-operation oracle should compare against a complete chain walk;
the standalone shared test enumerates all small occupancy layouts and safe hints.

## DirtyBandsAlign.inc

`DirtyBandsAlign.inc` and `DirtyBandsPlan.inc` expose the same implementation
bodies to existing namespace adapters, which keep their function identities
and compiler output through these includes; new consumers
can use the typed `DirtyBands.h` interface. The adapter defines dimensions,
capacity, viewport validation and alignment macros, then undefines them after
inclusion. No game-specific data or pixel comparisons enter the planner.

## IdentityIndexCache.h

`IdentityIndexCache.h` supplies bounded lookup hints for unique live record identities.
Every hit rechecks the current identity/liveness predicate and count. Collisions,
removal, slot reuse and storage repopulation retain the linear-lookup fallback;
failed lookups preserve the output index. Callers still resolve their namespace
(such as the active resource-file chain) first. The sanitizer suite compares
100,000 mutation/resize queries with a linear oracle.

## QuickOSWarm.inc

`QuickOSWarm.inc` supplies C-ABI assembly bodies for guarded HGetState/HLock
and SwapMMUMode entries. The caller must already validate the trap owner,
register image and pending-service certificate. Handle hits require a full
pinned-slot identity match and a currently allocated live flag; misses tail-call
the checked implementation without modifying guest state. The slot table is
read-only to assembly and must be cleared before its arena is reused. Mac OS
result condition codes preserve the saved X/high bits. MMU mode accepts only
low-byte 0/1 and preserves the current heap error; handle successes clear it.
Pair the bodies with the consumer's checked, original-paired C services across
handle flags, condition codes, invalid slots and MMU modes.

## StripAddressChecks.h

A regression fixture for native high pointers, not a runtime implementation.
`strip_address_checks::native(dispatch, report, pc)` checks 384 register/CCR/mode
cases; adapt each production dispatch to the snapshot contract and include normal
trap-PC advancement. `original24` checks the separate Macintosh logical tagging
contract (192 cases). The report callback must fail the caller's test on a false
result. See [native pointer validation](../../docs/native-port-validation.md#macintosh-logical-addresses-and-native-high-pointers)
for original-paired evidence and low/high-memory gameplay qualification.
