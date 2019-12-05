#!/bin/bash
if [ "$1" != "-c" ]; then
    echo "usage: $0 -c configfile ...other options..."
    exit 1
fi
config=$2
rm -rf /tmp/${config/.cfg/}
for i in transform execute; do
	echo === BEGIN STAGE $i
	runspec --noreportable --iterations 1 $@
done
