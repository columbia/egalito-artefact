We wrote an Egalito tool that transforms a binary to be compatible with the AFL
fuzzer. The tool is app/etcoverage in egalito-head. We compare it against
drAFL, a DynamoRIO-based binary fuzzing interface for AFL.

Everything has been pre-built; setup.sh generates drAFL directory.

To actually try running the two AFL tools, use test-readelf.sh which fuzzes
/usr/bin/readelf with /bin/cat as an initial input:
$ cd ~/scripts/4-afl/drAFL
$ ./test-readelf.sh drafl
$ ./test-readelf.sh egalito

NOTE: the test-readelf.sh script only runs from drAFL/ !

The script takes an optional second argument indicating the number of seconds
to run for (default: 10). AFL will automatically be killed after this period
of time (it is normal to see error messages at this point). The results are
appended to a file called log:

$ cat log
Tue Dec  3 22:53:46 EST 2019 drafl time=10 61
Tue Dec  3 22:54:47 EST 2019 egalito time=10 1661
$ ./parselog.pl
drafl   6.1 exec/s
egalito 166.1 exec/s

speedup: 27.2295081967213x
$

We provide parselog.pl to automatically compute the number of executions per
second and the overall speedup rate (here Egalito is 27x faster).
