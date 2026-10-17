#ifndef AMIGAXDEV_DIRTY_BANDS_H
#define AMIGAXDEV_DIRTY_BANDS_H
#ifndef __mc68000__
#include <stdint.h>
#endif
// Coordinate-only planner extracted from Alone in the Dark. Caller supplies
// viewport dimensions, bounded input storage and a signed 16-bit rectangle.
namespace DirtyBands {
// Kalms needs a width divisible by 32, but its output may start on any word.
// Anchoring the block at a 16-pixel boundary avoids expanding a narrow actor
// across two fixed 32-pixel columns. Keep the final block inside the viewport.
template<int Width,class Rect>
inline void alignSpan(Rect& r) {
    const int width=Width;
#include "DirtyBandsAlign.inc"

}

// Plan disjoint conversion bands from clipped draw coordinates, before alignment.
// No pixels are read. Each band has a constant set of dirty horizontal intervals;
// aligned overlaps become one span, then identical adjacent bands coalesce.
template<int Width,int Height,unsigned MaxDirty,class Rect>
inline bool plan(const Rect& viewport,const Rect* dirty,uint16_t dirtyCount,
                 Rect* output,uint16_t capacity,uint16_t& count) {
    const int width=Width,height=Height;
#define DIRTY_BANDS_CAPACITY MaxDirty
#define DIRTY_BANDS_ALIGN alignSpan<Width>
#define DIRTY_BANDS_VIEWPORT_VALID(v) ((v).top>=0 && (v).left>=0 && (v).bottom<=480 && (v).right<=640 && (v).bottom-(v).top==Height && (v).right-(v).left==Width)
#include "DirtyBandsPlan.inc"
#undef DIRTY_BANDS_VIEWPORT_VALID
#undef DIRTY_BANDS_ALIGN
#undef DIRTY_BANDS_CAPACITY

}

}
#endif
