#include "VBLPasses.h"
#include <assert.h>
#include <stdio.h>
int main() {
    VBLPasses p;p.reset(100);p.observe(102);
    assert(p.begin(2) && p.tick==101 && p.pending==1);
    unsigned calls[2]={};
    while(p.index<p.limit)++calls[p.index++];
    p.active=false;
    assert(p.begin(2) && p.tick==102);
    while(p.index<p.limit)++calls[p.index++];
    p.active=false;
    assert(calls[0]==2 && calls[1]==2 && !p.begin(2));
    // Arrival during a callback preserves the current pass and its membership.
    p.observe(104);assert(p.begin(3));++p.index;
    p.observe(106);assert(!p.begin(4) && p.index==1 && p.limit==3);
    p.removed(0);assert(p.index==0 && p.limit==2 && p.active);
    ++p.index;p.removed(1);assert(!p.active && p.index==1 && p.limit==1);
    assert(p.begin(4) && p.tick==104 && p.limit==4);
    p.reset(0xfffffffeu);p.observe(1);
    unsigned passes=0;
    while(p.begin(1)) {++passes;p.active=false;}
    assert(passes==3 && p.tick==1 && !p.needed(1));
    p.pending=0xfffffffeu;p.observe(10);assert(p.pending==0xffffffffu);
    // Partitioning elapsed time into arbitrary PAL-field batches must conserve
    // every virtual retrace, including periods with no safe dispatch point.
    for(unsigned stride=1;stride<38;++stride) {
        p.reset(0);unsigned delivered=0;
        for(unsigned now=stride;now<=600;now+=stride) {
            p.observe(now);
            while(p.begin(2)) {++delivered;p.active=false;}
        }
        p.observe(600);
        while(p.begin(2)) {++delivered;p.active=false;}
        assert(delivered==600 && p.tick==600);
    }
    puts("VBL PASSES PASS: conservation, in-flight arrivals, removal, wrap and saturation");
}
