#!/usr/bin/perl
open(LOG, "log") or die;
while(<LOG>) {
    if(/(\w+) time=(\d+) (\d+)/g) {
        $c{$1} += int($3) * 1.0 / int($2);
    }
}
close LOG;
for my $k (sort keys %c) {
    print "$k\t$c{$k} exec/s\n";
}
print "\nspeedup: ", $c{'egalito'} * 1.0/$c{'drafl'}, "x\n"
