#include <cassert>
#include <cstdint>
#include <cstdlib>
#include "PaulaChannelState.h"
#include "ImmutablePcmCache.h"
struct Plan {unsigned id=0,bytes=0;};
struct Memory {
    static bool fail;
    static unsigned live;
    static uint8_t* allocate(unsigned n) {
        if(fail)return nullptr;
        ++live;return static_cast<uint8_t*>(malloc(n));
    }
    static void free(uint8_t* p,unsigned) {--live;::free(p);}
};
bool Memory::fail=false;unsigned Memory::live=0;
struct Conversion {
    static unsigned calls;
    static bool equal(const Plan& a,const Plan& b){return a.id==b.id && a.bytes==b.bytes;}
    static unsigned bytes(const Plan& p){return p.bytes;}
    static void convert(const Plan& p,uint8_t* out){++calls;for(unsigned i=0;i<p.bytes;++i)out[i]=p.id+i;}
};
unsigned Conversion::calls=0;
int main() {
    PaulaChannelState channel;
    assert(!channel.quiet() && channel.disableLines()==579);
    channel.disabled();assert(channel.disableLines()==0 && !channel.quiet());
    channel.period(124);channel.markQuiet();
    assert(channel.quiet() && channel.disableLines()==0);
    channel.period(300);channel.started();
    assert(!channel.quiet() && channel.disableLines()==4);
    channel.period(124);assert(channel.disableLines()==4);
    channel.disabled();channel.period(124);channel.markQuiet();
    assert(channel.disableLines()==0);
    channel=PaulaChannelState();assert(channel.disableLines()==579);

    ImmutablePcmCache<Plan,Memory,Conversion,2,12> cache;
    auto* a=cache.acquire({1,6});assert(a && a->data[5]==6);
    auto* again=cache.acquire({1,6});assert(a==again && a->users==2 && Conversion::calls==1);
    auto* b=cache.acquire({2,6});assert(b && cache.retained()==12);
    assert(!cache.acquire({3,6})); // Never replace DMA-owned bytes.
    cache.release(a);assert(!cache.acquire({3,6}));
    cache.release(a);auto* c=cache.acquire({3,6});assert(c && c->data[5]==8);
    assert(b->data[5]==7 && Memory::live==2);
    cache.release(b);cache.release(c);cache.clearUnused();
    assert(cache.retained()==0 && Memory::live==0);
    Memory::fail=true;assert(!cache.acquire({4,6}));
    assert(cache.retained()==0);Memory::fail=false;
    assert(!cache.acquire({4,13}) && !cache.acquire({4,0}));
    a=cache.acquire({4,8});assert(a);
    assert(!cache.acquire({5,6})); // Budget, even though a slot is free.
    cache.release(a);b=cache.acquire({5,6});assert(b && cache.retained()==6);
    cache.release(b);cache.clearUnused();assert(Memory::live==0);
}
