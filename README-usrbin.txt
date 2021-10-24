Transform existing executables in /usr/bin with egalito. Test to make sure the
transformed programs work by running them with --help. By default, only looks
at /usr/bin/a*, but can be configured to run on any input directory.

Usage:

$ ./test-a.sh

Expected result: number of successful runs equal in each case.

SUCCESSES : 19/25 (76.00%)
...
SUCCESSES : 19/25 (76.00%)

(In this case, Egalito is transforming 100% correctly. Some binaries just don't
run properly with --help, before or after transformation.)
