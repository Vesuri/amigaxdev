#include <cassert>
#include <initializer_list>
#include "CodeRangeCache.h"
static bool slow(const uint32_t (*r)[2],uint32_t n,uint32_t pc,uint32_t& index,uint32_t& offset) {
    for(uint32_t i=0;i<n;++i)if(r[i][1]>=2 && pc>=r[i][0] && pc-r[i][0]<=r[i][1]-2) {
        index=i;offset=pc-r[i][0];return true;
    }
    return false;
}
int main() {
    uint32_t ranges[4][2]={{0,0},{0x1000,32},{0x2001,31},{0xfffffff0,16}};
    CodeRangeCache cache;
    for(unsigned pass=0;pass<5;++pass) {
        for(uint32_t pc:{0u,0xfffu,0x1000u,0x101eu,0x101fu,0x1020u,0x2000u,0x2001u,0x201eu,0x201fu,0xfffffff0u,0xfffffffeu,0xffffffffu}) {
            uint32_t a=77,b=88,x=77,y=88;
            assert(cache.find(ranges,4,pc,a,b)==slow(ranges,4,pc,x,y));assert(a==x && b==y);
        }
        ranges[1][0]+=32;ranges[2][1]=pass&1 ? 31 : 0;
    }
    uint32_t collision[2][2]={{0x1000,32},{0x41000,32}};
    for(unsigned n=0;n<20;++n){uint32_t i=0,o=0;unsigned wanted=n&1;
        assert(cache.find(collision,2,collision[wanted][0]+4,i,o) && i==wanted && o==4);}
    uint32_t i=0,o=0;
    assert(cache.find(ranges,4,0xfffffff0,i,o) && i==3);
    assert(!cache.find(ranges,3,0xfffffff0,i,o)); // reduced table must reject a cached slot
    ranges[3][1]=1;assert(!cache.find(ranges,4,0xfffffff0,i,o));
    ranges[3][0]=0x3000;ranges[3][1]=4;
    assert(!cache.find(ranges,4,0xfffffff0,i,o));assert(cache.find(ranges,4,0x3002,i,o) && i==3 && o==2);
}
