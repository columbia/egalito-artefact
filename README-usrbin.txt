Transform existing executables in /usr/bin with egalito. Test to make sure the
transformed programs work by running them with --help. By default, only looks
at /usr/bin/a*, but can be configured to run on any input directory.

Usage:

$ ./test-a.sh

Expected result: number of successful runs equal in each case.

SUCCESSES : 19/25 (76.00%)
...
SUCCESSES : 19/25 (76.00%)

The first number is how many successes we can expect (some binaries just don't
run properly with --help). The second number is how many successes observed
after Egalito transforms the executables. If the numbers match, Egalito is
transforming 100% correctly.
