#pragma once
#include <array>
#include <cstdint>

// Regression fixture, not a StripAddress implementation. Adapt each production
// dispatch path to Snapshot -> Snapshot, including its trap PC advancement.
namespace amigaxdev { namespace strip_address_checks {
constexpr std::array<uint32_t, 6> values{{0, 0x123456, 0x41c27330, 0x40000000,
                                         0x7fff8000, 0x81234567}};
struct Snapshot {
    std::array<uint32_t, 15> regs; // D0-D7, A0-A6
    uint32_t pc;
    uint16_t sr;
    uint8_t mode, low_mode;
};
inline uint16_t flags(uint32_t value, uint16_t incoming) {
    return (incoming & 16) | ((value & 65535) == 0 ? 4 : 0) | (value & 0x8000 ? 8 : 0);
}
// Native pointers are physical, even when the emulated logical mode is 24 bit.
// On failure report the input and result through the caller's assertion/logger.
template<class Dispatch, class Report>
unsigned native(Dispatch dispatch, Report report, uint32_t pc) {
    unsigned checked = 0;
    for (uint32_t value : values) for (unsigned mode = 0; mode < 2; ++mode)
        for (unsigned cc = 0; cc < 32; ++cc) {
            Snapshot before{};
            for (unsigned i = 0; i < 15; ++i) before.regs[i] = i ? 0x12340000 + i : value;
            before.pc = pc; before.sr = cc; before.mode = before.low_mode = mode;
            Snapshot after = dispatch(before);
            bool ok = after.regs == before.regs && after.pc == pc + 2 &&
                after.sr == flags(value, cc) && after.mode == mode && after.low_mode == mode;
            report(ok, before, after);
            ++checked;
        }
    return checked;
}
// The measured System 7.5.5 24-bit logical-address contract is deliberately
// separate: strip the tag, retain X, set N/Z from the low word, clear V/C.
template<class Dispatch, class Report>
unsigned original24(Dispatch dispatch, Report report) {
    unsigned checked = 0;
    for (uint32_t value : values) for (unsigned cc = 0; cc < 32; ++cc) {
        auto result = dispatch(value, cc);
        uint32_t logical = value & 0xffffff;
        report(result.first == logical && result.second == flags(logical, cc));
        ++checked;
    }
    return checked;
}
} }
