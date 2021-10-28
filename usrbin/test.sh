export EGALITO_ROOT=~/egalito-head
export TMP_DIR=/tmp/egalito-out

rm -rf $TMP_DIR >/dev/null 2>&1
mkdir -p $TMP_DIR

# Choose the executables to test
if [ -z "$1" ]; then
    echo "Usage: $0 in-file1 [in-file2 ...]"
    exit
fi

# For each file in /tmp/test1, if it is a pie executable, transform it with Egalito.
echo
echo ==== Transforming executables with Egalito
for file in $@; do
    if [ -n "$(file -L $file | grep 'ELF 64-bit LSB shared object.*interpreter' | grep -Ev 'setuid|setgid')" ]; then
        mkdir -p $(dirname $TMP_DIR/.orig/$file)
        echo cp $file $TMP_DIR/.orig/$file
        cp $file $TMP_DIR/.orig/$file

        mkdir -p $(dirname $TMP_DIR/.egalito/$file)
        echo app/etelf $file $TMP_DIR/.egalito/$file
        $EGALITO_ROOT/app/etelf $file $TMP_DIR/.egalito/$file
    fi
done

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
# $ ./runhelp.pl $ORIG_FILES
# ...
# SUCCESSES : 18/22 (81.82%)
# $ ./runhelp.pl $EGALITO_FILES
# ...
# SUCCESSES : 18/22 (81.82%)

