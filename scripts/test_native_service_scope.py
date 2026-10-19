"""Compile the exact host-only scope counter embedded in the emulator patch."""
import os
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
patch=(root/'patches/fsuae-native-service-scope.patch').read_text()
part=patch.split('diff --git a/src/include/NativeServiceScope.h b/src/include/NativeServiceScope.h\n',1)[1].split('\ndiff --git ',1)[0]
header='\n'.join(line[1:] for line in part.splitlines() if line.startswith('+') and not line.startswith('+++'))+'\n'
assert header.startswith('#pragma once\n')
(root/'tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='native-service-scope-',dir=root/'tmp') as directory:
 p=Path(directory);(p/'NativeServiceScope.h').write_text(header)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(p),str(root/'scripts/test_native_service_scope.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('NATIVE SERVICE SCOPE PASS: nested IRQ exclusion, native return boundaries, exact partition, partial scopes, foreign PCs, unpaired/overflow controls')
