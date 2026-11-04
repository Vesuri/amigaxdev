// Shared low placement for the arena/master-block MacHeap adapters.
// Include at file scope after MacHeap.h and the adapter's block/copy helpers.
// The adapter supplies block(), movable(), physical(), split(), release()
// (which coalesces), moveBytes(), compact(), purge(), publish(), result() and
// the Block layout {span,logical,owner,kind,...}. Define
// AMIGAXDEV_HEAP_TARGET_START to a boundary no free block precedes (such as
// HeapFindSpace's searchStart_); the default walks from headerBytes.
#ifndef AMIGAXDEV_HEAP_TARGET_START
#define AMIGAXDEV_HEAP_TARGET_START headerBytes
#endif
// MEASURED (System 7.5.5): NewPtr and explicit or implicit MoreMasters place
// their block at the lowest run of free and movable blocks that covers it,
// relocating the movable ones elsewhere, even across locked blocks. The
// original picks relocation targets with its own rover; this relocates
// first-fit outside the run. Returns the free block now covering the run, or 0
// when a movable block finds no room; blocks moved before that stay moved, with
// their master pointers updated.
uint32_t MacHeap::clearLow(uint32_t bytes)
{
    const uint32_t needed=physical(bytes);
    for(uint32_t p=headerBytes;p<end_;p+=block(p).span) {
        if(block(p).kind!=freeBlock && !movable(p))continue;
        uint32_t q=p;
        while(q<end_ && q-p<needed && (block(q).kind==freeBlock || movable(q)))q+=block(q).span;
        if(q-p<needed)continue;
        const uint32_t e=p+needed;
        // Released blocks coalesce, but their stale headers keep the walk valid.
        for(uint32_t m=p;m<q;) {
            const Block saved=block(m);const uint32_t next=m+saved.span;
            if(saved.kind!=freeBlock) {
                const uint32_t span=physical(saved.logical);uint32_t target=0;
                for(uint32_t off=AMIGAXDEV_HEAP_TARGET_START;off<end_ && !target;off+=block(off).span) {
                    const uint32_t free=block(off).span;
                    if(block(off).kind!=freeBlock)continue;
                    if(off+free<=p || off>=e) { if(free>=span)target=off; }
                    else if(off+free>e) {
                        // A free block crossing the run's end keeps its upper part usable.
                        const uint32_t cut=e-off>=minimumBlock ? e : off+minimumBlock;
                        if(off+free>=cut+span) {
                            block(off).span=cut-off;block(cut)={off+free-cut,0,0,freeBlock,0,0};target=cut;
                        }
                    }
                }
                if(!target)return 0;
                split(target,span,saved.logical,handleBlock,saved.owner);
                moveBytes(arena_+target+blockBytes,arena_+m+blockBytes,saved.logical);
                *(Handle)(arena_+saved.owner)=arena_+target+blockBytes;
                release(m);
            }
            m=next;
        }
        for(uint32_t off=headerBytes;off<end_;off+=block(off).span)
            if(off<=p && p<off+block(off).span)return block(off).kind==freeBlock ? off : 0;
        return 0;
    }
    return 0;
}
// NewPtr and MoreMasters: the lowest clearable run, then after compaction,
// then after purging. Allocates the block and publishes the heap header.
uint32_t MacHeap::allocateLow(uint32_t bytes,uint32_t kind)
{
    if(!arena_ || !physical(bytes)) { result(memFullErr);return 0; }
    uint32_t off=clearLow(bytes);
    if(!off) { compact();off=clearLow(bytes); }
    if(!off) { purge(bytes);off=clearLow(bytes); }
    publish();
    if(!off) { result(memFullErr);return 0; }
    split(off,physical(bytes),bytes,kind,0);result(0);return off;
}
