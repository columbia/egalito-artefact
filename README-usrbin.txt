test-a.sh
**********

Transform existing executables in /usr/bin with egalito. Test to make sure the
transformed programs work by running them with --help. By default, only looks
at /usr/bin/a*, but can be configured to run on any input directory.

Usage:

$ ./test-a.sh

Expected result: number of successful runs equal in each case.

==== Running original executables with --help                               
...
SUCCESSES : 19/25 (76.00%)
...
==== Running transformed executables with --help
...
SUCCESSES : 19/25 (76.00%)

The first number is how many successes we can expect (some binaries just don't
run properly with --help). The second number is how many successes observed
after Egalito transforms the executables. If the numbers match, Egalito is
transforming 100% correctly.

test-any.sh
************

Transforms the executable which is passed as argument using etelf app. Tests to make sure the transformed program work by running the original as well as the transformed program with --help. 

Usage: 

$ ./test-any.sh in-file

If both returns OK, then transformation is successful. If original returns OK, while transformed returns ERROR, the transformation is unsuccessful. If both programs return ERROR, then we don't know if transformation is successful nor not.
