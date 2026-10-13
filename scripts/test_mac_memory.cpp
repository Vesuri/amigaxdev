#include <cassert>
#include <cstring>
#include <initializer_list>
#include "BigEndianMemory.h"
int main() {
    for(unsigned offset=0;offset<8;++offset) {
        for(uint32_t value:{0u,1u,0x12345678u,0x80000000u,0xffffffffu}) {
            uint8_t data[16];std::memset(data,0xa5,sizeof data);
            BigEndianMemory::write32(data+offset,value);
            for(unsigned i=0;i<16;++i)
                assert(data[i]==(i>=offset && i<offset+4 ? uint8_t(value>>(24-8*(i-offset))) : 0xa5));
            assert(BigEndianMemory::read32(data+offset)==value);
            assert(BigEndianMemory::read16(data+offset)==uint16_t(value>>16));
            BigEndianMemory::write16(data+offset+1,0xface);
            assert(BigEndianMemory::read16(data+offset+1)==0xface);
            assert(data[offset]==uint8_t(value>>24) && data[offset+3]==uint8_t(value));
        }
    }
}
