"""Check a Unicorn library for the arm64 constant subtract-with-borrow fix:

    python3 -I scripts/test_unicorn.py LIBUNICORN

X and the source of SUBX are constants here, so Unicorn's TCG folds the subtraction to
sub2 with a constant low part.  Unpatched 2.1.4 encodes that as an invalid arm64
instruction and this process dies with SIGILL (patches/unicorn-aarch64-addsub2.patch).
"""

import ctypes as C
import sys

ARCH_M68K, MODE_BIG_ENDIAN, CPU_M68K_M68020 = 7, 1 << 30, 2
CTL_WRITE_CPU_MODEL = 7 | (1 << 26) | (1 << 30)  # UC_CTL_WRITE(UC_CTL_CPU_MODEL, 1)
REG_D2 = 11
BASE = 0x10000
# sub.w #0,d0 (X = 0); moveq #76,d6; subx.w d6,d2; nop
CODE = bytes.fromhex("907c0000" "7c4c" "9546" "4e71")

uc = C.CDLL(sys.argv[1])
uc.uc_open.argtypes = [C.c_int, C.c_int, C.POINTER(C.c_void_p)]
uc.uc_ctl.argtypes = [C.c_void_p, C.c_int]
uc.uc_mem_map.argtypes = [C.c_void_p, C.c_uint64, C.c_size_t, C.c_uint32]
uc.uc_mem_write.argtypes = [C.c_void_p, C.c_uint64, C.c_char_p, C.c_size_t]
uc.uc_reg_write.argtypes = [C.c_void_p, C.c_int, C.c_void_p]
uc.uc_reg_read.argtypes = [C.c_void_p, C.c_int, C.c_void_p]
uc.uc_emu_start.argtypes = [C.c_void_p, C.c_uint64, C.c_uint64, C.c_uint64, C.c_size_t]


def ok(err: int, what: str) -> None:
    if err:
        sys.exit(f"{what}: error {err}")


h = C.c_void_p()
ok(uc.uc_open(ARCH_M68K, MODE_BIG_ENDIAN, C.byref(h)), "uc_open")
ok(uc.uc_ctl(h, CTL_WRITE_CPU_MODEL, C.c_int(CPU_M68K_M68020)), "uc_ctl")
ok(uc.uc_mem_map(h, BASE, 0x1000, 7), "uc_mem_map")
ok(uc.uc_mem_write(h, BASE, CODE, len(CODE)), "uc_mem_write")
d2 = C.c_uint32(0x1000)
ok(uc.uc_reg_write(h, REG_D2, C.byref(d2)), "uc_reg_write")
ok(uc.uc_emu_start(h, BASE, BASE + len(CODE) - 2, 0, 0), "uc_emu_start")
ok(uc.uc_reg_read(h, REG_D2, C.byref(d2)), "uc_reg_read")
if d2.value != 0x1000 - 76:
    sys.exit(f"subx.w: d2 = {d2.value:#x}, want {0x1000 - 76:#x}")
