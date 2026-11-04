// HeapClearLow.inc against a minimal arena/master-block adapter. The cases are
// the System 7.5.5 placements the helper reproduces: NewPtr goes to the lowest
// run of free and movable blocks, moving handles even across locked ones, and
// fails without moving anything when no run can be cleared.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

class MacHeap {
public:
    using Handle=uint8_t**;
    struct Block { uint32_t span,logical,owner,kind,stateOffset,reserved; };
    enum { freeBlock=0,ptrBlock=1,handleBlock=2,masterBlock=3,
           headerBytes=64,blockBytes=24,minimumBlock=32,slots=16 };
    enum { memFullErr=-108 };
    alignas(8) uint8_t storage[65536];
    uint8_t* arena_=storage;
    uint32_t end_=0,masterOff=0;
    int16_t error_=0;unsigned publishes=0;bool moved=false;
    explicit MacHeap(uint32_t bytes) {
        std::memset(storage,0,sizeof(storage));end_=bytes;
        block(headerBytes)={end_-headerBytes,0,0,freeBlock,0,0};
        const uint32_t masterBytes=slots*(sizeof(uint8_t*)+1);
        masterOff=headerBytes;split(masterOff,physical(masterBytes),masterBytes,masterBlock,slots);
    }
    Handle slot(unsigned i) { return (Handle)(arena_+masterOff+blockBytes)+i; }
    uint8_t* flag(unsigned i) { return arena_+masterOff+blockBytes+slots*sizeof(uint8_t*)+i; }
    Handle newHandle(uint32_t bytes,unsigned i) {
        const uint32_t span=physical(bytes);
        for(uint32_t off=headerBytes;off<end_;off+=block(off).span)
            if(block(off).kind==freeBlock && block(off).span>=span) {
                split(off,span,bytes,handleBlock,uint32_t((uint8_t*)slot(i)-arena_));
                *slot(i)=arena_+off+blockBytes;return slot(i);
            }
        return nullptr;
    }
    void disposeHandle(unsigned i) { release(uint32_t(*slot(i)-arena_-blockBytes));*slot(i)=nullptr; }
    uint32_t largestFree() {
        uint32_t best=0;
        for(uint32_t off=headerBytes;off<end_;off+=block(off).span)
            if(block(off).kind==freeBlock && block(off).span>best)best=block(off).span;
        return best;
    }
    uint8_t* newPtr(uint32_t bytes) { uint32_t off=allocateLow(bytes,ptrBlock);return off ? arena_+off+blockBytes : nullptr; }
    // Every block chains to end_, no two free blocks touch, and each handle's
    // master pointer addresses its own block's payload.
    bool check() {
        uint32_t off=headerBytes;bool previousFree=false;
        while(off<end_) {
            const Block& b=block(off);
            if(b.span<minimumBlock || off+b.span>end_)return false;
            if(b.kind==freeBlock && previousFree)return false;
            if(b.kind==handleBlock && *(Handle)(arena_+b.owner)!=arena_+off+blockBytes)return false;
            previousFree=b.kind==freeBlock;off+=b.span;
        }
        return off==end_;
    }
    uint32_t clearLow(uint32_t bytes);
    uint32_t allocateLow(uint32_t bytes,uint32_t kind);
private:
    Block& block(uint32_t off) const { return *(Block*)(arena_+off); }
    static uint32_t physical(uint32_t logical) {
        if(!logical)return 0;
        uint32_t span=(logical+blockBytes+7)&~7u;return span<minimumBlock ? minimumBlock : span;
    }
    bool movable(uint32_t off) const { return block(off).kind==handleBlock && !(arena_[block(off).stateOffset]&0x80); }
    void split(uint32_t off,uint32_t span,uint32_t logical,uint32_t kind,uint32_t owner) {
        uint32_t state=0;
        if(kind==handleBlock) {
            const unsigned i=unsigned((owner-(masterOff+blockBytes))/sizeof(uint8_t*));
            state=uint32_t(flag(i)-arena_);
        }
        const uint32_t available=block(off).span;
        if(available-span>=minimumBlock)block(off+span)={available-span,0,0,freeBlock,0,0};
        else span=available;
        block(off)={span,logical,owner,kind,state,0};
    }
    void release(uint32_t off) { block(off).kind=freeBlock;block(off).logical=block(off).owner=0;coalesce(); }
    void coalesce() {
        for(uint32_t off=headerBytes;off<end_;) {
            const uint32_t next=off+block(off).span;
            if(block(off).kind==freeBlock && next<end_ && block(next).kind==freeBlock)block(off).span+=block(next).span;
            else off=next;
        }
    }
    void moveBytes(uint8_t* dst,const uint8_t* src,uint32_t bytes) { if(dst!=src && bytes)moved=true;std::memmove(dst,src,bytes); }
    void compact() {
        uint32_t dst=headerBytes;
        for(uint32_t src=headerBytes;src<end_;) {
            const Block saved=block(src);const uint32_t next=src+saved.span;
            if(saved.kind!=freeBlock) {
                if(movable(src)) {
                    if(dst!=src)moveBytes(arena_+dst,arena_+src,saved.span);
                    *(Handle)(arena_+saved.owner)=arena_+dst+blockBytes;dst+=saved.span;
                } else {
                    if(dst<src)block(dst)={src-dst,0,0,freeBlock,0,0};
                    dst=next;
                }
            }
            src=next;
        }
        if(dst<end_)block(dst)={end_-dst,0,0,freeBlock,0,0};
    }
    void purge(uint32_t) { compact(); }
    void publish() { ++publishes; }
    int16_t result(int16_t e) { error_=e;return e; }
};
#include "../share/mac-runtime/HeapClearLow.inc"

