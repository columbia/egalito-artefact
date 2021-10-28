#!/bin/bash
if [ -z "$1" ]; then
    echo "usage: $0 [egalito|drafl] [time-in-seconds]"
    exit
fi

input_binary=$(which readelf)

if [ "$1" = "egalito" ]; then
    name=egalito
    afl=./afl-patched/afl-fuzz
    if [ -z "$EGALITO_ROOT" ]; then
        EGALITO_ROOT=~/egalito-head
    fi
    binary=./$(basename $input_binary).egalito
    ln -sf $EGALITO_ROOT/app/libcoverage.so
    if [[ ! -a $binary ]]; then
        echo Generating $binary ...
        $EGALITO_ROOT/app/etcoverage $input_binary $binary
    fi
    export AFL_NO_FORKSRV=0
    export AFL_SKIP_BIN_CHECK=1
else
    name=drafl
    afl=./afl/afl-fuzz
    # there's a bug in drafl, can't pass a symlink
    binary=$(realpath $input_binary)
    export DRRUN_PATH=$(pwd)/build_dr/bin64/drrun
    export LIBCOV_PATH=$(pwd)/build/libbinafl.so
    export AFL_NO_FORKSRV=1
    export AFL_SKIP_BIN_CHECK=1
fi

in=in-$name
out=out-$name

mkdir -p env
rm -rf env/$in env/$out
mkdir env/$in env/$out
cp /bin/cat env/$in/seed

$afl -m none -i env/$in -o env/$out -- $binary -Wa @@ &

t=$2
if [ -z "$2" ]; then
    t=10
fi
sleep $t
kill %%
wait
echo "$(date)" $name time=$t $(grep 'execs_done' env/$out/fuzzer_stats \
    | awk '{ print $3 }') >> ./log
