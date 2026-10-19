#include <cstdint>
#include <cassert>
#include "PinnedSlotRanges.h"
template<unsigned Slots> void test(){
    PinnedSlotRanges<Slots> cache;
    alignas(128) uint8_t slots[Slots*8]={},flags[3]={1,0x81,0x41};
    assert(!cache.cachedFlags(nullptr) && !cache.cachedFlags(slots));
    assert(cache.rememberFlags(slots,flags)==flags);
    assert(cache.cachedFlags(slots)==flags && !cache.cachedFlags(slots+1));
    const auto* hints=cache.flagHints();
    unsigned index=((unsigned long)slots>>2)&(Slots-1);
    assert(hints[index].address==slots && hints[index].flags==flags);
    flags[0]=0;
    assert(*cache.cachedFlags(slots)==0); // disposal is never hidden
    flags[0]=0x61;
    assert(*cache.cachedFlags(slots)==0x61); // reuse is read afresh
    cache.rememberFlags(slots+8,flags+1);
    assert(cache.cachedFlags(slots)==flags && cache.cachedFlags(slots+8)==flags+1);
    cache.rememberFlags(slots+Slots*4,flags+2); // Same index, different validated slot.
    assert(!cache.cachedFlags(slots) && cache.cachedFlags(slots+Slots*4)==flags+2);
    assert(cache.cachedFlags(slots+8)==flags+1);
    flags[2]=0;
    assert(*cache.cachedFlags(slots+Slots*4)==0);
    flags[2]=0xe1;
    assert(*cache.cachedFlags(slots+Slots*4)==0xe1);
    assert(!cache.template find<4>(0));
    for(unsigned i=0;i<64;++i){
        uint32_t start=0x120+i*256,length=128;
        cache.remember(start,start,length);
        for(unsigned offset=0;offset<256;++offset){
            auto* r=cache.template find<4>(start+offset);
            assert(bool(r)==(offset<length && !(offset%4)));
            if(r)assert(r->start==start && r->length==length);
        }
        assert(!cache.template find<4>(start-1));
        if(i>=16)assert(!cache.template find<4>(start-4096));
    }
    cache.clear();
    for(unsigned i=0;i<Slots;++i)assert(!hints[i].address && !hints[i].flags);
    assert(!cache.cachedFlags(slots+8) && !cache.cachedFlags(slots+Slots*4));
    for(unsigned i=0;i<64;++i)assert(!cache.template find<4>(0x120+i*256));
    cache.remember(0xfffffff0,0xfffffff0,16);
    assert(cache.template find<8>(0xfffffff8));
    assert(!cache.template find<8>(0xfffffff4) && !cache.template find<8>(0));
}

int main(){test<32>();test<256>();}
