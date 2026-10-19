#include <cstdint>
#include <cassert>
namespace Division {
#include "UnsignedDivide.inc"
}
int main(){
    unsigned long long random=0x83e473991035ef83ULL;
    for(unsigned i=0;i<1000000;++i) {
        random=random*6364136223846793005ULL+1;auto numerator=random;
        random=random*6364136223846793005ULL+1;auto denominator=(i&1) ? random : random>>32;
        uint32_t result=0;bool okay=Division::divide(numerator,denominator,result);
        assert(okay==(denominator && numerator/denominator<=0xffffffffULL));
        if(okay)assert(result==numerator/denominator);
    }
    uint32_t quotient=0;assert(!Division::divide(1,0,quotient));
    assert(Division::divide(0xffffffffffffffffULL,0xffffffffffffffffULL,quotient) && quotient==1);
    assert(!Division::divide(0x100000000ULL,1,quotient));
    for(unsigned n=0;n<64;++n)for(unsigned d=0;d<64;++d)
        for(unsigned edge=0;edge<3;++edge) {
            auto numerator=(1ULL<<n)-(edge==0 ? 1 : 0)+(edge==2 ? 1 : 0);
            auto denominator=(1ULL<<d);
            for(unsigned delta=0;delta<2;++delta) {
                auto divisor=denominator+delta;
                bool okay=Division::divide(numerator,divisor,quotient);
                assert(okay==(numerator/divisor<=0xffffffffULL));
                if(okay)assert(quotient==numerator/divisor);
            }
        }
}
