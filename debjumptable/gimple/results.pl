#!/usr/bin/perl

use List::Util qw[max];

my %OVERRIDE = (
    'python2.7-minimal' => 'good',
    #'coreutils' => 'good',
    'e2fsprogs' => 'good',
    'iproute2' => 'good',
    'dirmngr' => 'good',
    'modemmanager' => 'good',       # verified through disasm
    'network-manager' => 'skip',  # no symbols for libs
);
my %exelist = ();
my %tablelist = ();
my %heuristiclist = ();
my %result = ();

my @files = @ARGV;
for my $file (@files) {
    $file =~ m|([^/]+)\.log|;
    my $name = $1;
    open(FILE, $file) or die;

    $tablelist{$name} = 0;
    $result{$name} = $OVERRIDE{$name} if defined($OVERRIDE{$name});

    my $line = '';
    my $last = '';
    my @exes = ();
    my $function = '';
    my %tables = ();
    while($line = <FILE>) {
        chomp $line;
        if($line =~ /^Executables: (.*)/) {
            @exes = split / /, $1;
        }
        elsif(@exes > 0 && $line =~ /^\[(\S+)\] a\.k\.a\./) {
            $function = $1;
        }
        elsif(@function ne '' && $line =~ /^    ground truth option (.*)/) {
            my $c = scalar(split / /, $1);
            $tables{$function} = $c if($c > $tables{$function});
        }
        $last = $line unless $line eq '';
    }

    @{ $exelist{$name} } = @exes;
    for my $f (keys %tables) {
        $tablelist{$name} += $tables{$f};
    }

    # last line
    if($last eq 'jumptable diff seems OK') {
        $result{$name} = 'good' unless defined($result{$name});
    }
    elsif($last eq 'Failure: couldn\'t build package!') {
        $result{$name} = 'skip' unless defined($result{$name});
    }
    elsif($last eq 'MISMATCH in jumptable detection') {
        if($tablelist{$name} > 0) {
            $result{$name} = 'fail' unless defined($result{$name});
        }
        else {
            $result{$name} = 'good' unless defined($result{$name});
        }
    }
    else {
        print STDERR "Unknown status ($name): $last\n";
    }

    close FILE;

    if($result{$name} eq 'good') {
        my @list = glob "build-$name/exe/*-*";
        my $n = 0;
        for my $exe (@list) {
            open(TABLES, "$exe/tables.egalito") or die;
            while(my $j = <TABLES>) {
                $n ++ if $j =~ /jump table/;
            }
            close TABLES;
        }
        $tablelist{$name} = $n;
    }
    if($result{$name} eq 'good') {
        my @list = glob "build-$name/exe/*-*";
        #print "(@list)\n";
        my $n = 0;
        for my $exe (@list) {
            open(LOG, "$exe/egalito.log") or die;
            while(my $l = <LOG>) {
                $n ++ if $l =~ /^APPARENTLY, /;
            }
            close LOG;
        }
        $heuristiclist{$name} = $n;
    }
}

my @types = ('good', 'fail', 'skip');
my %finalexe = ();
my %finaltable = ();
for my $type (@types) {
    print "$type list:";
    my $count = 0;
    my $execount = 0;
    my $tablecount = 0;
    my $heuristiccount = 0;
    for my $r (sort keys %result) {
        if($result{$r} eq $type) {
            print " $r";
            $count ++;
            $execount += scalar @{ $exelist{$r} };
            $tablecount += $tablelist{$r};
            $heuristiccount += $heuristiclist{$r};
        }
    }
    print "\n";
    print "$type count: $count packages, $execount exes, $tablecount tables, $heuristiccount needed heuristic\n";
    $finalexe{$type} = $execount;
    if($type eq 'good') {
        $finaltable{'good'} = ($tablecount - $heuristiccount);
        $finaltable{'total'} = $tablecount;
    }
}
printf "FINAL: %.2f%% of exes are good, %.2f%% of tables had bounds\n",
    ($finalexe{'good'}*100.0/($finalexe{'good'}+$finalexe{'fail'})),
    ($finaltable{'good'}*100.0/($finaltable{'total'}));
