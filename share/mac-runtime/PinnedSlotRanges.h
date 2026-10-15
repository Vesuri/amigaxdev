#pragma once
// Fixed-width types come from the caller. Cache only immutable master-block
// ranges, never allocation flags or pointees. Clear whenever the arena resets.
class PinnedSlotRanges {
public:
    struct Range {uint32_t start=0,length=0;};
private:
    Range ranges_[16]={};
public:
    void clear(){for(auto& r:ranges_)r=Range();}
    void remember(uint32_t position,uint32_t start,uint32_t length){
        ranges_[(position>>8)&15]={start,length};
    }
    template<unsigned SlotBytes> const Range* find(uint32_t position) const {
        const auto& r=ranges_[(position>>8)&15];
        uint32_t offset=position-r.start;
        return offset<r.length && !(offset%SlotBytes) ? &r : nullptr;
    }
};
