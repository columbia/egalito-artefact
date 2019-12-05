#!/bin/sh

dir=/tmp/egalito-retpolines
program=$1
shift

mkdir -p $dir
file=$dir/$(basename $program)

if [ -e "$file" ]; then
    $file $@
else
    #echo "parse2 $program\npromotejumps\ncollapseplt\ngenerate-static $file" | /home/dwk/project/egalito/egalito-spec2/app/build_x86_64/etshell
    /home/egalito/egalito-head/app/etharden --retpolines $program $file
    exit 1
fi
