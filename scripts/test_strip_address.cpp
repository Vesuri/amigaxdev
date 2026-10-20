#include "StripAddressChecks.h"
#include <cassert>
#include <utility>
using namespace amigaxdev::strip_address_checks;
int main() {
    auto native_body = [](Snapshot s) { s.sr=flags(s.regs[0],s.sr); s.pc+=2; return s; };
    unsigned failures=0;
    auto report=[&](bool ok, const Snapshot&, const Snapshot&) { if(!ok) ++failures; };
    assert(native(native_body,report,0x1000)==384 && failures==0);
    // The old truncation and independently corrupted registers/mode/flags/PC
    // must each fail; checking only D0 would miss several of these controls.
    for(unsigned damage=0;damage<5;++damage) {
        failures=0;
        native([&](Snapshot s) { s=native_body(s);
            if(damage==0)s.regs[0]&=0xffffff;
            if(damage==1)++s.regs[8];
            if(damage==2)s.low_mode^=1;
            if(damage==3)s.sr^=16;
            if(damage==4)s.pc-=2;
            return s;
        },report,0x1000);
        assert(failures>0);
    }
    failures=0;
    assert(original24([](uint32_t v,uint16_t cc) {
        return std::make_pair(v&0xffffff,flags(v&0xffffff,cc));
    },[&](bool ok){if(!ok)++failures;})==192 && failures==0);
    original24([](uint32_t v,uint16_t cc) {
        return std::make_pair(v,flags(v,cc));
    },[&](bool ok){if(!ok)++failures;});
    assert(failures>0);
}
