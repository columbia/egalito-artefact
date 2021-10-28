Provides some examples of using the egalito shell. Specifically, invokes
etshell in (egalito/app) with commands provided in the file provided as input.

shell0.in is the default file. To run the commands in shell0.in, run
$ ./shell.pl

To run the commands in a different input file such as shell1.in, run
$ ./shell.pl shell1.in


shell0: shows basic usage and disassembly
shell1: shows AST nodes parsed by Egalito
shell2: normal ELF parse + recursively parsing all dependencies
shell3: shows function address reassignment (new executable layout)
shell4: runs a pass that adds nop after every instruction (slow)


Of course, you can also manually run the shell and type whatever you like.
$ ../../egalito-head/app/etshell
