// Host checks for ResourceWriter.inc: the serialized fork layout, measure/serialize
// agreement, chunked source reads and sink failure handling.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include "../share/mac-runtime/ResourceWriter.inc"

static uint16_t be16(const uint8_t* p) { return uint16_t(p[0]<<8|p[1]); }
static uint32_t be32(const uint8_t* p) { return uint32_t(be16(p))<<16|be16(p+2); }

struct Bytes { std::vector<uint8_t> data; unsigned reads=0; };
static int32_t readBytes(void* c,uint32_t at,uint8_t* out,uint32_t size,uint32_t& actual) {
    auto& b=*(Bytes*)c;++b.reads;
    if(at>b.data.size() || size>b.data.size()-at)return -39;
    std::memcpy(out,b.data.data()+at,size);actual=size;return 0;
}
struct Memory { std::vector<uint8_t> out; uint32_t size=0; int begun=0,published=0,discarded=0; int failAt=-1,writes=0; };
static int32_t begin(void* c,uint32_t size) { auto& m=*(Memory*)c;++m.begun;m.size=size;m.out.assign(size,0xee);return 0; }
static int32_t write(void* c,uint32_t at,const uint8_t* p,uint32_t size,uint32_t& actual) {
    auto& m=*(Memory*)c;actual=0;
    if(m.writes++==m.failAt)return -36;
    assert(at<=m.size && size<=m.size-at && size<=ResourceForks::chunkBytes);
    std::memcpy(m.out.data()+at,p,size);actual=size;return 0;
}
static int32_t finish(void* c,bool publish) { auto& m=*(Memory*)c;(publish?m.published:m.discarded)++;return 0; }

int main() {
    const uint32_t PICT=0x50494354,SND=0x736e6420;
    Bytes big,small;
    big.data.resize(150000);for(size_t i=0;i<big.data.size();++i)big.data[i]=uint8_t(i*7+3);
    small.data={1,2,3,4,5};
    const ResourceForks::Source bs={&big,uint32_t(big.data.size()),readBytes},ss={&small,5,readBytes};
    const uint8_t name[]={'T','i','t','l','e'};
    // Types follow first appearance; a duplicate PICT 128 keeps recipe order.
    const ResourceWriter::Entry entries[]={
        {PICT,128,0x20,name,5,bs,0,150000},
        {SND,-1,0,nullptr,0,ss,1,3},
        {PICT,128,0,name,0,ss,0,5},
    };
    uint32_t measured=0;assert(ResourceWriter::measure(entries,3,measured)==0);
    Memory m;ResourceWriter::Sink sink={&m,begin,write,finish};
    assert(ResourceWriter::serialize(entries,3,sink)==0);
    assert(m.begun==1 && m.published==1 && m.discarded==0 && m.size==measured && big.reads==3);
    const uint8_t* f=m.out.data();
    const uint32_t dataOffset=be32(f),mapOffset=be32(f+4),dataBytes=be32(f+8),mapBytes=be32(f+12);
    assert(dataOffset==256 && dataBytes==(4+150000)+(4+3)+(4+5) && mapOffset==((256+dataBytes+1)&~1u));
    assert(mapOffset+mapBytes==measured && f[256+dataBytes]==0);
    const uint8_t* map=f+mapOffset;
    assert(std::memcmp(map,f,16)==0 && be16(map+24)==28 && be16(map+28)==1);
    const uint8_t* names=map+be16(map+26);
    assert(be32(map+30)==PICT && be16(map+34)==1 && be32(map+38)==SND && be16(map+42)==0);
    const uint8_t* refs=map+28+be16(map+36);
    // PICT references: both 128s in recipe order, the first named with attrs $20.
    assert(be16(refs)==128 && be16(refs+2)==0 && refs[4]==0x20 && (be32(refs+4)&0xffffff)==0);
    assert(names[0]==5 && std::memcmp(names+1,"Title",5)==0);
    assert(be16(refs+12)==128 && be16(refs+14)==6 && names[6]==0 && (be32(refs+16)&0xffffff)==4+150000+4+3);
    const uint8_t* sref=map+28+be16(map+44);
    assert(int16_t(be16(sref))==-1 && be16(sref+2)==0xffff && (be32(sref+4)&0xffffff)==4+150000);
    const uint8_t* body=f+256;
    assert(be32(body)==150000 && std::memcmp(body+4,big.data.data(),150000)==0);
    assert(be32(body+150004)==3 && std::memcmp(body+150008,small.data.data()+1,3)==0);
    assert(be32(body+150011)==5 && std::memcmp(body+150015,small.data.data(),5)==0);
    // A failed sink write discards staging and publishes nothing.
    for(int at=0;at<4;++at) {
        Memory bad;bad.failAt=at;ResourceWriter::Sink s={&bad,begin,write,finish};
        assert(ResourceWriter::serialize(entries,3,s)==-36 && bad.published==0 && bad.discarded==1);
    }
    // Validation rejects out-of-range payloads before any sink call.
    const ResourceWriter::Entry wrong[]={{PICT,1,0,nullptr,0,ss,3,3}};
    Memory none;ResourceWriter::Sink s={&none,begin,write,finish};
    assert(ResourceWriter::serialize(wrong,1,s)==-50 && none.begun==0 && ResourceWriter::measure(wrong,1,measured)==-50);
    std::puts("RESOURCE WRITER PASS: layout, duplicate order, chunked reads, sink failures");
}
