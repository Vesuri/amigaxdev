#include "VideoTicks.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
int main() {
    uint16_t phase=0;uint32_t ticks=0;
    for(uint32_t field=0;field<100;++field) {
        assert(ticks==field*6/5);
        for(uint32_t us=0;us<20000;++us) {
            uint32_t actual=VideoTicks::withinPALField(ticks,phase,uint16_t(us));
            uint32_t expected=uint32_t((uint64_t(field)*20000+us)*60/1000000);
            assert(actual==expected);
        }
        ticks+=VideoTicks::fieldDelta(true,phase);
    }
    assert(ticks==120 && phase==0);
    for(unsigned n=0;n<60;++n)assert(VideoTicks::fieldDelta(false,phase)==1);
    assert(phase==0);
    assert(VideoTicks::withinPALField(UINT32_MAX,0,16666)==UINT32_MAX);
    assert(VideoTicks::withinPALField(UINT32_MAX,0,16667)==0);
    // A repeated five-tick deadline: coarse field polling always skips the
    // requested deadline; within-field reads reach it without changing delay.
    for(bool fine:{false,true}) {
        uint32_t time=0,last=0;
        for(unsigned update=0;update<20;++update) {
            uint32_t current;
            do {
                time+=100;
                uint32_t field=time/20000;
                current=field*6/5;
                if(fine)current=VideoTicks::withinPALField(current,field%5,time%20000);
            } while(current-last<5);
            assert(current-last==(fine?5:6));last=current;
        }
        assert(last==(fine?100:120));
    }
    std::puts("VIDEO TICKS PASS: field phase, sub-field deadlines, NTSC and wrap");
}
