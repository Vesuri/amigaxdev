#include "NativeServiceScope.h"
#include <assert.h>
int main(){
 NativeServiceScope s;s.configure(0x100,0x200,0x300);
 s.charge(7);s.after(0x300,0x4e75,0x400,true);assert(!s.faults); // pre-window tail
 s.exception(10,0x400,0xa055,true);s.charge(11);
 s.exception(27,0x150,0,true);s.charge(13);
 s.exception(26,0x160,0,true);s.charge(17);
 s.after(0x170,0x4e73,0x160,true);s.charge(19);
 s.after(0x180,0x4e73,0x150,true);s.charge(23);
 s.after(0x190,0x4e73,0x250,true);assert(s.depth==1); // user-mode bridge
 s.exception(10,0x410,0xa029,true);s.charge(29);
 s.after(0x100,0x4e73,0x412,true);s.charge(31);
 s.after(0x300,0x4e75,0x420,true);s.charge(37); // callback starts outside service
 assert(s.cost[0x55].units==65 && s.cost[0x55].irq==49);
 assert(s.cost[0x29].units==29 && s.cost[0x29].returns==1);
 assert(s.unscoped==44 && s.depth==0 && s.irqDepth==0 && !s.faults);
 s.exception(10,0x500,0xa069,true);s.charge(41);s.reset();
 assert(s.cost[0x69].before==1 && !s.cost[0x69].calls);
 s.charge(43);s.after(0x200,0x4e73,0x502,true);
 assert(s.cost[0x69].units==43 && s.cost[0x69].returns==1 && !s.depth);
 s.after(0x200,0x4e73,0x502,true);assert(s.faults==1);
 s.configure(0x100,0x200,0x300);s.exception(10,0,0xa069,true);
 s.after(0x100,0x4e75,0,true);assert(s.faults==1 && s.depth==1);
 s.configure(0x100,0x200,0x300);
 for(int i=0;i<65;++i)s.exception(10,0,0xa055,true);
 assert(s.faults==1 && s.depth==64);
 s.configure(0x100,0x200,0x300);
 s.exception(27,0x500,0,true);s.exception(10,0,0xa055,true);assert(!s.depth);
 s.reset();assert(s.irqBefore==1);
 s.after(0x150,0x4e73,0x501,true);assert(s.irqDepth==1);
 s.after(0x150,0x4e73,0x500,true);assert(!s.irqDepth && s.irqExited==1);
 s.configure(0x100,0x200,0x300,0x100,0x400);
 s.exception(10,0x900,0xa055,true);
 s.charge(2,0x900);s.charge(3,0x200);s.charge(5,0xf80000);
 s.charge(7,0x800);
 assert(s.cost[0x55].units==17 && s.cost[0x55].foreign==7);
 s.exception(8,0,0,true);assert(s.faults==1);
 s.configure(0x100,0x200,0x300);
 s.exception(10,0x900,0xa055,false);s.reset();
 assert(s.cost[0x55].before==1 && s.cost[0x55].calls==0);
 s.charge(11);s.after(0x300,0x4e75,0x902,true);
 assert(s.cost[0x55].returns==1 && !s.depth);
 s.configure(0x100,0x200,0x300,0x100,0x400);
 s.execLow=0x800;s.execHigh=0x80c;
 s.exception(10,0x900,0xa05d,true);
 s.charge(2,0x800,true);s.charge(3,0x806,true);s.charge(5,0x802,true);
 assert(s.cost[0x5d].units==10 && s.cost[0x5d].foreign==5);
 s.exception(8,0xf80000,0,true,true);assert(!s.faults && s.privilegeCalls==1);
 s.charge(7,0xf80000);assert(s.cost[0x5d].units==17);
 s.charge(11,0x800,false);assert(s.cost[0x5d].foreign==16);
 s.exception(8,0xf80100,0,true,false);assert(s.faults==1);
}
