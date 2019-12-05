#!/usr/bin/env python3

import sys
import os

if len(sys.argv) != 2:
    print("Usage: " + sys.argv[0] + " <changes file>")
    sys.exit(1)

lines = open(sys.argv[1]).readlines()
os.system("mv " + sys.argv[1] + " " + sys.argv[1] + ".old")
output = open(sys.argv[1], "w")

mode = "copy"
cmd = ""
for line in lines:
    if line.startswith("Checksums-") or line.startswith("Files:"):
        mode = "checksum"
        if line.startswith("Files:"):
            cmd = "md5sum"
        elif line.startswith("Checksums-Sha1"):
            cmd = "sha1sum"
        elif line.startswith("Checksums-Sha256"):
            cmd = "sha256sum"
        output.write(line)
        continue
    if mode == "copy":
        output.write(line)
        if line.startswith("Checksums-") or line.startswith("Files:"):
            mode = "checksum"
            if line.startswith("Files:"):
                cmd = "md5sum"
            elif line.startswith("Checksums-Sha1"):
                cmd = "sha1sum"
            elif line.startswith("Checksums-Sha256"):
                cmd = "sha256sum"
            continue
    if mode == "checksum":
        lsplit = line.split()
        filename = lsplit[-1]
        os.system(cmd + " " + filename + " > /tmp/update")
        digest = (open("/tmp/update", "r").readlines()[0]).split()[0]
        
        output.write(" " + digest + " " + str(os.path.getsize(filename)) + " ")
        output.write(" ".join(lsplit[2:]))
        output.write("\n")
