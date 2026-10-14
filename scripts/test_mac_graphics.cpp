#include <cassert>
#include <cstring>
#include <initializer_list>
#include <vector>
#include "GWorld8.h"
#include "CopyBits8.h"
#include "FillRect8.h"
#include "RegionOps.h"
static void rect(uint8_t* p,int t,int l,int b,int r) {
    GWorld8::rect(p,{int16_t(t),int16_t(l),int16_t(b),int16_t(r)});
}
static void testOverlap() {
    std::vector<uint8_t> bounds(8),clip(8);rect(bounds.data(),-2,-3,22,29);rect(clip.data(),0,0,21,27);
    for(int dy=-9;dy<=9;++dy)for(int dx=-9;dx<=9;++dx) {
        std::vector<uint8_t> initial(24*32),actual;
        for(unsigned i=0;i<initial.size();++i)initial[i]=uint8_t(i*71+i/32);
        actual=initial;auto expected=initial;
        std::vector<uint8_t> from(8),to(8);rect(from.data(),3,4,17,21);rect(to.data(),3+dy,4+dx,17+dy,21+dx);
        for(int y=0;y<21;++y)for(int x=0;x<27;++x)
            if(y>=3+dy && y<17+dy && x>=4+dx && x<21+dx)
                expected[(y+2)*32+x+3]=initial[(y-dy+2)*32+x-dx+3];
        uint8_t drawn[8];
        assert(CopyBits8::copy(actual.data(),actual.size(),32,bounds.data(),actual.data(),actual.size(),32,bounds.data(),from.data(),to.data(),bounds.data(),bounds.data(),clip.data(),drawn));
        assert(actual==expected);
    }
}
static void validationCache() {
    static RegionRows::ValidationCache cache;
    std::vector<std::vector<uint8_t>> keys;
    for(unsigned n=0;n<96;++n) {
        std::vector<uint8_t> r(10,0);
        for(unsigned y=0;y<(n%2?800:20);++y) {
            r.push_back(y>>8);r.push_back(y);r.push_back(127);r.push_back(255);
        }
        r.push_back(127);r.push_back(255);
        GWorld8::word(r.data(),r.size());r[5]=n;
        keys.push_back(r);
    }
    for(unsigned round=0;round<3;++round)for(auto r:keys) {
        RegionRows::Edges edges{};
        assert(RegionRows::row(r.data(),r.size(),0,edges));
        assert(cache.validate(r.data(),r.size()));
        assert(cache.validate(r.data(),r.size()));
        assert(!cache.validate(r.data(),r.size()-1));
        r.back()=0;
        assert(!RegionRows::row(r.data(),r.size(),0,edges));
        assert(!cache.validate(r.data(),r.size()));
    }
}
int main() {
    testOverlap();
    validationCache();
    uint8_t a[10]={},b[10]={},out[1024]={};
    GWorld8::word(a,10);rect(a+2,1,2,5,6);
    GWorld8::word(b,10);rect(b+2,3,4,7,8);
    const RegionOps::Operation operations[]={RegionOps::Xor,RegionOps::Difference,RegionOps::Intersection
#ifdef AMIGAXDEV_REGION_UNION
        ,RegionOps::Union
#endif
    };
    for(auto operation:operations) {
        uint16_t size=0;
        assert(RegionOps::combine(a,10,b,10,operation,out,sizeof out,size));
        RegionRows::Cursor rows;assert(rows.begin(out,size));
        for(int y=0;y<9;++y) {
            assert(rows.advance(y));
            for(int x=0;x<10;++x) {
                bool inside=false;
                for(unsigned i=0;i<rows.edges.count;i+=2)
                    if(x>=rows.edges.x[i] && x<rows.edges.x[i+1])inside=true;
                bool inA=y>=1 && y<5 && x>=2 && x<6;
                bool inB=y>=3 && y<7 && x>=4 && x<8;
                bool expected=operation==RegionOps::Xor?inA!=inB:
                    operation==RegionOps::Difference?inA&&!inB:
                    operation==RegionOps::Intersection?inA&&inB:inA||inB;
                assert(inside==expected);
            }
        }
        assert(!RegionOps::combine(a,9,b,10,operation,out,sizeof out,size));
        assert(!RegionOps::combine(a,10,b,10,operation,out,9,size));
    }
    uint8_t bounds[8];rect(bounds,0,0,3,5);
    uint8_t src[24],dst[24],drawn[8];
    for(unsigned i=0;i<24;++i){src[i]=uint8_t(i);dst[i]=0xe1;}
    assert(CopyBits8::copy(src,24,8,bounds,dst,24,8,bounds,bounds,bounds,bounds,bounds,bounds,drawn));
    for(unsigned i=0;i<24;++i)assert(dst[i]==(i%8<5?src[i]:0xe1));
    assert(!CopyBits8::copy(src,23,8,bounds,dst,24,8,bounds,bounds,bounds,bounds,bounds,bounds,drawn));
    for(unsigned alignment=0;alignment<4;++alignment)for(unsigned count=0;count<66;++count) {
        uint8_t pixels[80];std::memset(pixels,0x53,sizeof pixels);
        FillRect8::fillSpan(pixels+4+alignment,count,0xa7);
        for(unsigned i=0;i<80;++i)assert(pixels[i]==(i>=4+alignment && i<4+alignment+count?0xa7:0x53));
    }
    GWorld8::Layout layout{528,528*384};uint8_t map[50];
    GWorld8::pixmap(map,0x1000,0x2000,{0,0,384,510},layout);
    assert(RectBounds::word(map+4)==(0x8000|528));
    assert(RectBounds::word(map+12)==510 && RectBounds::word(map+14)==2);
}
