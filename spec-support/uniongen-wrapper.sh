#!/bin/sh

dir=/tmp/egalito-uniongen
program=$1
shift

mkdir -p $dir
file=$dir/$(basename $program)

if [ -e "$file" ]; then
    $file $@
else
    /home/egalito/egalito-uniongen/app/etelf -u $program $file
    exit 1
fi
