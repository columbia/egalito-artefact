#!/usr/bin/env python3

import sys

if len(sys.argv) != 2:
    print("usage: " + sys.argv[0] + " <collation-file>")

def process_for_file(fname, lines):
    if len(lines) == 0:
        print(fname + " all good")
    else:
        lt = 0
        gt = 0
        lsizes = {}
        rsizes = {}
        for line in lines:
            name = line.split('[')[1].split(']')[0]
            size = int(line.split(']')[1].split()[1])
            if line[0] == '<':
                lt += 1
                lsizes[name] = size
            elif line[0] == '>':
                gt += 1
                rsizes[name] = size

        if lt == 0:
            print(fname + " extra egalito")
        elif gt == 0:
            print(fname + " extra gimple")
        else:
            # looking for true negatives (rsize/lsize differ)
            keys = set(lsizes.keys()).intersection(set(rsizes.keys()))
            sizediffer = 0
            sizedifferlist = []
            for key in keys:
                if lsizes[key] != rsizes[key]:
                    sizediffer += 1
                    sizedifferlist.append(key)
            if sizediffer == 0:
                print(fname + " extra both")
            else:
                print(fname + " " + str(sizediffer) + " true negatives, extra both")
                for l in sizedifferlist:
                    print("        symbol " + l + " differs: gimple says " + str(lsizes[l]) + " and egalito says " + str(rsizes[l]))

lines = open(sys.argv[1]).readlines()

for_fname = ""
for_file = []
for line in lines:
    line = line.strip()
    if line[-1] == ':':
        if for_fname != "":
            process_for_file(for_fname, for_file)
        for_fname = line[0:-1]
        for_file = []
    else:
        for_file.append(line)

if len(for_file) > 0:
    process_for_file(for_fname, for_file)
