#ifndef TEST_DOS_DOS_H
#define TEST_DOS_DOS_H
// Host stand-in for the dos.library subset ResourceStage.inc uses. Files live in
// a map; every call is recorded so tests can prove which packets were sent.
#include <cstdint>
#include <map>
#include <string>
#include <vector>
typedef long LONG;typedef intptr_t BPTR;typedef void* APTR;typedef const unsigned char* CONST_STRPTR;
enum { ACCESS_READ=-2,MODE_NEWFILE=1006,ERROR_OBJECT_NOT_FOUND=205,DOS_FIB=2,FIBF_WRITE=4 };
struct FileInfoBlock { LONG fib_DirEntryType,fib_Protection,fib_Size; };
struct TestDos {
    struct Node { std::vector<uint8_t> bytes;bool directory=false;LONG protection=0; };
    std::map<std::string,Node> files;std::vector<std::string> calls;
    std::string open;bool failWrite=false,failOpen=false;LONG error=0;
};
inline TestDos testDos;
#endif
