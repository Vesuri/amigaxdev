"""Validate independently delimited native service counters, without call trees."""
import collections
import re


def validate(headers, exits, text_range):
    def require(ok, reason):
        if not ok:raise ValueError('NATIVE SCOPE / '+reason)
    require(headers,'EMPTY CAPTURE')
    totals=collections.defaultdict(lambda:dict.fromkeys(('units','calls','returns','irq','foreign','partial'),0))
    carry={};irq_carry=None;interrupts=0
    try:
        for index,h in enumerate(headers):
            require(h['native_scope_version']==1 and h['native_scope_faults']==0,'VERSION OR FAULT')
            require(tuple(h['native_scope_exit_'+str(i)] for i in range(3))==tuple(exits),'FROZEN RETURN BOUNDARIES')
            require((h['native_scope_text_low'],h['native_scope_text_high'])==tuple(text_range),'FROZEN TEXT RANGE')
            before,after=h['native_scope_irq_before'],h['native_scope_irq_after']
            entered,exited=h['native_scope_irq_entered'],h['native_scope_irq_exited']
            require(all(isinstance(v,int) and v>=0 for v in (before,after,entered,exited,h['native_scope_unscoped'])),'NEGATIVE COUNTER')
            require(before+entered==after+exited,'INTERRUPT PAIRING')
            if irq_carry is not None:require(before==irq_carry,'INTERRUPT CONTINUITY')
            irq_carry=after;interrupts+=entered
            ids={int(m[1],16) for key in h if (m:=re.fullmatch(r'native_([0-9a-f]{3})_(units|calls|returns|irq|before|after|foreign)',key))}
            require(set(carry)<=ids,'LOST CARRY')
            accounted=h['native_scope_unscoped'];next_carry={}
            for trap in ids:
                r={k:h[f'native_{trap:03x}_{k}'] for k in ('units','calls','returns','irq','before','after','foreign')}
                require(all(isinstance(v,int) and v>=0 for v in r.values()),'NEGATIVE COUNTER')
                require(r['foreign']<=r['units'],'FOREIGN ACCOUNTING')
                require(r['before']+r['calls']==r['returns']+r['after'],'SERVICE PAIRING')
                if index:require(r['before']==carry.get(trap,0),'SERVICE CONTINUITY')
                accounted+=r['units']+r['irq']
                if r['after']:next_carry[trap]=r['after']
                total=totals[trap]
                for key in ('units','calls','returns','irq','foreign'):total[key]+=r[key]
                total['partial']+=r['before']+r['after']
            carry=next_carry
            require(accounted==h['units']-h['tail'],'INSTRUCTION ACCOUNTING')
    except KeyError as error:
        raise ValueError('NATIVE SCOPE / MISSING COUNTER '+str(error)) from error
    return dict(totals),dict(interrupts=interrupts,irq_before=headers[0]['native_scope_irq_before'],irq_after=irq_carry)


def linea_entries(header, pcs, nodes):
    """Validate CPU Line-A entry charges, separately from native handler PCs."""
    def require(ok, reason):
        if not ok:raise ValueError('LINE-A ENTRY / '+reason)
    require(header.get('executed_pc_frozen')==1 and header.get('linea_entry_version')==1,'INSTRUMENT IDENTITY')
    ids={int(m[1],16) for key in header if (m:=re.fullmatch(r'linea_([0-9a-f]{8})_(units|calls)',key))}
    result={};calls=0
    for pc in ids:
        units=header.get(f'linea_{pc:08x}_units');count=header.get(f'linea_{pc:08x}_calls')
        require(isinstance(units,int) and units>=0 and isinstance(count,int) and count>0,'MISSING OR INVALID COUNTER')
        require(pc in pcs and pcs[pc][:2]==(units,count),'FLAT INSTRUCTION ACCOUNTING')
        result[pc]=units;calls+=count
    require(calls==sum(row[4] for row in nodes.values() if row[2]==10),'EXCEPTION CALL COUNT')
    return result
