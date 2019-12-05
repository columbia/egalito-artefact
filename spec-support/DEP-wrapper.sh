#!/bin/sh

dir=/tmp/egalito-DEP
program=$1
shift

mkdir -p $dir
file=$dir/$(basename $program)

if [ -e "$file" ]; then
    $file $@
else
    ln -s /home/egalito/egalito-uniongen/app/libsandbox.so
    /home/egalito/egalito-uniongen/app/etsandbox $program $file
    exit 1
fi
