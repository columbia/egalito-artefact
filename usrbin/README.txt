These scripts transform existing executables on the system (e.g. from
/usr/bin), to ensure no-op transformation works correctly.


test1.sh
************

Transforms the executable which is passed as argument using etelf app. Tests to
make sure the transformed program work by running the original as well as the
transformed program with --help. 

Usage: 

$ ./test1.sh in-file

If both returns OK, then transformation is successful. If original returns OK,
while transformed returns ERROR, the transformation is unsuccessful. If both
programs return ERROR, then we don't know if transformation is successful nor
not.


test.sh
**********

Transforms multiple existing executables (e.g. from /usr/bin) with egalito. The
input and output binaries are tested with --help to see if each version
produces a zero exit code.

Usage example:

$ ./test.sh /usr/bin/a*

Expected result: number of successful runs equal in each case.

==== Running original executables with --help                               
...
SUCCESSES : 19/22 (86.36%)
...
==== Running transformed executables with --help
...
SUCCESSES : 19/22 (86.36%)

The first number is how many successes we can expect (some binaries just don't
run properly with --help). The second number is how many successes observed
after Egalito transforms the executables. If the numbers match, Egalito is
transforming 100% correctly.
