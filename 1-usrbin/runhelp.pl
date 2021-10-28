#!/usr/bin/perl

my $count = 0;
my $success = 0;

for my $file (@ARGV) {
    print "$file: ";
    if(system("$file --help >/dev/null 2>&1") == 0) {
        print "OK\n";
        $success++;
    }
    else {
        print "ERROR " . ($? & 127) . "\n";
    }
    $count++;
}
printf "SUCCESSES : $success/$count (%.2f%%)\n", ($success*100.0/$count);
