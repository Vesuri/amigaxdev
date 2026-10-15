#include <cassert>
#include <cstdint>
class MacHeap {
public:
    using Handle=uint8_t**;
    enum {nilHandleErr=-109};
    uint8_t byte=0;
    unsigned lookups=0,publications=0;
    int16_t error=7;
    uint8_t* slot=nullptr;
    uint8_t* flags(Handle h){++lookups;return h==&slot ? &byte : nullptr;}
    int16_t queryResult(int16_t e){++publications;error=e;return e;}
    int16_t lockHandle(Handle);
};
#include "HeapLockHandle.inc"
int main() {
    for(unsigned bits=0;bits<256;++bits) {
        MacHeap h;h.byte=bits;
        assert(h.lockHandle(&h.slot)==(bits&1 ? 0 : -109));
        assert(h.byte==(bits&1 ? ((bits&0xe0)|0x81) : bits));
        assert(h.lookups==1 && h.publications==1);
        auto saved=h.byte;
        assert(h.lockHandle(nullptr)==-109 && h.byte==saved);
        assert(h.lookups==2 && h.publications==2);
    }
}
