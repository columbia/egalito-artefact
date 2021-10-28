export EGALITO_ROOT=~/egalito-head
export TMP_DIR=/tmp/egalito-out

mkdir -p $TMP_DIR/.in $TMP_DIR/.out

# Choose the executables to test
if [ -z "$1" ]; then
    echo "Usage: $0 in-file1 [in-file2 ...]"
    exit
fi

# For each file in /tmp/test1, if it is a pie executable, transform it with Egalito.
echo
echo ==== Transforming executables with Egalito
./usrbin.sh $TMP_DIR $@

# Egalito-transformed and original executables
echo
echo ==== Showing input and output executables
ORIG_FILES=$(find $TMP_DIR/.orig -type f | sort)
EGALITO_FILES=$(find $TMP_DIR/.egalito -type f | sort)

# Check to make sure the files have been transformed with Egalito
echo
echo ==== Checking to make sure executables are transformed
./is-transformed.sh $ORIG_FILES $EGALITO_FILES | column -t

# Try running the executables with --help to check for successful transforms
echo
echo ==== Running original executables with --help
./runhelp.pl $ORIG_FILES
echo
echo ==== Running transformed executables with --help
./runhelp.pl $EGALITO_FILES

# Expected result: number of successful runs equal in each case.
# $ ./runhelp.pl $TMP_DIR/.orig/$DATA/*
# ...
# SUCCESSES : 18/22 (81.82%)
# $ ./runhelp.pl $TMP_DIR/$DATA/*
# ...
# SUCCESSES : 18/22 (81.82%)

