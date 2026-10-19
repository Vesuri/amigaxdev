#include <cstdint>
#include <cassert>
#include "AddressSpan.h"
static void check(uint32_t base,uint32_t size,uint32_t at,uint32_t n){
 bool valid=uint64_t(base)+size<=UINT32_MAX;
 assert(AddressSpan::valid(base,size)==valid);
 if(valid){bool expected=uint64_t(at)>=base && uint64_t(at)+n<=uint64_t(base)+size;
 assert(AddressSpan::contains(base,size,at,n)==expected);}
}
int main(){
 const uint32_t edges[]={0,1,7,8,9,65528,65535,65536,0x7fffffffU,0xfffffff7U,0xfffffff8U,0xffffffffU};
 for(auto b:edges)for(auto s:edges)for(auto p:edges)for(auto n:edges)check(b,s,p,n);
 uint32_t x=0x63451;
 for(unsigned i=0;i<1000000;++i){uint32_t v[4];for(auto& p:v){x=x*1664525U+1013904223U;p=x;}check(v[0],v[1],v[2],v[3]);}
}
