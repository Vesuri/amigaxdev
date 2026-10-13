#include <cstdint>
#include <cassert>
#include <vector>
namespace Pcm {
struct Layout {const uint8_t* pcm;uint32_t size,loopStart,loopEnd,attackBytes,reloadOffset,reloadBytes;};
struct Dma {Layout layout;uint16_t stride;};
#include "PcmDma.inc"
}
int main() {
    std::vector<uint8_t> source(515);for(unsigned i=0;i<source.size();++i)source[i]=i*37;
    for(unsigned alignment=0;alignment<4;++alignment)
    for(unsigned stride:{1u,2u,4u,8u,16u})
    for(unsigned end:{0u,102u,103u,210u}) {
        unsigned size=source.size()-alignment,start=end?3:0;
        unsigned attack=(((end?end:size)+stride-1)/stride+1)&~1u;
        unsigned cycle=end?(end-start):2;unsigned reload=cycle*2;
        Pcm::Dma dma={{source.data()+alignment,size,start,end,attack,attack,reload},uint16_t(stride)};
        std::vector<uint8_t> out(attack+reload+2,0x5a);
        Pcm::convert(dma,out.data()+1);
        assert(out.front()==0x5a && out.back()==0x5a);
        for(unsigned i=0;i<attack+(end?reload:2);++i) {
            unsigned at=i*stride;
            if(end && at>=end)at=start+(at-end)%(end-start);
            uint8_t expected=(!end && i>=attack)||at>=size?0:uint8_t(source[alignment+at]^0x80);
            assert(out[i+1]==expected);
        }
    }
}
