#ifndef TEST_PROTO_DOS_H
#define TEST_PROTO_DOS_H
#include "../dos/dos.h"
inline BPTR Lock(CONST_STRPTR p,LONG) {
    auto& d=testDos;d.calls.push_back("Lock");auto i=d.files.find((const char*)p);
    if(i==d.files.end()) { d.error=ERROR_OBJECT_NOT_FOUND;return 0; }
    return (BPTR)&i->second;
}
inline LONG IoErr() { return testDos.error; }
inline void UnLock(BPTR) { testDos.calls.push_back("UnLock"); }
inline APTR AllocDosObject(LONG,void*) { return new FileInfoBlock(); }
inline void FreeDosObject(LONG,APTR p) { delete (FileInfoBlock*)p; }
inline LONG Examine(BPTR l,FileInfoBlock* f) {
    auto& n=*(TestDos::Node*)l;f->fib_DirEntryType=n.directory?2:-3;f->fib_Protection=n.protection;
    f->fib_Size=LONG(n.bytes.size());return 1;
}
inline BPTR Open(CONST_STRPTR p,LONG mode) {
    auto& d=testDos;d.calls.push_back("Open");
    if(mode!=MODE_NEWFILE || d.failOpen)return 0;
    d.open=(const char*)p;d.files[d.open].bytes.clear();return 1;
}
inline LONG Write(BPTR,APTR b,LONG n) {
    auto& d=testDos;d.calls.push_back("Write");if(d.failWrite)return -1;
    auto& v=d.files[d.open].bytes;v.insert(v.end(),(uint8_t*)b,(uint8_t*)b+n);return n;
}
inline LONG Close(BPTR) { testDos.calls.push_back("Close");return 1; }
#endif
