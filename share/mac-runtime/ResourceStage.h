#ifndef AMIGAXDEV_RESOURCE_STAGE_H
#define AMIGAXDEV_RESOURCE_STAGE_H
#include "ResourceWriter.h"
// DOS sink for ResourceWriter: buffers the whole fork, then replaces the target
// in place, as the original Resource Manager writes its file. No rename, no
// staging files: WHDLoad's kickfs has neither ACTION_RENAME_OBJECT nor
// ACTION_SET_FILE_SIZE, and MODE_NEWFILE truncates through both it and native DOS.
// DOS calls run inside the adapter's RESOURCE_STAGE_SYSTEM_WINDOW. The caller
// closes old target streams before publication.
class ResourceStage {
public:
    static const uint32_t maximumBytes=2UL*1024*1024;
    bool bind(const char* path);
    ResourceWriter::Sink sink() { return {this,begin,write,finish}; }
    bool active() const { return bytes_!=0; }
    ~ResourceStage() { delete[] bytes_; }
private:
    char path_[192]={};
    uint8_t* bytes_=0;
    uint32_t size_=0,written_=0;
    static int32_t begin(void*,uint32_t);
    static int32_t write(void*,uint32_t,const uint8_t*,uint32_t,uint32_t&);
    static int32_t finish(void*,bool);
};
#endif
