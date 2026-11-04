// Shared DOS publication for Resource Manager writes: buffer, then replace in place.
#include <proto/dos.h>
#include <dos/dos.h>
#include "ResourceStage.h"
// The including adapter supplies RESOURCE_STAGE_SYSTEM_WINDOW(function, context),
// which runs function(context) where DOS may be called and returns its result.
extern "C" {
#include <string.h>
}
#ifndef RESOURCE_STAGE_SYSTEM_WINDOW
#error Define RESOURCE_STAGE_SYSTEM_WINDOW to the port system-window bridge
#endif
namespace {
struct StageRequest { const char* path;const uint8_t* bytes;uint32_t size; };
// A missing target is fine (it is created). An existing one must be a writable
// file: directories are -50 (paramErr), write-protected files -45 (fLckdErr).
int32_t stageCheck(void* context) {
    const StageRequest& r=*(StageRequest*)context;
    BPTR lock=Lock((CONST_STRPTR)r.path,ACCESS_READ);
    if(!lock)return IoErr()==ERROR_OBJECT_NOT_FOUND ? 0 : -36;
    FileInfoBlock* info=(FileInfoBlock*)AllocDosObject(DOS_FIB,0);
    int32_t error=!info ? -108 : !Examine(lock,info) ? -36 : info->fib_DirEntryType>=0 ? -50
                 : (info->fib_Protection&FIBF_WRITE) ? -45 : 0;
    if(info)FreeDosObject(DOS_FIB,info);
    UnLock(lock);return error;
}
int32_t stageReplace(void* context) {
    const StageRequest& r=*(StageRequest*)context;
    BPTR file=Open((CONST_STRPTR)r.path,MODE_NEWFILE);if(!file)return -36;
    int32_t error=0;
    for(uint32_t at=0;!error && at<r.size;) {
        uint32_t n=r.size-at;if(n>65536)n=65536;
        if(Write(file,(APTR)(r.bytes+at),n)!=(LONG)n)error=-36;
        at+=n;
    }
    if(!Close(file))error=-36;
    return error;
}
}
bool ResourceStage::bind(const char* path) {
    if(active() || !path || !*path)return false;
    // Volatile stores avoid the m68k compiler's shared-base byte-copy form.
    volatile char* out=path_;uint16_t n=0;
    while(path[n]) { if(n>=sizeof(path_)-1) { path_[0]=0;return false; } out[n]=path[n];++n; }
    out[n]=0;return true;
}
int32_t ResourceStage::begin(void* context,uint32_t size) {
    if(!context)return -50;
    auto& s=*(ResourceStage*)context;
    if(!s.path_[0] || s.active())return -50;
    if(size>maximumBytes)return -108;
    StageRequest r={s.path_,0,0};
    int32_t error=RESOURCE_STAGE_SYSTEM_WINDOW(stageCheck,&r);if(error)return error;
    s.bytes_=new uint8_t[size?size:1];if(!s.bytes_)return -108;
    s.size_=size;s.written_=0;return 0;
}
int32_t ResourceStage::write(void* context,uint32_t offset,const uint8_t* bytes,uint32_t size,uint32_t& actual) {
    actual=0;if(!context || (!bytes && size) || size>65536)return -50;
    auto& s=*(ResourceStage*)context;
    if(!s.bytes_ || offset!=s.written_ || size>s.size_-offset)return -50;
    if(size)memcpy(s.bytes_+offset,bytes,size);
    s.written_+=size;actual=size;return 0;
}
// publish=false discards the buffer and leaves the target untouched. A failed
// in-place write can leave the target truncated, as on the original.
int32_t ResourceStage::finish(void* context,bool publish) {
    if(!context)return -50;
    auto& s=*(ResourceStage*)context;
    int32_t error=0;
    if(publish) {
        if(!s.bytes_ || s.written_!=s.size_)error=-36;
        else { StageRequest r={s.path_,s.bytes_,s.size_};error=RESOURCE_STAGE_SYSTEM_WINDOW(stageReplace,&r); }
    }
    delete[] s.bytes_;s.bytes_=0;s.size_=s.written_=0;return error;
}
