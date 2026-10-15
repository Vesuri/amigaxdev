#include <cassert>
#include <cstdint>
class MacHeap {
public:
    using Handle=uint8_t**;
    enum {nilHandleErr=-109};
    uint8_t byte=0;
    unsigned lookups=0,queries=0;
    int16_t error=7;
    uint8_t* slot=nullptr;
    uint8_t* flags(Handle h){++lookups;return h==&slot ? &byte : nullptr;}
    int16_t queryResult(int16_t e){++queries;error=e;return e;}
    uint8_t state(Handle);
};
#include "HeapReadHandleState.inc"
int main() {
    for(unsigned bits=0;bits<256;++bits) {
        MacHeap h;h.byte=bits;
        assert(h.state(&h.slot)==(bits&1 ? bits&0xe0 : 0));
        assert(h.error==(bits&1 ? 0 : -109));
        assert(h.byte==bits && h.lookups==1 && h.queries==1);
        assert(h.state(nullptr)==0 && h.error==-109 && h.byte==bits);
        assert(h.lookups==2 && h.queries==2);
    }
}
