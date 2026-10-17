#include "../share/mac-runtime/DirtyBands.h"
#include <cassert>
#include <algorithm>
#include <cstdio>
struct Rect {int16_t top,left,bottom,right;};
template<int W,int H,unsigned N> void test() {
    Rect v={0,0,H,W},out[128],in[N];uint16_t count=0;
    uint32_t seed=29;
    for(unsigned trial=0;trial<4096;++trial) {
        seed=seed*1664525u+1013904223u;
        uint16_t n=0;
        for(int x=0;x<W/16;++x)if(seed&(1u<<x))in[n++]={0,int16_t(16*x+7),1,int16_t(16*x+9)};
        assert((DirtyBands::plan<W,H,N>(v,in,n,out,128,count)));
        unsigned coverage[W/16]={},best[W/16+1];best[W/16]=0;
        for(unsigned i=0;i<count;++i) {
            auto r=out[i];assert(r.top==0 && r.bottom==1 && r.left>=0 && r.right<=W && !(r.left%16) && !((r.right-r.left)%32));
            for(int x=r.left/16;x<r.right/16;++x)assert(++coverage[x]==1);
        }
        unsigned area=0;
        for(int x=W/16-1;x>=0;--x) {
            bool need=seed&(1u<<x);assert(!need || coverage[x]);area+=coverage[x];
            best[x]=need?100:best[x+1];
            for(int end=x+2;end<=W/16;end+=2)best[x]=std::min(best[x],unsigned(end-x)+best[end]);
        }
        assert(area==best[0]);
    }
    in[0]={-32768,-32768,32767,32767};
    assert((DirtyBands::plan<W,H,N>(v,in,1,out,1,count)) && count==1 && out[0].bottom==H && out[0].right==W);
    in[0]={2,2,1,3};assert((!DirtyBands::plan<W,H,N>(v,in,1,out,128,count)));
    assert((!DirtyBands::plan<W,H,N>(v,in,N+1,out,128,count)));
    assert((!DirtyBands::plan<W,H,N>(v,in,0,out,0,count)));
    assert((DirtyBands::plan<W,H,N>(v,(const Rect*)nullptr,0,out,128,count)) && !count);
    in[0]={0,0,2,1};in[1]={1,48,3,49};
    assert((DirtyBands::plan<W,H,N>(v,in,2,out,1,count)) && count==1 && out[0].top==0 && out[0].bottom==3 && out[0].left==0 && out[0].right>=49);
}
int main(){test<320,200,32>();test<512,384,64>();puts("PASS shared dirty bands: both viewports, 8192 minimum-row controls, clipping, empty, invalid and capacity fallback");}
