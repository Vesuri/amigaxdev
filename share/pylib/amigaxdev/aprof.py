"""Shared APROF 1 parsing and structural call-tree accounting.

Port symbol names, buckets and workload denominators belong to consumers.
Unmatched return counters are retained: a structurally valid tree does not
establish that dynamic return pairing was correct.
"""
import collections
import math


def require(ok, why):
    if not ok:
        raise ValueError('APROF / ' + why)


def parse_profile(text):
    """(header, pcs, nodes): pcs[pc]=(units, executions, chip_units, chip_accesses),
    nodes[id]=(parent, target, kind, self_units, calls); kind 0 is JSR/BSR, otherwise
    the exception vector; Line-A targets are 0xA0000000 | trap word."""
    header, pcs, nodes = {}, {}, {}
    lines = text.splitlines()
    require(lines and lines[0] == 'APROF 1', 'not an APROF 1 profile')
    for line in lines[1:]:
        f = line.split()
        if not f:
            continue
        if f[0] == 'P':
            chip = (int(f[4]), int(f[5])) if len(f) > 5 else (0, 0)
            pcs[int(f[1], 16)] = (int(f[2]), int(f[3])) + chip
        elif f[0] == 'N':
            nodes[int(f[1])] = (int(f[2]), int(f[3], 16), int(f[4]), int(f[5]), int(f[6]))
        elif len(f) == 2:
            header[f[0]] = int(f[1], 16) if f[0] == 'cacr' else (int(f[1]) if f[1].lstrip('-').isdigit() else f[1])
    require(0 in nodes and 'units' in header, 'incomplete profile')
    require(header.get('overflow', 0) == 0, 'PROFILE OVERFLOW')
    accounted = sum(v[3] for v in nodes.values())
    require(sum(v[0] for v in pcs.values()) + header['gap'] + header.get('high', 0) == accounted, 'PC/TREE ACCOUNTING')
    # aprof_stop prints the current clock without flushing aprof_last. Keep
    # that final sub-clock remainder explicit, never charge it to a function.
    tail = header['units'] - accounted
    # CPU units need not divide the Chip clock (50 MHz uses 36 versus 512).
    # sync_cycles rounds to a Chip boundary, so differences are aligned to
    # their greatest common divisor, not necessarily to a whole CPU unit.
    require(header['cycleunit'] > 0 and header['CYCLE_UNIT'] > 0, 'INVALID CLOCK UNITS')
    quantum = math.gcd(header['cycleunit'], header['CYCLE_UNIT'])
    require(0 <= tail <= header['CYCLE_UNIT'] and tail % quantum == 0, 'UNBOUNDED PROFILE TAIL')
    header['tail'] = tail
    return header, pcs, nodes


def call_tree(nodes):
    require(0 in nodes, 'MISSING TREE ROOT')
    require(all(n == 0 or v[0] in nodes for n, v in nodes.items()), 'MISSING TREE PARENT')
    children = collections.defaultdict(list)
    for n, (parent, *_rest) in nodes.items():
        if n:
            children[parent].append(n)
    order, stack, seen = [], [0], set()
    while stack:
        n = stack.pop()
        require(n not in seen, 'CYCLIC CALL TREE')
        seen.add(n)
        order.append(n)
        stack.extend(children[n])
    require(len(seen) == len(nodes), 'DISCONNECTED CALL TREE')
    inclusive = {}
    for n in reversed(order):
        inclusive[n] = nodes[n][3] + sum(inclusive[c] for c in children[n])
    return children, order, inclusive


def require_return_pairing(header):
    """Reject inclusive/active attribution when dynamic returns are unpaired.

    Flat PC accounting remains independently available. Zero diagnostics are a
    necessary gate; the caller still owns workload-specific completion controls.
    """
    require(header.get('overflow') == 0, 'CALL TREE OVERFLOW')
    require(header.get('unmatched_rts') == 0 and header.get('unmatched_rte') == 0,
            'UNVERIFIED RETURN PAIRING; USE FLAT PC COSTS')
