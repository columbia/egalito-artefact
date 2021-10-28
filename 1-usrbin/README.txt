These scripts transform existing executables on the system (e.g. from
/usr/bin). test1.sh and test.sh perform a no-op transformation to see how well
Egalito can work. harden1.sh and harden.sh add control-flow integrity (CFI)
defense.

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


harden1.sh, harden.sh
***********************

The same as the above, but they run etharden --cfi. Notice that success rates
may be lower.

$ ./harden.sh /usr/bin/a*

Expected result: number of successful runs equal in each case.

==== Running original executables with --help                               
...
SUCCESSES : 19/22 (86.36%)

==== Running transformed executables with --help
...
SUCCESSES : 18/22 (81.82%)

Here aspell does not work correctly with --cfi, although it does work with just
etelf above. You can see the result of the transformation as follows:

$ objdump -d /tmp/egalito-out/.egalito/usr/bin/awk | grep endbr | head
0000000040000000 <egalito_endbr_violation>:
    40000002:   f3 0f 1e fa             endbr64 
    40000020:   0f 85 da ff ff ff       jne    40000000 <egalito_endbr_violation>
    40000b26:   0f 85 d4 f4 ff ff       jne    40000000 <egalito_endbr_violation>
    40000bbe:   f3 0f 1e fa             endbr64 
    400012d4:   0f 85 26 ed ff ff       jne    40000000 <egalito_endbr_violation>
    400019d3:   0f 85 27 e6 ff ff       jne    40000000 <egalito_endbr_violation>
    40001ad8:   0f 85 22 e5 ff ff       jne    40000000 <egalito_endbr_violation>
    40001c44:   0f 85 b6 e3 ff ff       jne    40000000 <egalito_endbr_violation>
    40002222:   0f 85 d8 dd ff ff       jne    40000000 <egalito_endbr_violation>

