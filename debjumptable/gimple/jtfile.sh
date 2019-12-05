#!/bin/bash

#EGALITO_ROOT="/home/ethereal/egalito"

if [ -z "$3" ]; then
    echo "Usage: $0 foo foo.deb foo-build-tree/"
    exit 1
fi

pkg=$1
deb=$2
buildtree=$3

dpkg -x $deb install-root

splitdebug=1
if [ "$pkg" = "perl-base" ]; then
    exes=$buildtree/perl.debug
    splitdebug=0
else
    #exes=$(ls install-root/{usr/bin/*,bin/*,sbin/*} 2>/dev/null \
    #    | xargs file | grep -E 'ELF 64-bit LSB pie executable|ELF 64-bit LSB shared object' | sed 's/:.*//')
    exes=$(find install-root/ -type f 2>/dev/null \
        | xargs file | grep -E 'ELF 64-bit LSB pie executable|ELF 64-bit LSB shared object' | sed 's/:.*//')
fi

echo Executables: $exes

failure=0
execount=0
for exe in $exes; do
    exedir=exe/$execount-$(basename $exe)
    rm -rf $exedir
    mkdir -p $exedir
    ln -s ../../$exe $exedir/program

    if [ "$splitdebug" = "1" ]; then
        ls extract-dbg/usr/lib/debug/.build-id/$(readelf -Wa $exe \
            | grep "Build ID" | awk '{ print $3 }' | perl -pe 's|(..)|$1/|').debug | xargs readelf -Wa 2>/dev/null \
            | ../jtground.pl $buildtree > $exedir/tables.gimple
    else
        readelf -Wa $exe | ../jtground.pl $buildtree > $exedir/tables.gimple
    fi
    ../jtegalito.sh $exe $exedir
    ../jumptable-diff-option.pl $exedir/symbols $exedir/tables.gimple $exedir/tables.egalito | tee $exedir/tables.diff
    if [[ "$?" != "0" ]]; then
        failure=1
    fi
    ((++execount))
done

exit $failure
