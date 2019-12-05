#!/bin/bash

mkdir build-$1 || exit 1

pushd build-$1
apt-get source $1
DIRNAME=$(find . -maxdepth 1 -type d | grep -v '^\.$')

echo "=== Running build"
../autopkgtest-4.4/runner/autopkgtest $DIRNAME -- schroot pkgtest > buildlog 2>&1
RETVAL=$?

echo "=== Build return value: $RETVAL"
tail -n 10 build-$1/buildlog
echo "=== end build log"

for f in *.deb; do
    echo "=== Rewriting all executables in package $f"
    ../rewrite.sh $f 2>&1 | tee transformlog
done
../update-changes.py *.changes

echo "=== Running tests"
../autopkgtest-4.4/runner/autopkgtest $DIRNAME *.changes -- schroot pkgtest > testlog 2>&1
RETVAL=$?

popd

echo "=== Test return value: $RETVAL"
tail -n 10 build-$1/testlog
echo "=== end test log"
