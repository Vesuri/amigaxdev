#include <cassert>
#include <cstdint>
#include <cstring>
#include "RectBounds.h"
static void words(uint8_t* p,const uint16_t* v) {for(unsigned i=0;i<4;++i){p[2*i]=v[i]>>8;p[2*i+1]=v[i];}}
int main() {
 const uint16_t cases[][10]={
  {0,0,10,20,3,2,2,3,8,17},
  {20,30,10,15,2,3,23,32,7,13},
  {0x7fff,0xffff,0x8000,0,1,1,0x8000,0,0x7fff,0xffff}
 };
 for(auto& c:cases){uint8_t rect[8],expected[8];words(rect,c);words(expected,c+6);RectBounds::adjust(rect,c[4],c[5],0xa8a9);assert(!std::memcmp(rect,expected,8));}
 const uint16_t start[]={0x7fff,0xffff,0x8000,0}, shifted[]={0x8000,0,0x8001,1};
 uint8_t rect[8],expected[8];words(rect,start);words(expected,shifted);
 RectBounds::adjust(rect,1,1,0xa8a8);assert(!std::memcmp(rect,expected,8));
 RectBounds::adjust(rect,0xffff,0xffff,0xa8a8);words(expected,start);assert(!std::memcmp(rect,expected,8));
 const uint16_t a[]={1,2,10,20},b[]={3,4,30,40},u[]={1,2,30,40},i[]={3,4,10,20};
 uint8_t ra[8],rb[8];words(ra,a);words(rb,b);words(expected,u);
 assert(RectBounds::unite(ra,ra,rb));assert(!std::memcmp(ra,expected,8));
 words(ra,a);bool nonempty=false;words(expected,i);
 assert(RectBounds::intersect(rb,ra,rb,nonempty)&&nonempty);assert(!std::memcmp(rb,expected,8));
}
