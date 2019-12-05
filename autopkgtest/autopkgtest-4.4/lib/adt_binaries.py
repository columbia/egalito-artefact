# adt_binaries.py is part of autopkgtest
# autopkgtest is a tool for testing Debian binary packages
#
# autopkgtest is Copyright (C) 2006-2015 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# See the file CREDITS for a full list of credits information (often
# installed as /usr/share/doc/autopkgtest/CREDITS).

import os
import subprocess
import atexit
import shutil
import errno

import adtlog
import adt_testbed


class DebBinaries:
    '''Registration and installation of .debs'''

    def __init__(self, testbed, output_dir):
        adtlog.debug('Binaries: initialising')

        self.testbed = testbed
        self.output_dir = output_dir

        # the binary dir must exist across testbed reopenings, so don't use a
        # TempPath
        self.dir = adt_testbed.Path(
            self.testbed, os.path.join(self.output_dir, 'binaries'),
            os.path.join(self.testbed.scratch, 'binaries'), is_dir=True)
        os.mkdir(self.dir.host)
        self.registered = set()

        # clean up an empty binaries output dir
        atexit.register(lambda: os.path.exists(self.dir.host) and (
            os.listdir(self.dir.host) or os.rmdir(self.dir.host)))

        self.need_apt_reset = False

    def register(self, path, pkgname):
        adtlog.debug('Binaries: register deb=%s pkgname=%s ' % (path, pkgname))

        dest = os.path.join(self.dir.host, pkgname + '.deb')

        # link or copy to self.dir
        try:
            os.remove(dest)
        except (IOError, OSError) as oe:
            if oe.errno != errno.ENOENT:
                raise oe
        try:
            os.link(path, dest)
        except (IOError, OSError) as oe:
            if oe.errno != errno.EXDEV:
                raise oe
            shutil.copy(path, dest)
        # clean up locally built debs (what=ubtreeN) to keep a clean
        # --output-dir, but don't clean up --binary arguments
        if path.startswith(self.output_dir):
            atexit.register(lambda f: os.path.exists(f) and os.unlink(f), path)
        self.registered.add(pkgname)

    def publish(self):
        if not self.registered:
            adtlog.debug('Binaries: no registered binaries, not publishing anything')
            return
        adtlog.debug('Binaries: publish')

        try:
            with open(os.path.join(self.dir.host, 'Packages'), 'w') as f:
                subprocess.check_call(['apt-ftparchive', 'packages', '.'],
                                      cwd=self.dir.host, stdout=f)
            with open(os.path.join(self.dir.host, 'Release'), 'w') as f:
                subprocess.call(['apt-ftparchive', 'release', '.'],
                                cwd=self.dir.host, stdout=f)
        except subprocess.CalledProcessError as e:
            adtlog.bomb('apt-ftparchive failed: %s' % e)

        # copy binaries directory to testbed; self.dir.tb might have changed
        # since last time due to a reset, so update it
        self.dir.tb = os.path.join(self.testbed.scratch, 'binaries')
        self.testbed.check_exec(['rm', '-rf', self.dir.tb])
        self.dir.copydown()

        aptupdate_out = adt_testbed.TempPath(self.testbed, 'apt-update.out')
        script = '''
  printf 'Package: *\\nPin: origin ""\\nPin-Priority: 1002\\n' > /etc/apt/preferences.d/90autopkgtest
  echo "deb [trusted=yes] file://%(d)s /" >/etc/apt/sources.list.d/autopkgtest.list
  if [ "x`ls /var/lib/dpkg/updates`" != x ]; then
    echo >&2 "/var/lib/dpkg/updates contains some files, aargh"; exit 1
  fi
  apt-get --quiet --no-list-cleanup -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/autopkgtest.list -o Dir::Etc::sourceparts=/dev/null update 2>&1
  cp /var/lib/dpkg/status %(o)s
  ''' % {'d': self.dir.tb, 'o': aptupdate_out.tb}
        self.need_apt_reset = True
        self.testbed.check_exec(['sh', '-ec', script], kind='install')

        aptupdate_out.copyup()

        adtlog.debug('Binaries: publish reinstall checking...')
        pkgs_reinstall = set()
        pkg = None
        for l in open(aptupdate_out.host, encoding='UTF-8'):
            if l.startswith('Package: '):
                pkg = l[9:].rstrip()
            elif l.startswith('Status: install '):
                if pkg in self.registered:
                    pkgs_reinstall.add(pkg)
                    adtlog.debug('Binaries: publish reinstall needs ' + pkg)

        if pkgs_reinstall:
            rc = self.testbed.execute(
                ['apt-get', '--quiet', '-o', 'Debug::pkgProblemResolver=true',
                 '-o', 'APT::Get::force-yes=true',
                 '-o', 'APT::Get::Assume-Yes=true',
                 '--reinstall', 'install'] + list(pkgs_reinstall),
                kind='install')[0]
            if rc:
                adtlog.badpkg('installation of basic binaries failed, exit code %d' % rc)

        adtlog.debug('Binaries: publish done')

    def reset(self):
        '''Revert apt configuration for testbeds without reset'''

        if self.need_apt_reset and 'revert' not in self.testbed.caps:
            adtlog.info('Binaries: resetting testbed apt configuration')
            self.testbed.check_exec(
                ['sh', '-ec',
                 'rm -f /etc/apt/sources.list.d/autopkgtest.list /etc/apt/preferences.d/90autopkgtest; '
                 '(apt-get --quiet update || (sleep 15; apt-get update)) 2>&1'],
                kind='install')

            self.need_apt_reset = False
