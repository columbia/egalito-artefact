#!/bin/bash

if [[ "$1" == "" ]]; then
    echo "Usage: $0 file.deb"
    echo "result will be put in gen/"
    exit 1
fi

if [[ $EGALITO_ROOT == "" ]]; then
    echo "EGALITO_ROOT must be set"
    exit 1
fi

TMPDIR=$(mktemp -d)

mkdir $TMPDIR/DEBIAN

dpkg -e $1 $TMPDIR/DEBIAN
dpkg -x $1 $TMPDIR

pushd $TMPDIR

for dir in bin sbin usr/bin usr/sbin; do
    if [[ ! -d $dir ]]; then
        continue
    fi

    echo "processing $dir:"
    for elf in $(ls $dir/* | file -f - | grep BuildID | awk -F: '{print $1}'); do
        echo "transforming $elf..."
        TEMPFILE=$(mktemp)
        mv $elf $TEMPFILE
        $EGALITO_ROOT/app/etelf -m $TEMPFILE $elf
        rm $TEMPFILE
    done
done

rm DEBIAN/md5sums
find -type f | sed 's/^\.\///' | grep -v '^DEBIAN' | xargs -n 100 md5sum > DEBIAN/md5sums

popd

mkdir -p orig
mv $1 orig/
dpkg -b $TMPDIR .

rm -rf $TMPDIR
