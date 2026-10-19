from pathlib import Path
import copy, importlib.util
spec=importlib.util.spec_from_file_location('scope',Path(__file__).resolve().parents[1]/'share/pylib/amigaxdev/native_service_scope.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
h=dict(native_scope_version=1,native_scope_faults=0,native_scope_unscoped=30,native_scope_irq_before=0,native_scope_irq_after=0,native_scope_irq_entered=1,native_scope_irq_exited=1,native_scope_text_low=100,native_scope_text_high=1000,units=104,tail=4)
h.update({f'native_scope_exit_{i}':v for i,v in enumerate((200,300,400))})
h.update({f'native_055_{k}':v for k,v in dict(units=60,calls=2,returns=2,irq=10,before=0,after=0,foreign=0).items()})
validate=lambda rows:module.validate(rows,(200,300,400),(100,1000))
totals,diag=validate([h,h]);assert totals[0x55]['calls']==4 and totals[0x55]['units']==120 and diag['interrupts']==2
controls=0
for key in h:
 bad=copy.deepcopy(h);del bad[key]
 try:validate([bad])
 except ValueError:controls+=1
 else:raise AssertionError('accepted missing '+key)
for key,value in [('native_scope_faults',1),('native_scope_version',2),('native_scope_exit_0',202),('native_scope_text_high',999),('native_scope_irq_exited',0),('native_scope_unscoped',31),('native_055_calls',3),('native_055_units',-1),('native_055_foreign',61)]:
 bad=copy.deepcopy(h);bad[key]=value
 try:validate([bad])
 except ValueError:controls+=1
 else:raise AssertionError('accepted '+key)
a,b=copy.deepcopy(h),copy.deepcopy(h)
a['native_055_returns']=1;a['native_055_after']=1
b['native_055_before']=1;b['native_055_returns']=3
assert validate([a,b])[0][0x55]['partial']==2
for rows in ([a,h],[h,b],[]):
 try:validate(rows)
 except ValueError:controls+=1
 else:raise AssertionError('accepted broken continuity')
print(f'NATIVE SERVICE SCOPE READER PASS: partition, repeated and crossing scopes; {controls} rejected alterations')
