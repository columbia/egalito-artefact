#!/bin/bash

show_packages() {
    echo -n "$1:"
    for dir in build-* result-*; do
        if [ ! -e $dir/testlog ]; then continue; fi

        if [ -n "$(tail -n 1 $dir/testlog | grep $1)" ]; then
            echo -n " $(echo $dir | perl -pe 's/^(build|result)-//')"
        fi
    done
    echo
}

show_packages PASS
show_packages FAIL
show_packages SKIP

echo

echo -n "PASS "
ls build-*/testlog result-*/testlog 2>/dev/null | xargs tail -n 1 | grep -c PASS
echo -n "FAIL "
ls build-*/testlog result-*/testlog 2>/dev/null | xargs tail -n 1 | grep -c FAIL
echo -n "SKIP "
ls build-*/testlog result-*/testlog 2>/dev/null | xargs tail -n 1 | grep -c SKIP

