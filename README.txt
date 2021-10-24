This is the Egalito SSSS'21 Tutorial virtual machine version 1. The VM image is
hosted on AWS and has 4 cores, 16GB RAM (for minimum requirements: 2 cores, 4GB
RAM will be slow but sufficient).

Log in as user ubuntu (has sudo access).

The machine contains the following:
- egalito-head/: Pre-built Egalito source
- scripts/
  - Demo scripts for testing Egalito on programs in /usr/bin (usrbin)
  - Demo scripts for examining Egalito IR with etshell2 (chunkhierarchy)
  - Demo scripts for running the Egalito shell etshell (shell)
  - Demo scripts for running Egalito and DynamoRIO AFL fuzzing (afl-support)
    [note: requires Github internet access]
  - [Optional] Instructions for building Egalito manually (README-manual.txt)
- egalito-shadow-stack-app/
  - Main Egalito shadow stack exercise
  - (includes separate copy of Egalito in egalito-shadow-stack-app/egalito)

We suggest running the usrbin demo (try test-a.sh), then the shell demos
(chunkhierarchy and shell). Then, proceed to ~/egalito-shadow-stack-app (see
its README.txt) when you are ready to start the exercise.

Egalito's website is https://egalito.org/ and its source may be found at
https://github.com/columbia/egalito. Egalito is distributed under a GPL v3
license. This virtual machine was prepared by David Williams-King and Vidya
Rajagopalan, and all supporting scripts (which are not inside the egalito
directories) can be considered public domain.
