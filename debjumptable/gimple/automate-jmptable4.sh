#!/bin/bash

TMPFILE=$(mktemp)

function fail() {
    echo "Failure: $1"
    rm $TMPFILE
    exit 1
}

if [[ $1 == "" ]]; then
    fail "Usage: $0 package-name"
fi

BUILDLOG=$PWD/build-$1.log

if [[ $EGALITO_ROOT == "" ]]; then
    fail "Path to egalito not specified in \$EGALITO_ROOT."
fi

mkdir build-$1 2>/dev/null
if [[ $? = "0" ]]; then
    yes | sudo apt-get build-dep $1

    pushd build-$1 >/dev/null

    apt-get source $1 || fail "couldn't get source tree!"
    ln -s *-*/ tree

    DIRNAME=$(find -maxdepth 1 -type d | grep -v '^.$')

    log_path=build-logs
    mkdir $log_path
    pushd $DIRNAME
    rm ~/gimple-rescue/*
    PATH=~/intercept-bin:$PATH DEB_BUILD_OPTIONS="nocheck notest" DEB_CFLAGS_APPEND=-fdump-rtl-dfinish \
        dpkg-buildpackage -B --no-sign \
        || fail "couldn't build package!"
    mv ~/gimple-rescue .
    ../../trim-md5.pl ./gimple-rescue
    popd # $DIRNAME, package directory
else
    echo "using existing build tree for $1"
    pushd build-$1 >/dev/null
fi


if [[ ! -e extract-dbg ]]; then
    mkdir extract-dbg

    for f in $(ls *-dbgsym*.deb *-dbg_*.deb 2>/dev/null); do dpkg -x $f extract-dbg; done
fi

if [[ ! -e exe ]]; then
    ../jtfile.sh $1 $1_*.deb tree/
    good=$?
else
    good=0
    for diff in $(ls exe/*/tables.diff); do
        if [[ -s "$diff" ]]; then
            good=1
        fi
    done
fi

if [[ $good != "0" ]]; then
    echo "MISMATCH in jumptable detection"
else
    echo "jumptable diff seems OK"
fi
