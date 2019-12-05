#!/bin/bash
#EGALITO_ROOT="/home/ethereal/egalito"

program=$1
exedir=$2
log=$exedir/egalito.log

echo -e "parse $program\njumptables\nfunctions3 module-(executable)" \
    | EGALITO_SYSROOT=$PWD/extract-dbg/ EGALITO_DEBUG=djumptable=10 $EGALITO_ROOT/app/etshell \
    > $log

grep '^0x' $log > $exedir/symbols
grep '^jump table' $log > $exedir/tables.egalito
