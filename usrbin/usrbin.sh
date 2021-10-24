#!/bin/bash

if [ -z "$EGALITO_ROOT" ]; then
    EGALITO_ROOT=~/egalito-head
fi

dir=/usr/bin
if [ -z "$1" ]; then
    echo "Usage: $0 in-dir [out-dir]"
    echo "Default out-dir is $outdir"
    exit
else
    dir=$1
fi

outdir=/tmp/egalito-out
if [ -n "$2" ]; then
    outdir=$2
fi

rm -rf $outdir >/dev/null 2>&1
mkdir -p $outdir
echo "$dir -> $outdir"

for file in $dir/*; do
    if [ -n "$(file $file | grep 'ELF 64-bit LSB shared object.*interpreter' | grep -Ev 'setuid|setgid')" ]; then
        echo "$file -> $outdir/$file"
        echo mkdir -p $(dirname $outdir/$file)
        mkdir -p $(dirname $outdir/$file)
        echo app/etelf $file $outdir/$file
        $EGALITO_ROOT/app/etelf $file $outdir/$file

        mkdir -p $(dirname $outdir/.orig/$file)
        echo cp $file $outdir/.orig/$file
        cp $file $outdir/.orig/$file
    fi
done
