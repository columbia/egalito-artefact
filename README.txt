This is the Egalito SSSS'21 Tutorial virtual machine version 1. The VM image is
hosted on AWS and has 4 cores, 16GB RAM (half of this should be sufficient
though).

Log in as user ubuntu (has sudo access).

The machine contains the following:
- [Optional] Instructions for building Egalito manually (README-manual.txt)
- Built Egalito source (egalito-head/)
- Main Egalito shadow stack exercise (egalito-shadow-stack-app/);
  includes separate copy of Egalito in egalito-shadow-stack-app/egalito
- Scripts for examining Egalito IR with etshell2 (chunkhierarchy)
- Scripts for running the Egalito shell etshell (shell)
- Scripts for running Egalito and DynamoRIO AFL fuzzing tools (afl-support)

See ~/README-{manual,chunkhierarchy,shell,afl}.txt for further instructions.

We recommend running experiments from within tmux because they can take a
while. The AFL experiment requires Github internet access.

Egalito's website is https://egalito.org/ and its source may be found at
https://github.com/columbia/egalito. Egalito is distributed under a GPL v3
license. This virtual machine was prepared by David Williams-King and Vidya
Rajagopalan, and all supporting scripts (which are not inside the egalito
directories) can be considered public domain.
