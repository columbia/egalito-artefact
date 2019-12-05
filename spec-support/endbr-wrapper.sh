#!/bin/sh

dir=/tmp/egalito-endbr
program=$1
shift

mkdir -p $dir
file=$dir/$(basename $program)

if [ -e "$file" ]; then
    $file $@
else
    #echo "parse2 $program\nendbradd\nendbrenforce\npromotejumps\ncollapseplt\ngenerate-static $file" | /home/egalito/egalito-head/app/etshell
    /home/egalito/egalito-uniongen/app/etharden -u --cfi $program $file
    exit 1
fi
