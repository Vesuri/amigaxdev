"""Resolve macOS displays to SDL desktop coordinates, without GUI automation."""
import ctypes
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Display:
    identifier: int
    x: float
    y: float
    width: float
    height: float
    primary: bool


def active_displays():
    if sys.platform != "darwin":
        raise RuntimeError("AMIGA_MONITOR currently requires macOS")

    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    class Size(ctypes.Structure):
        _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

    class Rect(ctypes.Structure):
        _fields_ = [("origin", Point), ("size", Size)]

    cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    display_id = ctypes.c_uint32
    cg.CGMainDisplayID.argtypes = []
    cg.CGMainDisplayID.restype = display_id
    cg.CGGetActiveDisplayList.argtypes = [ctypes.c_uint32, ctypes.POINTER(display_id),
                                        ctypes.POINTER(ctypes.c_uint32)]
    cg.CGGetActiveDisplayList.restype = ctypes.c_int32
    cg.CGDisplayBounds.argtypes = [display_id]
    cg.CGDisplayBounds.restype = Rect
    count = ctypes.c_uint32()
    if cg.CGGetActiveDisplayList(0, None, ctypes.byref(count)) or not count.value:
        raise RuntimeError("cannot enumerate active displays")
    displays = (display_id * count.value)()
    if cg.CGGetActiveDisplayList(count.value, displays, ctypes.byref(count)):
        raise RuntimeError("cannot read active displays")
    primary = cg.CGMainDisplayID()
    result = []
    for identifier in displays[:count.value]:
        bounds = cg.CGDisplayBounds(identifier)
        if bounds.size.width > 0 and bounds.size.height > 0:
            result.append(Display(identifier, bounds.origin.x, bounds.origin.y,
                                  bounds.size.width, bounds.size.height,
                                  identifier == primary))
    return result


def position(displays, selection):
    if selection == "auto":
        if len(displays) < 2:
            return None
        selection = "left"
    if selection not in ("left", "right", "primary"):
        raise ValueError("AMIGA_MONITOR must be left, right or primary")
    if not displays:
        raise RuntimeError("no active displays")
    # Horizontal desktop order; topmost, then primary wins a tie (stacked/mirrored).
    if selection == "primary":
        display = next((d for d in displays if d.primary), None)
        if display is None:
            raise RuntimeError("primary display is not active")
    else:
        display = min(displays, key=lambda d: (
            d.x if selection == "left" else -d.x, d.y, not d.primary, d.identifier))
    # CoreGraphics desktop bounds are logical points, as used by SDL on macOS.
    # Inset the top-left corner rather than depending on a project's window dimensions.
    return (round(display.x + min(40, display.width / 4)),
            round(display.y + min(40, display.height / 4)))


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: monitor.py auto|left|right|primary")
        coordinates = position(active_displays(), sys.argv[1])
        if coordinates is not None:
            print(*coordinates)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"AMIGA_MONITOR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
