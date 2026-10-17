#include <cstdint>
#include <cstdio>
#include "BlockMoveBytes.h"
#include "BlockMoveChecks.h"
int main() {
    auto checks=BlockMoveChecks::run(BlockMoveBytes::move);
    std::printf("BlockMove checks: %u\n",checks);
    return checks==28388?0:1;
}
