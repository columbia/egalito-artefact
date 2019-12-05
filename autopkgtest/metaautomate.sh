#!/bin/bash
DELETE_BUILD_DIRS=1
mkdir -p automate-logs/
echo "running experiments"
echo "logs will be in automate-logs/"
if [[ $DELETE_BUILD_DIRS = 1 ]]; then
    echo "build-* automatically deleted to save disk, summarized in result-*"
fi
echo "==="
for package in $@; do
    echo -n "$package..."
    time ( ./autotest.sh $package > automate-logs/$package.log 2>&1 )
    tail -n 1 automate-logs/$package.log

    if [[ $DELETE_BUILD_DIRS = 1 ]]; then
        rm -rf result-$package
        mkdir result-$package
        cp -a build-$package/testlog result-$package
        rm -rf build-$package
    fi

	echo
done
