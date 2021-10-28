#!/bin/bash

for file in "$@"; do
    echo -n "$file: "
    if [ -n "$(readelf -Wl $file 2>/dev/null | grep 'LOAD.*0x0000000040000000')" ]; then
        echo "egalito-transformed"
    else
        echo "normal"
    fi
done
