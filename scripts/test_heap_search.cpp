#include <initializer_list>
#include <cassert>
#include <cstdint>
#include <cstdio>
// Enumerate every eight-block free/occupied layout and every safe hint.
class MacHeap {
public:
    struct Block {uint32_t span,kind;};
    enum {freeBlock=0};
    Block blocks[8];
    uint32_t end_=8;
    mutable uint32_t searchStart_=0;
    static uint32_t physical(uint32_t bytes){return bytes;}
    const Block& block(uint32_t off) const{return blocks[off];}
    uint32_t findSpace(uint32_t bytes) const;
};
#include "../share/mac-runtime/HeapFindSpace.inc"
int main() {
    unsigned cases=0;
    for(unsigned mask=0;mask<256;++mask) {
        MacHeap h;unsigned first=8;
        for(unsigned i=0;i<8;++i){h.blocks[i]={1,(mask>>i)&1};if(!h.blocks[i].kind && first==8)first=i;}
        for(unsigned hint=0;hint<=first;++hint) {
            h.searchStart_=hint;
            for(unsigned size: {2u,1u,0u,1u,2u}) {
                auto old=h.searchStart_;
                unsigned expected=size==1 && first<8 ? first : 0;
                assert(h.findSpace(size)==expected);
                assert(h.searchStart_==(size?first:old));++cases;
            }
        }
    }
    std::printf("HEAP SEARCH PASS: %u first-fit layouts/hints/requests\n",cases);
}
