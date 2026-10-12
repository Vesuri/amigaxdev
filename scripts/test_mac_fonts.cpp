#include <cassert>
#include <cstdint>
#include <cstring>
#include "BitmapFont.h"
#include "BitmapText8.h"
static void w(uint8_t* p,uint16_t n){p[0]=n>>8;p[1]=n;}
int main(){
 uint8_t family[60]={};w(family+2,7);w(family+4,65);w(family+6,66);w(family+50,2);w(family+54,12);w(family+58,9);
 BitmapFont::Family selected;
 assert(BitmapFont::association(family,60,7,12,0,selected)&&selected.bitmap==9);
 assert(!BitmapFont::association(family,60,7,13,0,selected));
 assert(!BitmapFont::association(family,60,7,12,1,selected));
 for(unsigned n=0;n<60;++n)assert(!BitmapFont::association(family,n,7,12,0,selected));
 uint8_t data[54]={};uint16_t header[]={0x9001,65,66,4,0xffff,0xffff,4,2,11,1,1,0,1};
 for(unsigned i=0;i<13;++i)w(data+2*i,header[i]);
 w(data+26,0xa000);w(data+28,0x5000);
 uint16_t locations[]={0,2,2,4},widths[]={0x0103,0xffff,2,0xffff};
 for(unsigned i=0;i<4;++i){w(data+30+2*i,locations[i]);w(data+38+2*i,widths[i]);}
 BitmapFont font;assert(font.openBitmap(data,sizeof data));
 assert(font.ascent()==1 && font.descent()==1 && font.advance()==4 && font.leading()==0);
 assert(font.integerWidth('A')==3 && font.integerWidth('B')==2 && font.integerWidth('Z')==2);
 assert(font.leftBearing('A')==0 && font.leftBearing('B')==-1 && font.imageWidth('A')==2);
 for(unsigned n=0;n<sizeof data;++n){BitmapFont bad;assert(!bad.openBitmap(data,n));}
 uint8_t unaligned[55];std::memcpy(unaligned+1,data,sizeof data);assert(font.openBitmap(unaligned+1,sizeof data));
 assert(font.openBitmap(data,sizeof data));uint8_t pixels[16]={},rect[8]={},dirty[8];w(rect+4,4);w(rect+6,4);
 int16_t pen=1;const uint8_t text[]={'A'};
 assert(BitmapText8::draw(pixels,16,4,rect,rect,rect,rect,font,text,1,2,pen,7,dirty));
 assert(pen==4);
 for(unsigned i=0;i<16;++i)assert(pixels[i]==((i==5||i==10)?7:0));
 std::memset(pixels,0,16);uint8_t clip[8];std::memcpy(clip,rect,8);w(clip+2,2);pen=1;
 assert(BitmapText8::draw(pixels,16,4,rect,rect,rect,clip,font,text,1,2,pen,7,dirty));
 for(unsigned i=0;i<16;++i)assert(pixels[i]==(i==10?7:0));
 pen=1;assert(!BitmapText8::draw(pixels,15,4,rect,rect,rect,rect,font,text,1,2,pen,7,dirty));
 w(data+32,17);BitmapFont bad;assert(!bad.openBitmap(data,sizeof data));
}
