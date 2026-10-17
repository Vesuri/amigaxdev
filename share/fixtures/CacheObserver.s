        include whdload.i
        section code,code
base:   SLAVE_HEADER
        dc.w 10,WHDLF_NoError|WHDLF_Req68020
        dc.l $80000,0
        dc.w start-base,0,0
        dc.b 0,$59
exp:    dc.l $10000
        dc.w name-base,name-base,name-base
name:   dc.b 'Authored debugger memory fixture',0
        even
; This standalone authored fixture never loads game data. SetCPU calls are setup
; only. No flush, policy change or OS call occurs between the observation points.
start:  move.l a0,a2
        moveq #0,d0
        move.l #WCPUF_All,d1
        jsr resload_SetCPU(a2)
        move.l exp(pc),a3
        lea $100(a3),a3
        move.l a3,a0
        moveq #$40,d0
        moveq #95,d1
.fill:  move.b d0,(a0)+
        addq.b #1,d0
        dbf d1,.fill
        move.l #$10203040,$400.w
        move.l #WCPUF_Base_NC|WCPUF_Exp_CB|WCPUF_Slave_CB|WCPUF_IC|WCPUF_DC,d0
        move.l #WCPUF_All,d1
        jsr resload_SetCPU(a2)
        ; WHDLoad NOMMU leaves caches off. This authored experiment explicitly
        ; chooses the matrix arm during setup, before any observed stores.
        movec cacr,d0
        move.l d0,a6
        IFD OBS_CACHE
        move.l #$80008000,d0
        ELSE
        moveq #0,d0
        ENDC
        movec d0,cacr
        lea completed(pc),a5
        move.l #$13579bdf,(a3)
        move.l #$2468ace0,4(a3)
        move.l (a3),d2
        move.l 4(a3),d3
        move.l #$11223344,15(a3)
        movec cacr,d4
        movec tc,d5
        move.l #$4f425331,d6
        lea second(pc),a4
        move.w #999,d7
        bsr delay
second:
        move.l #$89abcdef,(a3)
        move.l (a3),d2
        move.l #$4f425332,d6
        lea done(pc),a4
        move.w #49,d7
        bsr delay
done:   cmp.l #$89abcdef,(a3)
        bne.s failed
        cmp.l #$2468ace0,4(a3)
        bne.s failed
        cmp.l #$11223344,15(a3)
        bne.s failed
        cmp.l #$60616263,32(a3)
        bne.s failed
        move.l #$50415353,$404.w
completed:
        ; Teardown follows all observation and native continuation assertions.
        move.l a6,d0
        movec d0,cacr
        pea TDREASON_OK
        jmp resload_Abort(a2)

failed: illegal

delay:
.loop:  move.l $dff004,d0
        and.l #$1ff00,d0
        cmp.l #$10000,d0
        bne.s .loop
.leave: move.l $dff004,d0
        and.l #$1ff00,d0
        cmp.l #$10000,d0
        beq.s .leave
        dbf d7,.loop
        rts
