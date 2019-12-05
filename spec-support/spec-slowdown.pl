#!/usr/bin/perl

use warnings;
use strict;

sub parse_times($) {
    my $file = shift;
    my %time = ();
    while(my $line = <$file>) {
        if($line =~ /^ (Success|Error) (\d+.\w+) base \w+ ratio=\S+, runtime=([.0-9]+)$/) {
            if($1 eq 'Success') {
                $time{$2} = $3;
            }
            else {
                $time{$2} = -1;
            }
        }
    }
    return %time;
}

open(my $base, $ARGV[0]) or die;
my %basetime = parse_times($base);
close $base;

my %incumbenttime = ();

for(my $a = 1; $a < @ARGV; $a ++) {
    open(my $incumbent, $ARGV[$a]) or die;
    my %itime = parse_times($incumbent);
    close $incumbent;
    for my $i (keys %itime) {
        if(!exists $incumbenttime{$i} or $itime{$i} != -1) {
            $incumbenttime{$i} = $itime{$i};
        }
    }
}

my $total = 0;
my $count = 0;
my $product = 1;

for my $key (sort keys %basetime) {
    next unless defined $incumbenttime{$key};
    next if $key =~ 'specrand';

    if($incumbenttime{$key} >= 0) {
        my $slowdown = $incumbenttime{$key} / $basetime{$key};

        printf("%-20s %10.6f => %10.6f  %10.6f\n", $key,
            $basetime{$key}, $incumbenttime{$key},
            $slowdown);
        $total += $slowdown;
        $product *= $slowdown;
        $count ++;;
    }
    else {
        printf("%-20s %10.6f => %10s  %10s\n", $key,
            $basetime{$key}, '-', '-');
    }
}
if($count > 0) {
    printf("%-20s %10s    %10s  %10.6f\n",
        "arithmetic-mean", '', '', $total / $count);
    printf("%-20s %10s    %10s  %10.6f\n",
        "geometric-mean", '', '', $product ** (1.0 / $count));
}