static void fill(uint8_t* p,unsigned n,uint8_t v) { std::memset(p,v,n); }
static bool filled(const uint8_t* p,unsigned n,uint8_t v) { for(unsigned i=0;i<n;++i)if(p[i]!=v)return false;return true; }

int main() {
    // An unlocked handle run at the bottom: the pointer takes the lowest
    // address and the handles move above it with their bytes intact.
    {
        MacHeap h(65536);std::vector<uint8_t*> before;
        for(unsigned i=0;i<3;++i) { auto x=h.newHandle(2048,i);assert(x);fill(*x,2048,uint8_t(0x10+i));before.push_back(*x); }
        uint8_t* p=h.newPtr(256);
        assert(p && p==before[0] && h.error_==0 && h.check() && h.moved && h.publishes==1);
        for(unsigned i=0;i<3;++i)assert(*h.slot(i)>p && filled(*h.slot(i),2048,uint8_t(0x10+i)));
    }
    // Locked blocks are never moved; the run below a locked block is used
    // when it fits, so the pointer stays below it.
    {
        MacHeap h(65536);
        auto a=h.newHandle(2048,0),l=h.newHandle(1024,1);assert(a && l);*h.flag(1)=0x80;
        uint8_t* locked=*l;fill(*a,2048,0x5a);
        uint8_t* p=h.newPtr(1024);
        assert(p && p<locked && *l==locked && *a>locked && filled(*a,2048,0x5a) && h.check());
    }
    // An 11 KB request fits only by moving the low 8 KB handle across a locked
    // one into a 9 KB hole; a 13 KB request fails and moves nothing.
    for(uint32_t request: {11264u,13312u}) {
        MacHeap h(65536);
        auto h1=h.newHandle(8192,0),g=h.newHandle(4096,1),l2=h.newHandle(1024,2);
        assert(h1 && g && l2);*h.flag(2)=0x80;fill(*h1,8192,0x5a);
        auto f=h.newHandle(9216,3),l3=h.newHandle(1024,4);assert(f && l3);*h.flag(4)=0x80;
        // Lock the rest of the heap so the 9 KB hole is the only room outside the run.
        auto rest=h.newHandle(h.largestFree()-MacHeap::blockBytes,5);assert(rest && h.largestFree()==0);*h.flag(5)=0x80;
        h.disposeHandle(1);h.disposeHandle(3);
        uint8_t* low=*h1;uint8_t* lockedA=*l2;uint8_t* lockedB=*l3;
        h.moved=false;
        uint8_t* p=h.newPtr(request);
        if(request==11264) {
            assert(p && p<lockedA && p<=low && *h1>lockedA && *h1<lockedB && filled(*h1,8192,0x5a));
        } else assert(!p && h.error_==MacHeap::memFullErr && *h1==low && !h.moved);
        assert(*l2==lockedA && *l3==lockedB && h.check());
    }
    std::puts("HEAP LOW PASS: lowest run, locked blocks pinned, relocation across locked, failure");
}
