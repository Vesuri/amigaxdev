# Kalms interleaved rectangle adapter

`c2p1x1_8_c5_030_2.s` is unchanged public-domain source from Kalmalyzer/kalms-c2p
commit `d8ecf79a3325615305dd800ae7704b518e0d9dda`, file
[`normal/c2p1x1_8_c5_030_2.s`](https://github.com/Kalmalyzer/kalms-c2p/blob/d8ecf79a3325615305dd800ae7704b518e0d9dda/normal/c2p1x1_8_c5_030_2.s). Its SHA-256 is pinned in
`manifest/kalms-c2p.sha256`. Despite the name, its instructions assemble for 68020.

`KalmsC2PRect.s` adapts Alone in the Dark's row adapter to this kernel. Supply
`C2P_SOURCE_STRIDE`, `C2P_OUTPUT_STRIDE`, `C2P_PLANE_STRIDE`, `C2P_MAX_WIDTH`
and an assembler include path containing the kernel and NDK `lvo/exec_lib.i`.
The C ABI is `(const uint8_t* source, uint8_t* destination, uint32_t width,
uint32_t rows)`. Width is positive, divisible by 32 and no greater than the
configured maximum, which must not exceed eight times the plane stride.
The configured row strides must fit a positive signed word; the plane stride
must not exceed 16 KiB. Rows must be positive and all source/destination extents
validated by the caller. Output may start on a word boundary. Each source span
needs four readable bytes after its end for the kernel's unused prefetch.
The adapter adds four BSS bytes after the scratch buffer for its final prefetch.
It calls the ordinary initializer, never the self-modifying initializer.

This is a conversion helper, not a dirty planner or presentation scheduler.
Prince of Persia 2 retains its original dirty bands and frame-end publication.
Its integrated fixed-14-MHz 68020 build passed 193 native byte/ABI cases
(every 32-pixel width through 512, four source alignments, multiple heights,
full-screen and bottom-right extents, unchanged source and surrounding memory),
82 full-frame planar comparisons and matched opening repeats. Its landing
measurement is 275.91–275.99 ms per stored row, with 49.98–50.01 ms conversion.
The original cadence gate remains unmet. These measurements do not transfer to other ports;
validate full output, ABI, memory bounds and matched workloads before adoption.
