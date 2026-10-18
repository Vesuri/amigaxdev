#include "IdentityIndexCache.h"
#include <cassert>
#include <cstdio>
struct Record {uint32_t identity;bool live;};
int main() {
    Record rows[512]={};
    for(unsigned i=0;i<512;++i)rows[i]={i+1,true};
    IdentityIndexCache<> cache;
    auto matches=[](const Record& r,uint32_t key){return r.live && r.identity==key;};
    uint32_t index=999;
    assert(cache.find(rows,512,1,matches,index) && index==0);
    assert(cache.find(rows,512,129,matches,index) && index==128); // collision
    assert(cache.find(rows,512,1,matches,index) && index==0);
    rows[0].live=false;index=999;
    assert(!cache.find(rows,512,1,matches,index) && index==999);
    rows[0]={9001,true};
    assert(cache.find(rows,512,9001,matches,index) && index==0);
    assert(!cache.find(rows,0,9001,matches,index));
    assert(cache.find(rows,512,512,matches,index) && index==511);
    assert(!cache.find(rows,511,512,matches,index));
    // Reset/repopulate the same storage while retaining stale cache entries.
    for(unsigned i=0;i<512;++i)rows[i]={i+1,true};
    uint32_t random=0x12345678;
    for(unsigned n=0;n<100000;++n) {
        random=random*1664525+1013904223;
        uint32_t slot=(random>>16)&511;rows[slot].live=!rows[slot].live;
        uint32_t count=(random>>6)%513,key=(random>>18)%600;
        int oracle=-1;
        for(unsigned i=0;i<count;++i)if(matches(rows[i],key)){oracle=i;break;}
        index=0xfeed;
        bool found=cache.find(rows,count,key,matches,index);
        assert(found==(oracle>=0));
        assert(found ? index==uint32_t(oracle) : index==0xfeed);
    }
    std::puts("PASS identity-index cache: 100000 mutation/resize queries; collision, removal, reuse, empty and miss preservation");
}
