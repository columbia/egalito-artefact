#!/bin/bash

if [ -z "$EGALITO_ROOT" ]; then
    EGALITO_ROOT=~/egalito-head
fi

outdir=/tmp/egalito-out
if [ -z "$1" ]; then
    echo "Usage: $0 out-dir file1 [file2...]"
    exit
else
    dir=$1
    shift
fi

files="$@"

rm -rf $outdir >/dev/null 2>&1
mkdir -p $outdir
echo "$dir -> $outdir"

for file in $files; do
    if [ -n "$(file -L $file | grep 'ELF 64-bit LSB shared object.*interpreter' | grep -Ev 'setuid|setgid')" ]; then
        echo "$file -> $outdir/.egalito/$file"
        echo mkdir -p $(dirname $outdir/$file)
        mkdir -p $(dirname $outdir/.egalito/$file)
        echo app/etelf $file $outdir/.egalito/$file
        $EGALITO_ROOT/app/etelf $file $outdir/.egalito/$file

        mkdir -p $(dirname $outdir/.orig/$file)
        echo cp $file $outdir/.orig/$file
        cp $file $outdir/.orig/$file
    fi
done
