#ifndef TEST_RESOURCE_FORKS_H
#define TEST_RESOURCE_FORKS_H
#include <stdint.h>
// The part of a consumer's ResourceForks.h that ResourceWriter.inc uses.
class ResourceForks {
public:
    static const uint16_t kMaximumResources=4096;
    static const uint32_t chunkBytes=65536,maximumMapBytes=262144;
    struct Source {
        void* context;
        uint32_t size;
        int32_t (*read)(void*,uint32_t,uint8_t*,uint32_t,uint32_t&);
    };
};
#endif
