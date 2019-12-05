#!/bin/bash
targets=$@
if [ -z "$targets" ]; then
    targets="all_c all_cpp"
fi

for i in execute; do
	echo === BEGIN STAGE $i
	runspec -c baseline --noreportable --iterations 1 --size ref -a run $targets
done
