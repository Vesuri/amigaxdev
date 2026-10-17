        include whdload.i
        section code,code
base:   SLAVE_HEADER
        dc.w 10,WHDLF_NoError|WHDLF_Req68020
        dc.l $80000,0
        dc.w start-base,0,0
        dc.b 0,$59
        dc.l 0
        dc.w name-base,name-base,name-base
name:   dc.b 'Authored debugger CCR fixture',0
        even
start:  move.l a0,a2
        lea table(pc),a3
        lea completed(pc),a5
        move.l #$43435231,d6
        move.w #999,d7
waitfield:
        move.l $dff004,d0
        and.l #$1ff00,d0
        cmp.l #$10000,d0
        bne.s waitfield
leavefield:
        move.l $dff004,d0
        and.l #$1ff00,d0
        cmp.l #$10000,d0
        beq.s leavefield
        dbf d7,waitfield
        move.w #15,ccr
        moveq #0,d1
capture0:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #4,d0
        bne failed
        move.w #15,ccr
        moveq #-1,d1
capture1:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #8,d0
        bne failed
        move.w #15,ccr
        moveq #1,d1
capture2:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #0,d0
        bne failed
        move.w #31,ccr
        moveq #0,d1
capture3:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #20,d0
        bne failed
        move.w #31,ccr
        moveq #-1,d1
capture4:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #24,d0
        bne failed
        move.w #31,ccr
        moveq #1,d1
capture5:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #16,d0
        bne failed
        moveq #0,d1
        subq.b #1,d1
capture6:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #25,d0
        bne failed
        moveq #127,d1
        addq.b #1,d1
capture7:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #10,d0
        bne failed
        moveq #-128,d1
        subq.b #1,d1
capture8:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #2,d0
        bne failed
        moveq #-1,d1
        addq.b #1,d1
capture9:
        move.w ccr,d0
        and.w #31,d0
        cmp.w #21,d0
        bne failed
        move.l #$50415353,$404.w
completed:
        pea TDREASON_OK
        jmp resload_Abort(a2)
failed: illegal
table:
        dc.w capture0-table
        dc.w capture1-table
        dc.w capture2-table
        dc.w capture3-table
        dc.w capture4-table
        dc.w capture5-table
        dc.w capture6-table
        dc.w capture7-table
        dc.w capture8-table
        dc.w capture9-table
