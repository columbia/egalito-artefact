#!/usr/bin/perl

die "Usage: $0 symbol-table ground-truth-options-list egalito-list\n" unless @ARGV == 3;
my $tablefile = $ARGV[0];
my $list1 = $ARGV[1];
my $list2 = $ARGV[2];
my $verbose = 0;

my %symbols = ();
my %addresses = ();
my %symbol_count = ();
open(ST, $tablefile) or die;
while(my $sym = <ST>) {
    $sym =~ /0x(\S+) 0x(\S+) (\S+)/;
    my $address = hex("0x$1");
    $symbols{$3} = $address;
    $symbol_count{$3} ++;
    push @{ $addresses{$address} }, $3;

    my $name = $3;
    if($name =~ s/\@GLIBC_2.*//) {
        $symbols{$name} = $address;
        push @{ $addresses{$address} }, $name;
    }

    $name = $3;
    if($name =~ s/constprop\.\d+/constprop/) {
        $symbols{$name} = $address;
        push @{ $addresses{$address} }, $name;
    }
    elsif($name =~ s/\.lto_priv\.\d+//) {
        $symbols{$name} = $address;
        push @{ $addresses{$address} }, $name;
    }
    elsif($name =~ s/\.cold\.\d+//) {
        $symbols{$name} = $address;
        push @{ $addresses{$address} }, $name;
    }
}
close ST;

# slurp jumptable data from files
open(LIST1, $list1) or die;  # options list
my %tables1 = ();
my $table_mode = '';
while(my $line = <LIST1>) {
    if($line =~ /^jump table in \[(.*)\]:/) {
        $table_mode = $1;
    }
    elsif($line =~ /^    (.*)/) {
        my $data = $1;
        my @t = ();
        for my $d (split m|\\n|, $data) {
            if($d =~ /^jump table in \[.*\] has (\d+) entries$/) {
                push @t, $1;
            }
            else {
                die "unknown option [$d] in [$data]\n"; 
            }
        }
        push @{ $tables1{$table_mode} }, [ @t ];
    }
    else {
        $table_mode = ''; 
    }
}
close LIST1;

open(LIST2, $list2) or die;  # egalito list
my %tables2 = ();
while(my $line = <LIST2>) {
    next unless $line =~ /\[(\S+)\] .* (\d+) entries$/;

    push @{ $tables2{$1} }, int $2;
}
close LIST2;

# consider options
my $all_ok = 1;
for my $func (sort keys %tables2) {
    my @options = ();
    my @egalito = ();
    my $match_option = 0;
    if($symbol_count{$func} <= 1) {
        my $address = defined $symbols{$func} ? $symbols{$func} : 0;
        for my $alias (@{ $addresses{$address} }) {
            if(defined $tables1{$alias}) {
                for my $t (@{ $tables1{$alias} }) {
                    push @options, [ @{ $t } ];
                }
            }
            for my $count (@{ $tables2{$alias} }) {
                push @egalito, $count;
            } 
        }

        for my $option (@options) {
            my @lhs = sort @egalito;
            my @rhs = sort @{ $option };
            my $match = 1;
            if($#lhs == $#rhs) {
                for my $x (0..$#lhs) {
                    $match = 0 if($lhs[$x] != $rhs[$x]);
                }
                if($match == 1) {
                    $match_option = 1;
                    last;
                }
            }
        }
    }
    else {
        my $address = defined $symbols{$func} ? $symbols{$func} : 0;
        my %present = ();
        my %baseline = ();
        my %egalito = ();
        for my $alias (@{ $addresses{$address} }) {
            if(defined $tables1{$alias}) {
                for my $t (@{ $tables1{$alias} }) {
                    for my $v (@{ $t }) {
                        $baseline{$v} = 1;
                    }
                }
            }
            for my $count (@{ $tables2{$alias} }) {
                $egalito{$count} = 1;
            } 
        }

        if(1) {
            my @lhs = sort keys %egalito;
            my @rhs = sort keys %baseline;
            @egalito = @lhs;
            push @options, [ @rhs ];
            my $match = 1;
            if($#lhs == $#rhs) {
                for my $x (0..$#lhs) {
                    $match = 0 if($lhs[$x] != $rhs[$x]);
                }
                if($match == 1) {
                    $match_option = 1;
                    last;
                }
            }
        }
    }

    if($verbose || !$match_option) {
        print "[$func] a.k.a. @{ $addresses{$address} }\n"
            . "    egalito found       @egalito\n";
        for my $option (@options) {
            print "    ground truth option @{ $option }\n"; 
        }
    }

    $all_ok = 0 if !$match_option;
}

exit 1 if !$all_ok;
