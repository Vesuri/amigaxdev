#include <cstdint>
#include <cassert>
#include "VideoTicks.h"
static uint32_t micro(uint32_t line,uint32_t hp){
    uint32_t value=line*64+hp*64/227;return value<20000?value:19999;
}
int main(){
    for(uint32_t due=0;due<20000;++due){
        uint32_t threshold=VideoTicks::deadlinePALBeam(due),line=threshold>>8,hp=threshold&255;
        assert(hp<227 && micro(line,hp)>=due);
        if(threshold){
            uint32_t previousLine=hp?line:line-1,previousHP=hp?hp-1:226;
            assert(micro(previousLine,previousHP)<due);
        }
    }
    for(uint32_t line=0;line<313;++line)for(uint32_t hp=0;hp<227;++hp){
        uint32_t value=micro(line,hp),beam=line*256+hp;
        assert(beam>=VideoTicks::deadlinePALBeam(value));
        assert(beam<VideoTicks::deadlinePALBeam(value+1));
    }
    assert(VideoTicks::deadlinePALBeam(20000)==0xffffffffUL);
}
