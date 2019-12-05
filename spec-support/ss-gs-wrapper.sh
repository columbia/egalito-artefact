#!/bin/sh

dir=/tmp/egalito-ss-gs
program=$1
shift

mkdir -p $dir
file=$dir/$(basename $program)

if [ -e "$file" ]; then
    $file $@
else
    #echo "parse2 $program\npromotejumps\ncollapseplt\nendbradd\nendbrenforce\ngenerate-static $file" | /home/grahamp/egalito/app/build_x86_64/etshell
    #echo "parse2 $program\nendbradd\nendbrenforce\npromotejumps\ncollapseplt\ngenerate-static $file" | /home/dwk/project/egalito/egalito-spec3/app/build_x86_64/etshell
    #/home/dwk/project/egalito/egalito-spec4/app/build_x86_64/etcet -g $program $file
    ln -sf /home/egalito/egalito-uniongen/app/libcet.so
    /home/egalito/egalito-uniongen/app/etharden -u --cet-gs $program $file
    exit 1
fi
