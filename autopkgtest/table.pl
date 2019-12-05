#!/usr/bin/perl

my %p = ();

my @result = `for file in build-*/testlog; do echo -n \$file --; tail -n 1 \$file; done`;
for my $result (@result) {
    $result =~ m|build-([^/]+)/| or next;
    my $name = $1;
    if($result =~ /FAIL/) { $p{$name} = 'fail' }
    elsif($result =~ /PASS/) { $p{$name} = 'pass' }
    elsif($result =~ /SKIP/) { $p{$name} = 'skip' }
    else { $p{$name} = 'error' }
}

my @false = `for file in build-*/testlog; do echo -n "\$file "; grep -c 'ymbol lookup error' \$file; done | awk '\$2 > 0 { print \$1 }'`;
for my $false (@false) {
    $false =~ m|build-([^/]+)/| or next;
    my $name = $1;
    #print "FALSE $name\n";
    $p{$name} = 'false' if $p{$name} eq 'fail';
}

#my @fail = `for file in build-*/testlog; do echo -n \$file --; tail -n 1 \$file; done | grep FAIL | perl -ne 'm|build-([^/]+)/| && print "$1\n"'`;
#for my $fail (@fail) {
#    chomp $fail;
#    $p{$fail} = 'fail';
#}

my @throw = split /\s/, `awk '\$2 > 0 { print \$1 }' throws3`;
for my $t (@throw) {
    #$t =~ s/\s//g;
    if($p{$t} eq 'fail') {
        $p{$t} = 'throw';
    }
}

for my $package (sort keys %p) {
    my %message = (
        'pass' => 'all tests pass',
        'fail' => 'at least one test fails',
        'false' => 'fails in chroot, false negative?',
        'error' => 'autopkgtest dependency error',
        'skip' => 'package contains no autopkgtests',
        'throw' => 'fails, but code uses exceptions',
    );
    my $type = $p{$package};
    #my $result = $type;
    #next if $result eq 'skip';
    #$result = 'skip' if($result eq 'error');
    #$result = 'skip' if($result eq 'false');
    #$result = 'fail' if($result eq 'throw');
    #print "\\texttt{$package} & $result & $message{$type} \\\\\n";

    next if $type eq 'skip';
    my %message2 = (
        'pass' => 'pass',
        'fail' => 'fail-1',
        'skip' => 'skip-0',
        'false' => 'skip-C',
        'error' => 'skip-1',
        'throw' => 'fail-T'
    );
    print "\\texttt{$package} & $message2{$type} \\\\\n";
}
