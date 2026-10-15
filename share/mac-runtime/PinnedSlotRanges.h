#pragma once
// Fixed-width types come from the caller. Cache only immutable master-block
// ranges, never allocation flags or pointees. Clear whenever the arena resets.
class PinnedSlotRanges {
public:
    struct Range {uint32_t start=0,length=0;};
private:
    Range ranges_[16]={};
    const void* lastSlot_=nullptr;
    uint8_t* lastFlags_=nullptr;
public:
    void clear(){for(auto& r:ranges_)r=Range();lastSlot_=nullptr;lastFlags_=nullptr;}
    // The caller supplies this mapping only after validating a pinned slot.
    // Cache its address, never its mutable flags or pointee. Reset clears both
    // kinds of mapping before any old master storage may be reused.
    uint8_t* cachedFlags(const void* slot) const {return slot==lastSlot_?lastFlags_:nullptr;}
    uint8_t* rememberFlags(const void* slot,uint8_t* flags) {
        lastSlot_=slot;lastFlags_=flags;return flags;
    }
    void remember(uint32_t position,uint32_t start,uint32_t length){
        ranges_[(position>>8)&15]={start,length};
    }
    template<unsigned SlotBytes> const Range* find(uint32_t position) const {
        const auto& r=ranges_[(position>>8)&15];
        uint32_t offset=position-r.start;
        return offset<r.length && !(offset%SlotBytes) ? &r : nullptr;
    }
};
