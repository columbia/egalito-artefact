Welcome to the Egalito SSSS'21 Tutorial virtual machine (version 2). 

The machine contains the following:
- egalito-head/: Pre-built Egalito source
- scripts/: Exercises and demos, each with their own README.txt
- egalito-shadow-stack-app/: Advanced exercise: build an Egalito shadow stack

Egalito has already been built from source on this VM, in ~/egalito-head. The
advanced exercise contains another copy of Egalito built with extra flags.

Exercises:

1. Try running the usrbin demo to transform existing system executables with
   Egalito.

    cd ~/scripts/1-usrbin
    cat README.txt
    ./test1.sh /bin/ls
    ./test.sh /usr/bin/a*
    ./harden.sh /usr/bin/a*

2. Examine the Chunk hierarchy with etshell2.

    cd ~/scripts/2-chunk-hierarchy
    cat README.txt
    ./shell2.pl shell.in

3. Try using the Egalito shell (etshell) to examine the information and data
   structures that Egalito parses from ELF files.

    cd ~/scripts/3-shell
    cat README.txt
    ./shell.pl shell0.in
    ./shell.pl shell1.in
    # ...

4. Test Egalito vs DynamoRIO binary fuzzing. (drAFL has already been built and
   the target program already transformed with Egalito.)

    cd ~/scripts/4-afl/drAFL
    cat ../README.txt
    ./test-readelf.sh drafl 10
    ./test-readelf.sh egalito 10
    ./parselog.pl 

5. If you would like a challenge, try our advanced exercise to build a shadow
   stack implementation with Egalito. C++ skills required. Or skip to the
   solution to just see results.

    cd ~/egalito-shadow-stack-app
    cat README.txt
    cd test && ./test1.sh && cd -
    cat test/README.txt
    # Hack on code. Or:
    git checkout solution
    make
    cd test && ./test1.sh && cd -

Happy hacking!


Egalito's website is https://egalito.org/ and its source may be found at
https://github.com/columbia/egalito. Egalito is distributed under a GPL v3
license. This virtual machine was prepared by David Williams-King and Vidya
Rajagopalan, and all supporting scripts (which are not inside the egalito
directories) can be considered public domain.

If you are setting up this VM yourself: our VM has 4 cores, 16GB RAM (for
minimum requirements: 2 cores, 4GB RAM will be slower but sufficient). Log in
as user ubuntu (has sudo access).
