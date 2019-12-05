#!/usr/bin/perl

my $EGALITO_ROOT = $ENV{'EGALITO_ROOT'};

#     34: 0000000000000000     0 FILE    LOCAL  DEFAULT  ABS array.c
#     35: 000000000000dbb0   121 FUNC    LOCAL  DEFAULT   14 null_lookup
#     36: 00000000000a4478     4 OBJECT  LOCAL  DEFAULT   25 num_array_types

my %tables = ();
for my $file (`find -H $ARGV[0] -name '*.dfinish'`) {
    # print STDERR $file;
    chomp $file;
    $file =~ m|/([^/]+)\.\d+[^.]+\.dfinish|;
    my $source_file = $1;
    # print "$source_file\n";
    my %file_tables = ();
    for my $line (split /\n/, `$EGALITO_ROOT/test/script/jumptables.pl $file`) {
        $line =~ /\[([^\]]+)\]/;
        $file_tables{$1} .= "$line\\n";
    }
    # $tables{$source_file} .= `$EGALITO_ROOT/test/script/jumptables.pl $file`;
    for my $func (sort keys %file_tables) {
        push @{ $tables{$source_file}->{$func} }, $file_tables{$func};
    }
}
# print %tables;

#for my $t (keys %tables) {
#    for my $f (keys %{ $tables{$t} }) {
#        print STDERR "$t $f\n";
#    }
#}

sub check_function($$$) {
    my ($file, $func, $context) = @_;
    print "$func\n";
    my $data_ref = $tables{$file}->{$func};
    if (defined ($data_ref)) {
        my @data = @{ $data_ref };
        print "jump table in [$func]:$context\n";
        for my $option (@data) {
            print "    $option\n";
        }
        # print "$file $func: {$data}";
    }
    else {
        # print STDERR "$file $func has no jump tables!\n";
    }
}

my $file = "";
while(my $line = <STDIN>) {
    print "[$file] ", $line;
    chomp $line;
    if($line =~ /FILE\s+LOCAL\s+DEFAULT\s+ABS\s+(\S+)/) {
        $file = $1;
    }
    elsif($line =~ /FUNC.*\s+(\S+)$/) {
        my $func = $1;
        if($file ne '' && exists($tables{$file})) {
            check_function($file, $func, '');
            check_function($file, $1, '') if $func =~ /(.*\.constprop)\.\d+$/;
            check_function($file, $1, '') if $func =~ /(.*\.cold)\.\d+$/;
            check_function($file, $1, '') if $func =~ /(.*\.lto_priv)\.\d+$/;
            #my $data_ref = $tables{$file}->{$func};
            #if (defined ($data_ref)) {
            #    my @data = @{ $data_ref };
            #    print "jump table in [$func]:\n";
            #    for my $option (@data) {
            #        print "    $option\n";
            #    }
            #    # print "$file $func: {$data}";
            #}
            #else {
            #    # print STDERR "$file $func has no jump tables!\n";
            #}
        }
        else {
            for my $f (keys %tables) {
                check_function($f, $func, " (from unknown FILE)");
                check_function($f, $1, " (from unknown FILE)") if $func =~ /(.*\.constprop)\.\d+$/;
                check_function($f, $1, " (from unknown FILE)") if $func =~ /(.*\.cold)\.\d+$/;
                check_function($f, $1, " (from unknown FILE)") if $func =~ /(.*\.lto_priv)\.\d+$/;
            }
            #for my $f (keys %tables) {
            #    my $data_ref = $tables{$f}->{$func};
            #    if (defined ($data_ref)) {
            #        my @data = @{ $data_ref };
            #        print "jump table in [$func]: (from unknown FILE)\n";
            #        for my $option (@data) {
            #            print "    $option\n";
            #        }
            #        # print "(unknown) $func: {$data}";
            #    }
            #}
        }
    }
}
