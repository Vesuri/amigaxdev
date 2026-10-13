#include <cassert>
#include <cstring>
#include <initializer_list>
#include "GWorld8.h"
#include "CopyBits8.h"
#include "FillRect8.h"
#include "RegionOps.h"
static void rect(uint8_t* p,int t,int l,int b,int r) {
    GWorld8::rect(p,{int16_t(t),int16_t(l),int16_t(b),int16_t(r)});
}
int main() {
    uint8_t a[10]={},b[10]={},out[1024]={};
    GWorld8::word(a,10);rect(a+2,1,2,5,6);
    GWorld8::word(b,10);rect(b+2,3,4,7,8);
    for(auto operation:{RegionOps::Xor,RegionOps::Difference,RegionOps::Intersection,RegionOps::Union}) {
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
