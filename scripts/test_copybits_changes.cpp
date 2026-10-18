#include "CopyBits8.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

// Independent scalar callback exercises the report API; the 68020 body has
// a separate native pixel/register oracle.
static unsigned calls;
static void scalarRows(const uint8_t* in,uint8_t* out,uint32_t width,uint32_t height,
                       uint32_t ss,uint32_t ds,CopyBits8::RowSpan* spans) {
    ++calls;
    for(uint32_t y=0;y<height;++y) {
        uint32_t first=width,last=width;
        for(uint32_t x=0;x<width;++x) {
            if(in[y*ss+x]!=out[y*ds+x]) {if(first==width)first=x;last=x+1;}
            out[y*ds+x]=in[y*ss+x];
        }
        spans[y]={uint16_t(first),uint16_t(last)};
    }
}
static void rect(uint8_t* p,int t,int l,int b,int r) {
    int v[]={t,l,b,r};
    for(unsigned i=0;i<4;++i){p[2*i]=uint16_t(v[i])>>8;p[2*i+1]=uint8_t(v[i]);}
}
int main() {
    for(unsigned trial=0;trial<8192;++trial) {
        const unsigned width=trial<4096?1+trial%97:1+(trial*37)%640;
        const unsigned height=1+(trial/97)%23;
        const unsigned ss=width+7,ds=width+13,sa=trial%4,da=(trial/4)%4;
        std::vector<uint8_t> source(sa+ss*height+8,0x5a),initial(da+ds*height+8,0xa5);
        for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x) {
            uint8_t value=uint8_t(x*31+y*17+trial);
            source[sa+y*ss+x]=value;
            initial[da+y*ds+x]=value;
            if(trial%7 && x>=(y+trial)%width && x<=width-1-(trial%width)/2)
                initial[da+y*ds+x]^=0x80;
        }
        const auto frozenSource=source;
        auto expected=initial,actual=initial,ordinary=initial;
        const unsigned top=(trial/13)%height,left=(trial/17)%width;
        const unsigned bottom=height,right=width;
        for(unsigned y=top;y<bottom;++y)for(unsigned x=left;x<right;++x)
            expected[da+y*ds+x]=source[sa+y*ss+x];
        uint8_t bounds[8],clip[8],drawn[8],oldDrawn[8];
        rect(bounds,-5,-7,int(height)-5,int(width)-7);
        rect(clip,int(top)-5,int(left)-7,int(bottom)-5,int(right)-7);
        CopyBits8::RowSpan spans[24];
        CopyBits8::Changes changes={spans,24,0,0,0,false,scalarRows};
        assert(CopyBits8::copy(source.data()+sa,ss*height,ss,bounds,
            actual.data()+da,ds*height,ds,bounds,bounds,bounds,bounds,bounds,clip,drawn,
            nullptr,nullptr,0,nullptr,&changes));
        assert(CopyBits8::copy(source.data()+sa,ss*height,ss,bounds,
            ordinary.data()+da,ds*height,ds,bounds,bounds,bounds,bounds,bounds,clip,oldDrawn));
        assert(actual==expected && ordinary==expected && source==frozenSource);
        for(unsigned i=0;i<8;++i)assert(drawn[i]==oldDrawn[i]);
        assert(changes.valid && changes.top==int(top)-5 && changes.left==int(left)-7);
        assert(changes.count==bottom-top);
        const unsigned called=calls;
        for(unsigned y=top;y<bottom;++y) {
            unsigned first=right,last=left;
            for(unsigned x=left;x<right;++x)if(initial[da+y*ds+x]!=expected[da+y*ds+x]) {
                if(first==right)first=x;last=x+1;
            }
            const auto span=spans[y-top];
            assert(span.left<=span.right && span.right<=right-left);
            if(first==right)assert(span.left==span.right);
            else assert(span.left==first-left && span.right==last-left);
        }
        // A report that cannot hold the rows must retain the ordinary copy.
        actual=initial;changes.capacity=0;changes.valid=true;
        assert(CopyBits8::copy(source.data()+sa,ss*height,ss,bounds,
            actual.data()+da,ds*height,ds,bounds,bounds,bounds,bounds,bounds,clip,drawn,
            nullptr,nullptr,0,nullptr,&changes));
        assert(!changes.valid && actual==expected && calls==called);
        // Overlapping buffers retain the existing traversal and no row report.
        auto overlap=initial,overlapExpected=initial;
        changes.capacity=24;changes.valid=true;
        assert(CopyBits8::copy(overlap.data()+da,ds*height,ds,bounds,
            overlap.data()+da,ds*height,ds,bounds,bounds,bounds,bounds,bounds,clip,drawn,
            nullptr,nullptr,0,nullptr,&changes));
        assert(!changes.valid && overlap==overlapExpected && calls==called);
        actual=initial;changes.copy=nullptr;changes.valid=true;
        assert(CopyBits8::copy(source.data()+sa,ss*height,ss,bounds,
            actual.data()+da,ds*height,ds,bounds,bounds,bounds,bounds,bounds,clip,drawn,
            nullptr,nullptr,0,nullptr,&changes));
        assert(!changes.valid && actual==expected && calls==called);
    }
    std::puts("PASS changed CopyBits rows: 8192 alignment/clipping/unchanged cases (up to 640 pixels), exact spans, padding and fallback controls");
}
