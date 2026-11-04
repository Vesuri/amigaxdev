# Kalms interleaved rectangle adapter

`c2p1x1_8_c5_030_2.s` is unchanged public-domain source from Kalmalyzer/kalms-c2p
commit `d8ecf79a3325615305dd800ae7704b518e0d9dda`, file
[`normal/c2p1x1_8_c5_030_2.s`](https://github.com/Kalmalyzer/kalms-c2p/blob/d8ecf79a3325615305dd800ae7704b518e0d9dda/normal/c2p1x1_8_c5_030_2.s). Its SHA-256 is pinned in
`manifest/kalms-c2p.sha256`. Despite the name, its instructions assemble for 68020.

`KalmsC2PRect.s` adapts this kernel to rectangles of rows. Supply
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

This is a conversion helper, not a dirty planner or presentation scheduler: the
consumer keeps its own dirty bands and frame-end publication. Before adopting it,
validate full output, ABI and memory bounds natively (every 32-pixel width up to the
maximum, several source alignments and heights, full-screen and bottom-right extents,
unchanged source and surrounding memory) and measure it on a matched workload;
measurements from one port do not transfer to another.
