#!/bin/bash
echo "=== setting up drAFL..."
git clone https://github.com/mxmssh/drAFL.git
cd drAFL

# next, follow instructions from drAFL README:
echo "=== setting up dynamorio..."
git clone https://github.com/DynamoRIO/dynamorio
mkdir build_dr
cd build_dr/
cmake ../dynamorio/
make -j 4
cd ..
echo "=== building dynamorio tool..."
mkdir build
cd build
cmake ../bin_cov/ -DDynamoRIO_DIR=../build_dr/cmake
make -j 4
cd ..
echo "=== building afl-fuzz harness..."
cd afl/
make
cd ..

# finally, patch afl to support non-dynamorio executions
cp -ar afl afl-patched
patch -p0 < ~/afl-support/afl.patch
echo "=== building patched afl-fuzz harness..."
cd afl-patched && make -j 4 && cd -

# copy in our support scripts
cp ~/afl-support/*.sh .

echo "=== done! please cd drAFL, run ./test-readelf.sh then ./parselog.sh"
