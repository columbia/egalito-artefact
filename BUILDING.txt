Egalito is already installed on the VM in ~/egalito-head. If you would like to
build it from scratch, first get your github SSH key onto the machine by either

- adding the key to your local ssh agent, then ssh in with -A
- or scp'ing the key into ~/.ssh/id_rsa*, then run eval `ssh-agent` & ssh-add

Next:

$ git clone git@github.com:columbia/egalito.git egalito-manual --recursive --branch master
$ cd egalito-manual
$ make -j 4  # if this fails, run it again (race condition)
$ cd app

You can also start from this point with "cd ~/egalito-head/app". To transform
a program manually in mirrorgen (1-1 ELF) mode:

$ ./etharden /bin/ls ls
Transforming file [/bin/ls]
Parsing ELF file...
Performing code generation into [ls]...
$ ./ls -l --color

Try -v to see lots of Egalito output. You can also try e.g.

$ ./etharden --retpolines /bin/ls ls
$ ./ls -l --color
$ ./etharden --cfi /bin/ls ls
$ ./ls -l --color
$ ./etharden -u /bin/ls ls
$ ./ls --color  # known uniongen bug with -l

There are other Egalito programs such as etshell, etshell2, and etprofile in
the app directory, feel free to try them out. Also, there are a set of tests
you can run here:

$ cd ~/egalito-manual/test/codegen
$ make

One way to tell if an executable has been transformed with Egalito is to check
the address of .text; it will always be 0x40000000 by default after
transformation.

$ readelf -S ./ls 2>/dev/null | grep '\.text'
  [21] .text             PROGBITS         0000000040000000  00014000

For more detailed tutorials and usage, please go to https://egalito.org .
