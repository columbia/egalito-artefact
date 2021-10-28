export EGALITO_ROOT=~/egalito-head
export TMP_DIR=/tmp/egalito-out

# Parsing the input and output files
if [ -z "$1" ]; then
    echo "Usage: $0 in-file"
    exit
else
    mkdir -p $TMP_DIR
    inpfile=$1
    outfile=$TMP_DIR/`basename $1`
fi

# Transform the input file with etelf app
echo
echo ==== Running etelf
echo $EGALITO_ROOT/app/etelf $inpfile $outfile
$EGALITO_ROOT/app/etelf $inpfile $outfile

# Check to make sure the output file have been transformed with Egalito
echo
echo ==== Checking to make sure output executable is transformed

echo -n "$outfile: "
if [ -n "$(readelf -Wl $outfile 2>/dev/null | grep 'LOAD.*0x0000000040000000')" ]; then
    echo "egalito-transformed"
else
    echo "normal"
fi


# Try running the executables with --help to check for successful transforms
echo
echo ==== Running original executable with --help
$inpfile --help >/dev/null 2>&1
exitcode1=$?
echo -n "$inpfile --help: "
if [ "$exitcode1" -eq 0 ]; then
    echo "OK";
else
    echo "ERROR";
fi

$outfile --help >/dev/null 2>&1
exitcode2=$?
echo
echo ==== Running transformed executable with --help

echo -n "$outfile --help: "
if [ "$exitcode2" -eq 0 ]; then
    echo "OK";
else
    echo "ERROR";
fi

# Print summary
echo
if [[ "$exitcode1" -eq 0 && "$exitcode2" -eq 0 ]] ; then
    echo "TRANSFORMATION SUCCESSFUL"
elif [[ "$exitcode1" -eq 0 && "$exitcode2" -ne 0 ]]; then
    echo "TRANSFORMATION UNSUCCESSFUL"
elif [ "$exitcode1" -ne 0 ]; then
    echo "COULDN'T VERIFY SUCCESS OF TRANSFORMATION"
fi
