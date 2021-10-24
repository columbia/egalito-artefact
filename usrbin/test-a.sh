export EGALITO_ROOT=~/egalito-head/
export DATA=/tmp/test1
export OUT=/tmp/egalito-out

# Choose the executables to test
mkdir -p $DATA
cp /usr/bin/a* $DATA

# For each file in /tmp/test1, if it is a pie executable, transform it with Egalito.
./usrbin.sh $DATA $OUT

# Egalito-transformed and original executables
ls $OUT/$DATA $OUT/.orig/$DATA

# Check to make sure the files have been transformed with Egalito
./is-transformed.sh $OUT/DATA/* $OUT/.orig/$DATA/*

# Try running the executables with --help to check for successful transforms
./runhelp.pl $OUT/$DATA/*
./runhelp.pl $OUT/.orig/$DATA/*

# Expected result: number of successful runs equal in each case.
# $ ./runhelp.pl $OUT/$DATA/*
# ...
# SUCCESSES : 18/22 (81.82%)
# $ ./runhelp.pl $OUT/.orig/$DATA/*
# ...
# SUCCESSES : 18/22 (81.82%)

