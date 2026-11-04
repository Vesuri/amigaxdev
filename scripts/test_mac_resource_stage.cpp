// Host checks for ResourceStage.inc against a recorded DOS stand-in: publication
// replaces the target in place with MODE_NEWFILE and never renames, deletes or
// creates other files; discards and refusals leave the target untouched.
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include "proto/dos.h"
static int windows=0;
static int32_t window(int32_t (*f)(void*),void* c) { ++windows;return f(c); }
#define RESOURCE_STAGE_SYSTEM_WINDOW window
#include "../share/mac-runtime/ResourceStage.inc"

static bool onlyCalls(std::initializer_list<const char*> allowed) {
    for(const auto& c:testDos.calls) {
        bool ok=false;for(const char* a:allowed)if(c==a)ok=true;
        if(!ok)return false;
    }
    return true;
}
static std::vector<uint8_t> pattern(uint32_t n) {
    std::vector<uint8_t> v(n);for(uint32_t i=0;i<n;++i)v[i]=uint8_t(i*13+1);return v;
}
static int32_t publish(const char* path,const std::vector<uint8_t>& bytes,bool commit=true) {
    ResourceStage stage;if(!stage.bind(path))return -999;
    auto sink=stage.sink();int32_t error=sink.begin(sink.context,uint32_t(bytes.size()));
    for(uint32_t at=0;!error && at<bytes.size();) {
        uint32_t n=uint32_t(bytes.size())-at;if(n>65536)n=65536;uint32_t actual=0;
        error=sink.write(sink.context,at,bytes.data()+at,n,actual);
        assert(error || actual==n);at+=n;
    }
    int32_t finished=sink.finish(sink.context,commit && !error);
    return error ? error : finished;
}
int main() {
    const char* path="Save.rsrc";
    // Replace an existing file in place, in 64 KiB writes, and touch nothing else.
    testDos={};testDos.files[path].bytes={9,9,9};
    auto big=pattern(150000);
    assert(publish(path,big)==0 && testDos.files[path].bytes==big && testDos.files.size()==1);
    assert(onlyCalls({"Lock","UnLock","Open","Write","Close"}) && windows==2);
    unsigned writes=0;for(auto& c:testDos.calls)writes+=c=="Write";
    assert(writes==3);
    // A missing target is created; an empty fork still truncates.
    testDos={};assert(publish(path,pattern(10))==0 && testDos.files[path].bytes==pattern(10));
    assert(publish(path,{})==0 && testDos.files[path].bytes.empty());
    // Discarding leaves the target untouched and opens nothing.
    testDos={};testDos.files[path].bytes={1,2,3};
    assert(publish(path,pattern(100),false)==0 && (testDos.files[path].bytes==std::vector<uint8_t>{1,2,3}));
    assert(onlyCalls({"Lock","UnLock"}));
    // Directories and write-protected files are refused before buffering.
    testDos={};testDos.files[path].directory=true;assert(publish(path,pattern(4))==-50);
    testDos={};testDos.files[path].protection=FIBF_WRITE;testDos.files[path].bytes={7};
    assert(publish(path,pattern(4))==-45 && testDos.files[path].bytes==std::vector<uint8_t>{7} && onlyCalls({"Lock","UnLock"}));
    // Oversized forks and DOS failures report errors.
    testDos={};assert(publish(path,std::vector<uint8_t>(ResourceStage::maximumBytes+1))==-108 && testDos.files.empty());
    testDos={};testDos.failOpen=true;assert(publish(path,pattern(4))==-36);
    testDos={};testDos.failWrite=true;assert(publish(path,pattern(4))==-36);
    // Writes must be sequential and within the declared size; bind refuses long paths.
    {
        testDos={};ResourceStage s;assert(s.bind(path));auto k=s.sink();uint32_t actual=0;uint8_t b[8]={};
        assert(k.begin(k.context,8)==0 && s.active());
        assert(k.write(k.context,4,b,4,actual)==-50 && k.write(k.context,0,b,9,actual)==-50);
        assert(k.write(k.context,0,b,8,actual)==0 && actual==8 && !s.bind(path));
        assert(k.finish(k.context,true)==0 && !s.active());
        std::string longPath(192,'x');assert(!s.bind(longPath.c_str()));
    }
    std::puts("RESOURCE STAGE PASS: in-place replace, no rename or staging files, discard, refusals, errors");
}
