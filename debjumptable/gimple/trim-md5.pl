#!/usr/bin/perl

if(@ARGV != 1) {
	die "Usage: $0 dir-to-parse\n";
}

my @files = `find -H $ARGV[0] -type f`;
my %h = ();
my $count = 0;
for my $file (@files) {
	chomp $file;
	my $hash = `md5sum $file`;
	$hash =~ /(\S+)/;
	# print "[$file] => [$1]\n";
	if(exists($h{$1})) {
		#print "rm '$file'\n";
		unlink $file;
		$count ++;
	}
	$h{$1} ++;
}
print "Trimmed $count files from $ARGV[0]\n";
