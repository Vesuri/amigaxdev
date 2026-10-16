"""Prove a stripped conversion changed only zero-filled padding beyond ELF sections."""
import struct,sys
from pathlib import Path

def check(elf, before, after):
    assert elf[:6]==b'\x7fELF\x01\x02'
    off=struct.unpack_from('>I',elf,32)[0]
    width,count=struct.unpack_from('>HH',elf,46)
    sections=[]
    for i in range(count):
        s=struct.unpack_from('>10I',elf,off+i*width)
        if s[2]&2 and s[5]:sections.append((s[1],s[5]))
    assert len(before)==len(after)
    pos=0
    def word():
        nonlocal pos
        v=struct.unpack_from('>I',after,pos)[0];pos+=4;return v
    assert word()==1011 and word()==0
    assert word()==len(sections) and word()==0 and word()==len(sections)-1
    for _ in sections:
        flags=word()>>30
        if flags==3:word()
    normalized=bytearray(before)
    for kind,size in sections:
        hunk=word()&0x3fffffff;n=word()*4
        assert n==(size//4+1)*4
        assert hunk==(1003 if kind==8 else hunk) and hunk in (1001,1002,1003)
        if hunk!=1003:
            assert after[pos+size:pos+n]==bytes(n-size)
            normalized[pos+size:pos+n]=bytes(n-size);pos+=n
        while True:
            record=word()
            if record==1010:break
            assert record==1004
            while True:
                num=word()
                if not num:break
                word()
                for _ in range(num):word()
    assert pos==len(after)
    assert bytes(normalized)==after,'Non-padding bytes changed'

if __name__=='__main__':
    check(*(Path(n).read_bytes() for n in sys.argv[1:]))
    print('HUNK PADDING PASS: identical section data, layout and relocations; zero-filled padding')
