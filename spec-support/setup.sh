#!/bin/bash

cd ~/speccpu
patch -p0 < ~/spec-support/spec-patch.diff
cp ~/spec-support/config/* config/
cp ~/spec-support/{run2.sh,run-baseline.sh,spec-slowdown.pl} .
