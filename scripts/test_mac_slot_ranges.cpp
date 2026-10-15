#include <cstdint>
#include <cassert>
#include "PinnedSlotRanges.h"
int main(){
    PinnedSlotRanges cache;
    assert(!cache.find<4>(0));
    for(unsigned i=0;i<64;++i){
        uint32_t start=0x120+i*256,length=128;
        cache.remember(start,start,length);
        for(unsigned offset=0;offset<256;++offset){
            auto* r=cache.find<4>(start+offset);
            assert(bool(r)==(offset<length && !(offset%4)));
            if(r)assert(r->start==start && r->length==length);
        }
        assert(!cache.find<4>(start-1));
        if(i>=16)assert(!cache.find<4>(start-4096));
    }
    cache.clear();
    for(unsigned i=0;i<64;++i)assert(!cache.find<4>(0x120+i*256));
    cache.remember(0xfffffff0,0xfffffff0,16);
    assert(cache.find<8>(0xfffffff8));
    assert(!cache.find<8>(0xfffffff4) && !cache.find<8>(0));
}
