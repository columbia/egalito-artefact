We wrote an Egalito tool that transforms a binary to be compatible with the AFL
fuzzer. The tool is app/etcoverage in egalito-head. We compare it against
drAFL, a DynamoRIO-based binary fuzzing interface for AFL.

Since drAFL depends on DynamoRIO and other large dependencies, we did not
install it on this virtual machine by default. However, we provide an
easy-to-use setup script that downloads the code from github. Run it like this:

$ cd ~/
$ ./afl-support/setup.sh

This clones and installs drAFL, dynamorio, and makes a patched copy
of afl-fuzz to support non-dynamorio executions.

To actually try running the two AFL tools, use test-readelf.sh which fuzzes
/usr/bin/readelf with /bin/cat as an initial input:
$ cd ~/drAFL
$ export EGALITO_ROOT=~/egalito-head/
$ ./test-readelf.sh drafl
$ ./test-readelf.sh egalito

The script takes an optional second argument indicating the number of seconds
to run for (default: 10). AFL will automatically be killed after this period
of time (it is normal to see error messages at this point). The results are
appended to a file called log:

$ cat log
Tue Dec  3 22:53:46 EST 2019 drafl time=10 61
Tue Dec  3 22:54:47 EST 2019 egalito time=10 1661
$ ./parselog.sh
drafl time=10 rate was 6.1
egalito time=10 rate was 166.1
$ perl -e 'print 166.1/6.1,"\n"'
27.2295081967213
$

We provide parselog.sh to automatically compute the number of executions per
second. The overall speedup rate (here Egalito is 27x faster) can then be
easily computed.
