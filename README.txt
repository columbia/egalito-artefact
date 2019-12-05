This is the Egalito Evaluation virtual machine. A copy of this README will be
provided both outside and inside the VM image. The VM image is in qemu qcow2
format, suitable for KVM or qemu. It uses 20GB disk, 4 cores, 8GB RAM.

Log in as user egalito, password UYVCANQS. egalito has sudo access.

The machine contains the following:
- Built Egalito source (main in egalito-head/, version with some uniongen
  commits in egalito-uniongen/)
- Scripts for running SPEC CPU 2006 experiments (spec-support/)
      NOTE: SPEC CPU itself is not included for licensing reasons;
      its ISO must be copied in separately. Details in README-speccpu.txt.
- Scripts for running Egalito and DynamoRIO AFL fuzzing tools (afl-support)
- Large-scale jump table analysis based on Debian packages (debjumptable/)
- Large-scale Debian package tests (autopkgtest/)

See ~/README-{speccpu,afl,largescale}.txt for further instructions.

We recommend running experiments from within tmux because they can take a
while. The AFL experiment requires Github internet access; the large-scale
experiments rely on internet access to a Debian mirror. Also, you may wish
to delete results from past experiments before running new ones to avoid
running out of disk space.

Egalito's website is https://egalito.org/ and its source may be found at
https://github.com/columbia/egalito. Egalito is distributed under a GPL v3
license. This virtual machine was prepared by David Williams-King, and all
supporting scripts (which are not inside the egalito directories) can be
considered public domain.
