#!/usr/bin/perl

use IPC::Open2;
use POSIX qw(:signal_h :errno_h :sys_wait_h);

my $shell = '../../egalito-head/app/etshell2';

# spawn shell target, getting handles for both stdin and stdout
print "spawning child process {$shell}\n";
my $pid = open2(my $chld_out, my $chld_in, $shell);

# parse the first line of output, which contains address information
print "Press enter to run commands... ";

my $input = 'shell.in';
$input = $ARGV[0] if @ARGV > 0;
open(COMMAND, "<$input") or die;
while(my $command = <COMMAND>) {
    chomp $command;
    print $chld_in "$command\n";
    <STDIN>;  # throw away
    read_more();
}
close COMMAND;

sub read_more {
    # read remaining output from program
    while(my $line = <$chld_out>) {
        chomp $line;
        if($line =~ /egalito.*> /) {
            print "$line";
            last;
        }
        else {
            print "$line\n";
        }
    }
}

# wait for exit status
waitpid( $pid, 0 );

<STDIN>;
