; Minimal host-assembled WHDLoad test: no ROM, DOS, game or game data.  It saves "PASS" to
; smoke-passed and quits, which shows WHDLoad, the slave and the test harness work.
;
; The project supplies the slave's name in smoke_name.i on the include path, one line:
;         dc.b "Game slave smoke test",0
; and assembles this file, for example:
;   $(VASM) -m68000 -pic -x -devpac -Fhunkexe -nosym -I. -I"$(WHDLOAD)/Include" -I"$(NDK)" \
;           -o Smoke.slave $(AMIGA_SHARE)/whdload/SmokeSlave.s
; -DSMOKE_DATA_LAST=1 places the PASS bytes after the code (Pokeri's layout).
        INCLUDE whdload.i
        INCLUDE whdmacros.i
_base   SLAVE_HEADER
        dc.w 17,0
        dc.l $10000,0
        dc.w _start-_base,0,0
        dc.b 0,$59
        dc.l 0
        dc.w _name-_base,_copy-_base,_info-_base
        dc.w 0
        dc.l 0
        dc.w 0,0
_name
        INCLUDE smoke_name.i
_copy   dc.b "2026",0
_info   dc.b "No game code is loaded",0
_file   dc.b "smoke-passed",0
        IFND SMOKE_DATA_LAST
_data   dc.b "PASS"
        ENDC
        EVEN
_start  move.l a0,a2
        lea (_file,pc),a0
        lea (_data,pc),a1
        moveq #4,d0
        jsr (resload_SaveFile,a2)
        pea TDREASON_OK
        jmp (resload_Abort,a2)
        IFD SMOKE_DATA_LAST
_data   dc.b "PASS"
        ENDC
