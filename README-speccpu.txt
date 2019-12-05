Many of Egalito's evaluations are performed on SPEC CPU 2006 (v1.1).
Unfortunately, due to licensing concerns, we could not include this benchmark
within our virtual machine. In order to replicate these experiments, you will
need to copy the SPEC image onto this machine yourself with e.g. scp. Then
run the following:

$ sudo mount SPECcpu2006-1.1.iso /mnt/iso -o loop,ro
$ /mnt/iso/install.sh -d /home/egalito/speccpu/ -f
$ ~/spec-support/setup.sh

The setup script applies a small patch for SPEC to remove C++ exceptions and
fix compile errors on GCC 6. It also copies in several scripts and config
files. The config files have hard-coded references to /home/egalito/speccpu,
please update them if you wish to install elsewhere. Config files refer to
helper scripts in ~/spec-support/*-wrapper.sh. Config files use -j 4 to take
advantage of the VM's 4 cores.

We add egalito into SPEC CPU runs as follows. Each invocation of a target
program actually invokes a wrapper script e.g. mirrorgen-wrapper.sh (for
egalito-mirrorgen.cfg). The first time the wrapper is called, it will
transform the target program with egalito and produce a generated executable in
/tmp/egalito-mirrorgen. Subsequent invocations of the wrapper simply exec the
transformed program. Thus, you need to call runspec twice: the first time you
will see exit code 1 occur many times, which means the wrapper invoked egalito;
the second time will be the actual timed invocation. Also, you may want to
delete /tmp/egalito-mirrorgen/* in between runs. Each config file uses
independent wrapper scripts and temp directories.

To make this easier, we provide a run2.sh script which automatically runs
SPEC CPU twice, and cleans up temporary files. Invoke it with similar arguments
to runspec:

$ cd ~/speccpu
$ . shrc
$ ./run2.sh -c egalito-mirrorgen --size test -a run bzip2

REMEMBER: exit code 1 just means egalito transformed the binary!

You can use size test for short runs and size ref for long runs. Aside from
listing individual benchmark programs, you can also use all_c and all_cpp.
We have config files for mirrorgen, uniongen, retpolines, endbr, ss-const, and
DEP. For example, to run many different experiments at scale, try:

$ . shrc
$ for exp in mirrorgen uniongen retpolines; do \
    ./run2.sh -c egalito-$exp --size ref -a run all_c all_cpp; \
  done

Each ref all_c all_cpp will take at least an hour and about 1GB of disk.
Also, you can measure a baseline with

$ ./run-baseline.sh -c baseline --size ref -a run all_c all_cpp

While we provide an ss-gs config file, it currently only works on binaries
compiled with GCC 7 (the VM has GCC 6). All uniongen modes use
~/egalito-uniongen which has a few patches not yet merged into mainline
Egalito. We provide a baseline config script (though performance in a virtual
machine may vary). To compare runs, use our spec-slowdown.pl script:

$ ./spec-slowdown.pl \
    result/baseline/result/CPU2006.001.log \
    result/egalito-retpolines/result/CPU2006.002.log 
400.perlbench        246.371646 => 279.544824    1.134647
401.bzip2            363.454961 => 359.034684    0.987838
403.gcc              240.298319 => 239.001359    0.994603
429.mcf              310.027626 => 276.543684    0.891997
433.milc             418.750912 => 415.134262    0.991363
444.namd             291.395960 => 285.234090    0.978854
445.gobmk            380.184697 => 371.571256    0.977344
447.dealII           249.768327 => 238.631418    0.955411
450.soplex           226.073974 => 218.129235    0.964858
453.povray           109.274892 => 173.863056    1.591061
456.hmmer            340.659477 => 332.732905    0.976732
458.sjeng            417.065764 => 460.878838    1.105051
462.libquantum       351.935347 => 355.226225    1.009351
464.h264ref          415.009163 => 491.068278    1.183271
470.lbm              246.944494 => 236.022914    0.955773
471.omnetpp          338.200350 => 387.683808    1.146314
473.astar            341.755838 => 336.476029    0.984551
482.sphinx3          456.396631 => 437.790229    0.959232
483.xalancbmk        209.185797 => 257.830677    1.232544
arithmetic-mean                                  1.053726
geometric-mean                                   1.044189

$ ./spec-slowdown.pl \
    result/baseline/result/cat.log \
    result/egalito-uniongen/result/CPU2006.002.log
400.perlbench        246.371646 => 231.246995    0.938610
401.bzip2            363.454961 => 350.644004    0.964752
403.gcc              240.298319 => 229.964238    0.956995
429.mcf              310.027626 => 268.102932    0.864771
433.milc             418.750912 => 409.251788    0.977316
444.namd             291.395960 => 282.736945    0.970284
445.gobmk            380.184697 => 366.200160    0.963216
447.dealII           249.768327 => 249.450693    0.998728
450.soplex           226.073974 => 220.438549    0.975073
453.povray           109.274892 => 105.895013    0.969070
456.hmmer            340.659477 => 328.216610    0.963474
458.sjeng            417.065764 => 415.083506    0.995247
462.libquantum       351.935347 => 343.516589    0.976079
464.h264ref          415.009163 => 431.362487    1.039405
470.lbm              246.944494 => 238.615496    0.966272
471.omnetpp          338.200350 => 328.260791    0.970610
473.astar            341.755838 => 351.721740    1.029161
482.sphinx3          456.396631 => 426.551798    0.934608
483.xalancbmk        209.185797 => 193.399366    0.924534
arithmetic-mean                                  0.967274
geometric-mean                                   0.966570

Hence, in the virtual environment, we see retpolines having a 4.4% slowdown
(geo mean) and uniongen having a 3.3% performance speedup.

The names of log files will be printed by runspec (or run2.sh). Each config
file places its logs in different directories for simplicity. Note that the
spec-slowdown.pl script must take one baseline (you can cat together multiple
logs if needed) but can take multiple additional logs, using the most recent
runtime for each case. This is useful for combining results from multiple
partial runs.
