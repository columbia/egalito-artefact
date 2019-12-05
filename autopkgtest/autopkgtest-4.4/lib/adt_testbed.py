# adt_testbed.py is part of autopkgtest
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
import sys
import errno
import time
import pipes
import traceback
import re
import signal
import subprocess
import tempfile
import shutil
import urllib.parse

from debian import debian_support

import adtlog
import VirtSubproc


timeouts = {'short': 100, 'copy': 300, 'install': 3000, 'test': 10000,
            'build': 100000}


class Testbed:
    def __init__(self, vserver_argv, output_dir, user,
                 setup_commands=[], setup_commands_boot=[], add_apt_pockets=[],
                 copy_files=[]):
        self.sp = None
        self.lastsend = None
        self.scratch = None
        self.modified = False
        self._need_reset_apt = False
        self.stop_sent = False
        self.dpkg_arch = None
        self.exec_cmd = None
        self.output_dir = output_dir
        self.shared_downtmp = None  # testbed's downtmp on the host, if supported
        self.vserver_argv = vserver_argv
        self.install_tmp_env = []
        self.user = user
        self.setup_commands = setup_commands
        self.setup_commands_boot = setup_commands_boot
        self.add_apt_pockets = add_apt_pockets
        self.copy_files = copy_files
        self.initial_kernel_version = None
        # tests might install a different kernel; [(testname, reboot_marker, kver)]
        self.test_kernel_versions = []
        # used for tracking kernel version changes
        self.last_test_name = ''
        self.last_reboot_marker = ''
        self.eatmydata_prefix = []
        self.apt_pin_for_pockets = []
        self.nproc = None
        self.cpu_model = None
        self.cpu_flags = None

        try:
            self.devnull = subprocess.DEVNULL
        except AttributeError:
            self.devnull = open(os.devnull, 'rb')

        adtlog.debug('testbed init')

    def start(self):
        # are we running from a checkout?
        root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        if os.path.exists(os.path.join(root_dir, '.git')):
            try:
                head = subprocess.check_output(['git', 'show', '--no-patch', '--oneline'],
                                               cwd=root_dir)
                head = head.decode('UTF-8').strip()
            except OSError:
                head = 'cannot determine current HEAD'
            adtlog.info('git checkout: %s' % head)
        else:
            adtlog.info('version @version@')

        # log command line invocation for the log
        adtlog.info('host %s; command line: %s' % (
            os.uname()[1], ' '.join([pipes.quote(w) for w in sys.argv])))

        self.sp = subprocess.Popen(self.vserver_argv,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   universal_newlines=True)
        self.expect('ok', 0)

    def stop(self):
        adtlog.debug('testbed stop')
        if self.stop_sent:
            # avoid endless loop
            return
        self.stop_sent = True

        self.close()
        if self.sp is None:
            return
        ec = self.sp.returncode
        if ec is None:
            self.sp.stdout.close()
            self.send('quit')
            self.sp.stdin.close()
            ec = self.sp.wait()
        if ec:
            self.bomb('testbed gave exit status %d after quit' % ec)
        self.sp = None

    def open(self):
        adtlog.debug('testbed open, scratch=%s' % self.scratch)
        if self.scratch is not None:
            return
        pl = self.command('open', (), 1)
        self._opened(pl)

    def post_boot_setup(self):
        '''Setup after (re)booting the test bed'''

        # provide autopkgtest-reboot command, if reboot is supported; /run is
        # usually "noexec" and /[s]bin might be readonly, so create in /tmp
        if 'reboot' in self.caps and 'root-on-testbed' in self.caps:
            adtlog.debug('testbed supports reboot, creating /tmp/autopkgtest-reboot')
            self.execute(['sh', '-ecC', '''[ ! -e /tmp/autopkgtest-reboot ] || exit 0; '''
                          '''/bin/echo -e '#!/bin/sh -e\\n'''
                          '''[ -n "$1" ] || { echo "Usage: $0 <mark>" >&2; exit 1; }\\n'''
                          '''echo "$1" > /run/autopkgtest-reboot-mark\\n'''
                          '''test_script_pid=$(cat /tmp/autopkgtest_script_pid)\\n'''
                          '''p=$PPID; while true; do read _ c _ pp _ < /proc/$p/stat;'''
                          '''  [ $pp -ne $test_script_pid ] || break; p=$pp; done\\n'''
                          '''kill -KILL $p\\n' > /tmp/autopkgtest-reboot;'''
                          '''chmod 755 /tmp/autopkgtest-reboot;'''
                          '''[ -L /sbin/autopkgtest-reboot ] || ln -s '''
                          '''  /tmp/autopkgtest-reboot /sbin/autopkgtest-reboot 2>/dev/null || true'''])

            self.execute(['sh', '-ecC', '''[ ! -e /tmp/autopkgtest-reboot-prepare ] || exit 0; '''
                          '''/bin/echo -e '#!/bin/sh -e\\n'''
                          '''[ -n "$1" ] || { echo "Usage: $0 <mark>" >&2; exit 1; }\\n'''
                          '''echo "$1" > /run/autopkgtest-reboot-prepare-mark\\n'''
                          '''test_script_pid=$(cat /tmp/autopkgtest_script_pid)\\n'''
                          '''kill -KILL $test_script_pid\\n'''
                          '''while [ -e /run/autopkgtest-reboot-prepare-mark ]; do sleep 0.5; done\\n'''
                          ''' '> /tmp/autopkgtest-reboot-prepare;'''
                          '''chmod 755 /tmp/autopkgtest-reboot-prepare;'''])

        # record running kernel version
        kver = self.check_exec(['uname', '-srv'], True).strip()
        if not self.initial_kernel_version:
            assert not self.last_test_name
            self.initial_kernel_version = kver
            adtlog.info('testbed running kernel: ' + self.initial_kernel_version)
        else:
            if kver != self.initial_kernel_version:
                self.test_kernel_versions.append((self.last_test_name, self.last_reboot_marker, kver))
                adtlog.info('testbed running kernel changed: %s (current test: %s%s)' %
                            (kver, self.last_test_name,
                             self.last_reboot_marker and (', last reboot marker: ' + self.last_reboot_marker) or ''))

        # get CPU info
        if self.nproc is None:
            cpu_info = self.check_exec(['sh', '-c', 'nproc; cat /proc/cpuinfo 2>/dev/null || true'],
                                       stdout=True).strip()
            self.nproc = cpu_info.split('\n', 1)[0]
            m = re.search('^(model.*name|cpu)\s*:\s*(.*)$', cpu_info, re.MULTILINE | re.IGNORECASE)
            if m:
                self.cpu_model = m.group(2)
            m = re.search('^(flags|features)\s*:\s*(.*)$', cpu_info, re.MULTILINE | re.IGNORECASE)
            if m:
                self.cpu_flags = m.group(2)

        xenv = ['AUTOPKGTEST_IS_SETUP_BOOT_COMMAND=1']
        if self.user:
            xenv.append('AUTOPKGTEST_NORMAL_USER=' + self.user)
            xenv.append('ADT_NORMAL_USER=' + self.user)

        for c in self.setup_commands_boot:
            rc = self.execute(['sh', '-ec', c], xenv=xenv, kind='install')[0]
            if rc:
                # setup scripts should exit with 100 if it's the package's
                # fault, otherwise it's considered a transient testbed failure
                if rc == 100:
                    self.badpkg('testbed boot setup commands failed with status 100')
                else:
                    self.bomb('testbed boot setup commands failed with status %i' % rc)

    def _opened(self, pl):
        self.scratch = pl[0]
        self.deps_installed = []
        self.apt_pin_for_pockets = []
        self.recommends_installed = False
        self.exec_cmd = list(map(urllib.parse.unquote, self.command('print-execute-command', (), 1)[0].split(',')))
        self.caps = self.command('capabilities', (), None)
        adtlog.debug('testbed capabilities: %s' % self.caps)
        for c in self.caps:
            if c.startswith('downtmp-host='):
                self.shared_downtmp = c.split('=', 1)[1]

        # provide a default for --user
        if self.user is None and 'root-on-testbed' in self.caps:
            self.user = ''
            for c in self.caps:
                if c.startswith('suggested-normal-user='):
                    self.user = c.split('=', 1)[1]

        self.run_setup_commands()

        # determine testbed architecture
        self.dpkg_arch = self.check_exec(['dpkg', '--print-architecture'], True).strip()
        adtlog.info('testbed dpkg architecture: ' + self.dpkg_arch)

        # do we have eatmydata?
        (code, out, err) = self.execute(['which', 'eatmydata'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if code == 0:
            adtlog.debug('testbed has eatmydata')
            self.eatmydata_prefix = [out.strip()]

        # record package versions of pristine testbed
        if self.output_dir and self.execute(['which', 'dpkg-query'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)[0] == 0:
            pkglist = TempPath(self, 'testbed-packages', autoclean=False)
            self.check_exec(['sh', '-ec', "dpkg-query --show -f '${Package}\\t${Version}\\n' > %s" % pkglist.tb])
            pkglist.copyup()

        self.post_boot_setup()

    def close(self):
        adtlog.debug('testbed close, scratch=%s' % self.scratch)
        if self.scratch is None:
            return
        self.scratch = None
        if self.sp is None:
            return
        self.command('close')
        self.shared_downtmp = None

    def reboot(self, prepare_only=False):
        '''Reboot the testbed'''

        self.command('reboot', prepare_only and ('prepare-only', ) or ())
        self.post_boot_setup()

    def run_setup_commands(self):
        '''Run --setup-commmands and --copy'''

        if not self.setup_commands and not self.add_apt_pockets and not self.copy_files:
            return

        adtlog.info('@@@@@@@@@@@@@@@@@@@@ test bed setup')
        for (host, tb) in self.copy_files:
            adtlog.debug('Copying file %s to testbed %s' % (host, tb))
            Path(self, host, tb, os.path.isdir(host)).copydown()

        # create apt sources for --apt-pocket
        for pocket in self.add_apt_pockets:
            pocket = pocket.split('=', 1)[0]  # strip off package list
            script = '''sed -rn 's/^(deb|deb-src) +(\[.*\] *)?([^ ]*(ubuntu.com|debian.org|ftpmaster|file:\/\/\/tmp\/testarchive)[^ ]*) +([^ -]+) +(.*)$/\\1 \\2\\3 \\5-%s \\6/p' /etc/apt/sources.list `ls /etc/apt/sources.list.d/*.list 2>/dev/null|| true` > /etc/apt/sources.list.d/%s.list; for retry in 1 2 3; do apt-get --no-list-cleanup -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/%s.list -o Dir::Etc::sourceparts=/dev/null update 2>&1 && break || sleep 15; done''' % (pocket, pocket, pocket)
            self.check_exec(['sh', '-ec', script])

        # create apt pinning for --apt-pocket with package list
        for pocket in self.add_apt_pockets:
            # do we have a package list?
            try:
                (pocket, pkglist) = pocket.split('=', 1)
            except ValueError:
                continue
            self._create_apt_pinning_for_packages(pocket, pkglist)

        # record the mtimes of dirs affecting the boot
        boot_dirs = '/boot /etc/init /etc/init.d /etc/systemd/system /lib/systemd/system'
        self.check_exec(['bash', '-ec',
                         'for d in %s; do [ ! -d $d ] || touch -r $d %s/${d//\//_}.stamp; done' % (
                             boot_dirs, self.scratch)])

        xenv = ['AUTOPKGTEST_IS_SETUP_COMMAND=1']
        if self.user:
            xenv.append('AUTOPKGTEST_NORMAL_USER=' + self.user)
            xenv.append('ADT_NORMAL_USER=' + self.user)

        for c in self.setup_commands:
            rc = self.execute(['sh', '-ec', c], xenv=xenv, kind='install')[0]
            if rc:
                # setup scripts should exit with 100 if it's the package's
                # fault, otherwise it's considered a transient testbed failure
                if rc == 100:
                    self.badpkg('testbed setup commands failed with status 100')
                else:
                    self.bomb('testbed setup commands failed with status %i' % rc)

        # if the setup commands affected the boot, then reboot
        if self.setup_commands and 'reboot' in self.caps:
            boot_affected = self.execute(
                ['bash', '-ec', '[ ! -e /run/autopkgtest_no_reboot.stamp ] || exit 0;'
                 'for d in %s; do s=%s/${d//\//_}.stamp;'
                 '  [ ! -d $d ] || [ `stat -c %%Y $d` = `stat -c %%Y $s` ]; done' % (
                     boot_dirs, self.scratch)])[0]
            if boot_affected:
                adtlog.info('rebooting testbed after setup commands that affected boot')
                self.reboot()

    def reset(self, deps_new, with_recommends):
        '''Reset the testbed, if possible and necessary'''

        adtlog.debug('testbed reset: modified=%s, deps_installed=%s(r: %s), deps_new=%s(r: %s)' %
                     (self.modified, self.deps_installed, self.recommends_installed,
                      deps_new, with_recommends))
        if 'revert' in self.caps and (
                self.modified or self.recommends_installed != with_recommends or
                [d for d in self.deps_installed if d not in deps_new]):
            adtlog.debug('testbed reset')
            pl = self.command('revert', (), 1)
            self._opened(pl)
        self.modified = False

    def install_deps(self, deps_new, recommends, shell_on_failure=False):
        '''Install dependencies into testbed'''
        adtlog.debug('install_deps: deps_new=%s, recommends=%s' % (deps_new, recommends))

        self.deps_installed = deps_new
        self.recommends_installed = recommends
        if not deps_new:
            return
        self.satisfy_dependencies_string(', '.join(deps_new), 'install-deps', recommends, shell_on_failure=shell_on_failure)

    def needs_reset(self):
        # show what caused a reset
        (fname, lineno, function, code) = traceback.extract_stack(limit=2)[0]
        adtlog.debug('needs_reset, previously=%s, requested by %s() line %i' %
                     (self.modified, function, lineno))
        self.modified = True

    def bomb(self, m, _type=adtlog.TestbedFailure):
        adtlog.debug('%s %s' % (_type.__name__, m))
        self.stop()
        raise _type(m)

    def badpkg(self, m):
        self.bomb(m, adtlog.BadPackageError)

    def send(self, string):
        try:
            adtlog.debug('sending command to testbed: ' + string)
            self.sp.stdin.write(string)
            self.sp.stdin.write('\n')
            self.sp.stdin.flush()
            self.lastsend = string
        except:
            (type, value, dummy) = sys.exc_info()
            self.bomb('cannot send to testbed: %s' % traceback.
                      format_exception_only(type, value))

    def expect(self, keyword, nresults):
        line = self.sp.stdout.readline()
        if not line:
            self.bomb('unexpected eof from the testbed')
        if not line.endswith('\n'):
            self.bomb('unterminated line from the testbed')
        line = line.rstrip('\n')
        adtlog.debug('got reply from testbed: ' + line)
        ll = line.split()
        if not ll:
            self.bomb('unexpected whitespace-only line from the testbed')
        if ll[0] != keyword:
            if self.lastsend is None:
                self.bomb("got banner `%s', expected `%s...'" %
                          (line, keyword))
            else:
                self.bomb("sent `%s', got `%s', expected `%s...'" %
                          (self.lastsend, line, keyword))
        ll = ll[1:]
        if nresults is not None and len(ll) != nresults:
            self.bomb("sent `%s', got `%s' (%d result parameters),"
                      " expected %d result parameters" %
                      (self.lastsend, line, len(ll), nresults))
        return ll

    def command(self, cmd, args=(), nresults=0, unquote=True):
        # pass args=[None,...] or =(None,...) to avoid more url quoting
        if type(cmd) is str:
            cmd = [cmd]
        if len(args) and args[0] is None:
            args = args[1:]
        else:
            args = list(map(urllib.parse.quote, args))
        al = cmd + args
        self.send(' '.join(al))
        ll = self.expect('ok', nresults)
        if unquote:
            ll = list(map(urllib.parse.unquote, ll))
        return ll

    def execute(self, argv, xenv=[], stdout=None, stderr=None, kind='short'):
        '''Run command in testbed.

        The commands stdout/err will be piped directly to autopkgtest and its log
        files, unless redirection happens with the stdout/stderr arguments
        (passed to Popen).

        Return (exit code, stdout, stderr). stdout/err will be None when output
        is not redirected.
        '''
        env = list(xenv)  # copy
        if kind == 'install':
            env.append('DEBIAN_FRONTEND=noninteractive')
            env.append('APT_LISTBUGS_FRONTEND=none')
            env.append('APT_LISTCHANGES_FRONTEND=none')
        env += self.install_tmp_env

        adtlog.debug('testbed command %s, kind %s, sout %s, serr %s, env %s' %
                     (argv, kind, stdout and 'pipe' or 'raw',
                      stderr and 'pipe' or 'raw', env))

        if env:
            argv = ['env'] + env + argv

        VirtSubproc.timeout_start(timeouts[kind])
        try:
            proc = subprocess.Popen(self.exec_cmd + argv,
                                    stdin=self.devnull,
                                    stdout=stdout, stderr=stderr)
            (out, err) = proc.communicate()
            if out is not None:
                out = out.decode()
            if err is not None:
                err = err.decode()
            VirtSubproc.timeout_stop()
        except VirtSubproc.Timeout:
            # This is a bit of a hack, but what can we do.. we can't kill/clean
            # up sudo processes, we can only hope that they clean up themselves
            # after we stop the testbed
            killtree(proc.pid)
            adtlog.debug('timed out on %s %s (kind: %s)' % (self.exec_cmd, argv, kind))
            if 'sudo' not in self.exec_cmd:
                proc.wait()
            msg = 'timed out on command "%s" (kind: %s)' % (' '.join(argv), kind)
            if kind == 'test':
                adtlog.error(msg)
                raise
            else:
                self.bomb(msg)

        adtlog.debug('testbed command exited with code %i' % proc.returncode)

        if proc.returncode in (254, 255):
            self.command('auxverb_debug_fail')
            self.bomb('testbed auxverb failed with exit code %i' % proc.returncode)

        return (proc.returncode, out, err)

    def check_exec(self, argv, stdout=False, kind='short'):
        '''Run argv in testbed.

        If stdout is True, capture stdout and return it. Otherwise, don't
        redirect and return None.

        argv must succeed and not print any stderr.
        '''
        (code, out, err) = self.execute(argv,
                                        stdout=(stdout and subprocess.PIPE or None),
                                        stderr=subprocess.PIPE, kind=kind)
        if err:
            self.bomb('"%s" failed with stderr "%s"' % (' '.join(argv), err),
                      adtlog.AutopkgtestError)
        if code != 0:
            self.bomb('"%s" failed with status %i' % (' '.join(argv), code),
                      adtlog.AutopkgtestError)
        return out

    def install_apt(self, deps, recommends=False, shell_on_failure=False):
        '''Install dependencies with apt-get into testbed

        This requires root privileges and a writable file system.
        '''
        # create a dummy deb with the deps
        pkgdir = tempfile.mkdtemp(prefix='autopkgtest-satdep.')
        debdir = os.path.join(pkgdir, 'DEBIAN')
        os.chmod(pkgdir, 0o755)
        os.mkdir(debdir)
        os.chmod(debdir, 0o755)
        with open(os.path.join(debdir, 'control'), 'w') as f:
            f.write('''Package: autopkgtest-satdep
Section: oldlibs
Priority: extra
Maintainer: autogenerated
Version: 0
Architecture: %s
Depends: %s
Description: satisfy autopkgtest test dependencies
''' % (self.dpkg_arch, deps))

        deb = TempPath(self, 'autopkgtest-satdep.deb')
        subprocess.check_call(['dpkg-deb', '-b', pkgdir, deb.host],
                              stdout=subprocess.PIPE)
        shutil.rmtree(pkgdir)
        deb.copydown()

        # install it and its dependencies in the tb; our apt pinning is not
        # very clever wrt. resolving transitional dependencies in the pocket,
        # so we might need to retry without pinning
        download_fail_retries = 3
        while True:
            self.check_exec(['dpkg', '--unpack', deb.tb], stdout=subprocess.PIPE)
            # capture status-fd to stderr
            (rc, _, serr) = self.execute(['/bin/sh', '-ec', '%s apt-get install '
                                          '--assume-yes --fix-broken '
                                          '-o APT::Status-Fd=3 '
                                          '-o APT::Install-Recommends=%s '
                                          '-o Dpkg::Options::=--force-confnew '
                                          '-o Debug::pkgProblemResolver=true 3>&2 2>&1' %
                                          (' '.join(self.eatmydata_prefix), recommends)],
                                         kind='install', stderr=subprocess.PIPE)
            if rc != 0:
                adtlog.debug('apt-get install failed; status-fd:\n%s' % serr)
                # check if apt failed during package download, which might be a
                # transient error, so retry
                if 'dlstatus:' in serr and 'pmstatus:' not in serr:
                    download_fail_retries -= 1
                    if download_fail_retries > 0:
                        adtlog.warning('apt failed to download packages, retrying in 10s...')
                        time.sleep(10)
                        continue
                    else:
                        self.bomb('apt repeatedly failed to download packages')

                if shell_on_failure:
                    self.run_shell()
            else:
                # apt-get -f may succeed, but its solution might remove
                # autopkgtest-satdep, which is still a failure
                rc = self.execute(['dpkg', '--status', 'autopkgtest-satdep'],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)[0]

            if rc != 0:
                if self.apt_pin_for_pockets:
                    pocket = self.apt_pin_for_pockets.pop()
                    adtlog.warning('Test dependencies are unsatisfiable with using apt pinning. '
                                   'Retrying with using all packages from %s' % pocket)
                    self.check_exec(['/bin/sh', '-ec', 'rm /etc/apt/preferences.d/autopkgtest-*-' + pocket])
                    continue

                if shell_on_failure:
                    self.run_shell()
                self.badpkg('Test dependencies are unsatisfiable. A common reason is '
                            'that your testbed is out of date with respect to the '
                            'archive, and you need to use a current testbed or run '
                            'apt-get update or use -U.')
            break

        # remove autopkgtest-satdep to avoid confusing tests, but avoid marking our
        # test dependencies for auto-removal
        out = self.check_exec(['apt-get', '--simulate', '--quiet',
                               '-o', 'APT::Get::Show-User-Simulation-Note=False',
                               '--auto-remove',
                               'purge', 'autopkgtest-satdep'],
                              True)
        test_deps = []
        for line in out.splitlines():
            if not line.startswith('Purg '):
                continue
            pkg = line.split()[1]
            if pkg != 'autopkgtest-satdep':
                test_deps.append(pkg)
        if test_deps:
            adtlog.debug('Marking test dependencies as manually installed: %s' %
                         ' '.join(test_deps))
            # avoid overly long command lines
            batch = 0
            while batch < len(test_deps):
                self.check_exec(['apt-mark', 'manual', '-qq'] + test_deps[batch:batch + 20])
                batch += 20

        self.execute(['dpkg', '--purge', 'autopkgtest-satdep'])

    def install_tmp(self, deps, recommends=False):
        '''Unpack dependencies into temporary directory

        This is a fallback if the testbed does not have root privileges or a
        writable file system, and will only work for packages that can be
        used from a different directory with PATH, LD_LIBRARY_PATH, PYTHONPATH
        etc. set.

        Sets/updates self.install_tmp_env to necessary variables.
        '''
        unsupported = []
        pkg_constraints = {}  # pkg -> (relation, version)

        # parse deps into pkg_constraints
        dep_re = re.compile(
            r'(?P<p>[a-z0-9+-.]+)\s*'
            r'(\((?P<r><<|<=|>=|=|>>)\s*(?P<v>[^\)]*)\))?$')
        for dep in deps.split(','):
            dep = dep.strip()
            if not dep:
                continue  # trailing comma
            m = dep_re.match(dep)
            if not m:
                unsupported.append(dep)
                continue
            pkg_constraints[m.group('p')] = (m.group('r'), m.group('v'))

        adtlog.debug('install_tmp: "%s" -> %s, unsupported: %s' %
                     (deps, pkg_constraints, unsupported))

        if unsupported:
            adtlog.warning('The following dependencies cannot be handled in '
                           'reduced "unpack to temporary directory" mode: ' +
                           ', '.join(unsupported))

        # simulate installation, grab packages, and check constraints
        (rc, out, _) = self.execute(['apt-get', '--quiet', '--simulate', '--no-remove',
                                     '-o', 'Debug::pkgProblemResolver=true',
                                     '-o', 'Debug::NoLocking=true',
                                     '-o', 'APT::Install-Recommends=%s' % recommends,
                                     '-o', 'APT::Get::Show-User-Simulation-Note=False',
                                     'install'] + list(pkg_constraints),
                                    stdout=subprocess.PIPE)
        if rc != 0:
            self.badpkg('Test dependencies are unsatisfiable. A common reason is '
                        'that your testbed is out of date with respect to the '
                        'archive, and you need to use a current testbed, or '
                        'try "--setup-commands ro-apt-update".')

        def check_constraint(pkg, ver):
            constraint = pkg_constraints.get(pkg, (None, None))
            if constraint[0] is None:
                return True
            comp = debian_support.version_compare(ver, constraint[1])
            if constraint[0] == '<<':
                return comp < 0
            if constraint[0] == '<=':
                return comp <= 0
            if constraint[0] == '==':
                return comp == 0
            if constraint[0] == '>=':
                return comp >= 0
            if constraint[0] == '>>':
                return comp > 0
            raise ValueError('invalid dependency version relation %s' % constraint[0])

        to_install = []
        for line in out.splitlines():
            if not line.startswith('Inst '):
                continue
            fields = line.split()
            pkg = fields[1]
            if fields[2].startswith('('):
                ver = fields[2][1:]
            elif fields[3].startswith('('):
                ver = fields[3][1:]
            else:
                raise ValueError('Cannot parse line: %s' % line)
            # ignore Python 2 stuff, with PYTHONPATH we can only support one
            # Python major version (3)
            if pkg.startswith('python-') or pkg.startswith('libpython-') or \
               'python2.' in pkg or pkg == 'python':
                adtlog.warning('Ignoring Python 2.x dependency %s, not '
                               'supported in unpack only mode' % pkg)
                continue
            if not check_constraint(pkg, ver):
                self.badpkg('test dependency %s (%s %s) is unsatisfiable: available version %s' %
                            (pkg, pkg_constraints[pkg][0], pkg_constraints[pkg][1], ver))
            to_install.append(pkg)

        adtlog.debug('install_tmp: packages to install: %s' % ' '.join(to_install))

        if not to_install:
            # we already have everything, all good
            return

        adtlog.warning('virtualisation system does not offer root or writable '
                       'testbed; unpacking dependencies to temporary dir, '
                       'which will only work for some packages')

        # download and unpack all debs
        script = '''d=%(t)s/deps
mkdir -p $d; cd $d
apt-get download %(pkgs)s >&2
for p in *.deb; do dpkg-deb --extract $p .; rm $p; done

# executables
echo PATH=$d/sbin:$d/bin:$d/usr/sbin:$d/usr/bin:$d/usr/games:$PATH

# shared libraries / Qt plugins
l=""
q=""
for candidate in $(find $d -type d \( -name 'lib' -o -path '*/lib/*-linux-*' \)); do
    [ -z "$(ls $candidate/*.so $candidate/*.so.* 2>/dev/null)" ] || l="$candidate:$l"
    [ -z "$(ls $candidate/lib*qt*.so* 2>/dev/null)" ] || q="$candidate:$q"
done
[ -z "$l" ] || echo LD_LIBRARY_PATH=$l${LD_LIBRARY_PATH:-}
[ -z "$q" ] || echo QT_PLUGIN_PATH="$q"

# ImageMagick needs some hacks to make python[3]-wand find its library
l=""
for ml in $(ls usr/lib/*-linux-*/libMagick*.so.* 2>/dev/null); do
    if [ -L $ml ]; then continue; fi
    l=$(dirname $ml)
    ln -sf $(basename "$ml") "${ml%%.so.*}.so"
done
if [ -n "$l" ]; then
    [ -d "$l/lib" ] || ln -sf . "$l/lib"
    echo MAGICK_HOME="$d/$l"
fi

# Python modules
p=""
for candidate in $d/usr/lib/python3*/dist-packages; do
    [ ! -d $candidate ] || p="$candidate:$p"
done
[ -z "$p" ] || echo PYTHONPATH=$p${PYTHONPATH:-}

# Perl modules
p=""
for candidate in $d/usr/share/perl* $d/usr/lib/perl5 $d/usr/lib/*/perl5/*; do
    [ ! -d $candidate ] || p="$candidate:$p"
done
[ -z "$p" ] || echo PERL5LIB=$p${PERL5LIB:-}

# gobject-introspection
l=""
if [ -d $d/usr/lib/girepository-1.0 ]; then
    l=$d/usr/lib/girepository-1.0
fi
for candidate in $(find $d -type d -path '*/usr/lib/*/girepository-*'); do
    [ -z "$(ls $candidate/*.typelib 2>/dev/null)" ] || l="$candidate:$l"
done
[ -z "$l" ] || echo GI_TYPELIB_PATH="$l:${GI_TYPELIB_PATH:-}"

# udev rules
if [ -n "$(ls $d/lib/udev/rules.d/*.rules 2>/dev/null)" ] && [ -w /run/udev ]; then
    mkdir -p /run/udev/rules.d
    cp $d/lib/udev/rules.d/*.rules /run/udev/rules.d/
    udevadm control --reload
    udevadm trigger || true
fi
''' % {'t': self.scratch, 'pkgs': ' '.join(to_install)}
        (rc, out, _) = self.execute(['sh', '-euc', script],
                                    stdout=subprocess.PIPE, kind='install')
        if rc != 0:
            self.bomb('failed to download and unpack test dependencies')
        self.install_tmp_env = [l.strip() for l in out.splitlines() if l]
        adtlog.debug('install_tmp: env is now %s' % self.install_tmp_env)

    def install_click(self, clickpath):
        # copy click into testbed
        tp = Path(self, clickpath, os.path.join(
            self.scratch, os.path.basename(clickpath)))
        tp.copydown()
        # install it
        clickopts = ['--all-users']
        if 'AUTOPKGTEST_CLICK_NO_FRAMEWORK_CHECK' in os.environ:
            # this is mostly for testing
            clickopts.append('--force-missing-framework')
        if 'root-on-testbed' in self.caps:
            rc = self.execute(['click', 'install', '--allow-unauthenticated'] +
                              clickopts + [tp.tb], kind='install')[0]
        else:
            rc = self.execute(['pkcon', 'install-local', '--allow-untrusted',
                               tp.tb], kind='install')[0]
        if rc != 0:
            self.badpkg('click install failed with status %i' % rc)

        # work around https://launchpad.net/bugs/1333215
        # we don't want su -l here which resets the environment from
        # self.execute(); so emulate the parts that we want
        # FIXME: move "run as user" as an argument of execute()/check_exec() and run with -l
        self.check_exec(['su', '--shell=/bin/sh', self.user, '-c',
                         ('export USER=%s;' % self.user) +
                         '. /etc/profile >/dev/null 2>&1 || true; '
                         ' . ~/.profile >/dev/null 2>&1 || true; '
                         '[ -z "$UPSTART_SESSION" ] || /sbin/initctl --user start click-user-hooks'])

    def apparmor_click(self, clickpkgs, installed_clicks):
        '''Update AppArmor rules for click tests

        Return True if anything was modified and apparmor_restore_click()
        needs to be called.
        '''
        # check if we are in a click+AppArmor environment
        if self.execute(['sh', '-ec',
                         '[ -d /var/cache/apparmor -a -d /var/lib/apparmor/clicks -a ! -e /var/cache/apparmor/click-ap.rules ] && '
                         'type aa-clickhook >/dev/null 2>&1'])[0] != 0:
            adtlog.debug('testbed does not have AppArmor/click or already has Autopilot click rules, no need to adjust rules')
            return False
        adtlog.debug('testbed has AppArmor/click')

        if 'root-on-testbed' not in self.caps:
            adtlog.warning('Cannot adjust AppArmor rules without root/sudo '
                           'privileges; Autopilot tests will fail and test '
                           'dependencies will not be available!')
            return False

        rules = 'dbus (receive, send) bus=session path=/com/canonical/Autopilot/**,'
        for e in self.install_tmp_env:
            if e.startswith('QT_PLUGIN_PATH='):
                for p in e.split('=', 1)[1].split(':'):
                    p = p.strip()
                    if p:
                        rules += ' %s/** r,' % p
                break

        script = '''echo '%s' > /var/cache/apparmor/click-ap.rules; ''' % rules

        if clickpkgs or installed_clicks:
            adtlog.info('Updating AppArmor rules to allow autopilot introspection for tested clicks')
            script += 'for c in %s; do ' \
                '   info=$(click info %s %s/$(basename "$c")); ' \
                ''' name=$(echo "$info" | sed -rn '/"name"/ {s/^.*: *"([^"]+)",/\\1/; p}'); ''' \
                ''' version=$(echo "$info" | sed -rn '/"version"/ {s/^.*: *"([^"]+)",/\\1/; p}'); ''' \
                '   touch -h /var/lib/apparmor/clicks/${name}_*_${version}.json >/dev/null || true; '\
                'done; ' \
                'for c in %s; do ' \
                '    touch -h /var/lib/apparmor/clicks/${c}_*.json 2>/dev/null || true; ' \
                'done; ' \
                'aa-clickhook --include=/var/cache/apparmor/click-ap.rules' % (
                    ' '.join(clickpkgs),
                    self.user and ('--user ' + self.user) or '',
                    self.scratch,
                    ' '.join(installed_clicks))
        else:
            adtlog.info('Updating AppArmor rules to allow autopilot introspection for all clicks (will take a minute)...')
            script += 'aa-clickhook --force --include=/var/cache/apparmor/click-ap.rules'

        if self.execute(['sh', adtlog.verbosity >= 2 and '-exc' or '-ec', script], kind='install')[0] != 0:
            self.bomb('Failed to update click AppArmor rules')

        return True

    def apparmor_restore_click(self, clickpkgs, installed_clicks):
        '''Restore AppArmor rules after click tests'''

        adtlog.info('Restoring click package AppArmor rules')
        # if we only modified some clicks above, --force will be fast, so it's
        # ok to always do that
        script = 'rm -f /var/cache/apparmor/click-ap.rules; aa-clickhook --force'
        if self.execute(['sh', adtlog.verbosity >= 2 and '-exc' or '-ec', script], kind='install')[0] != 0:
            self.bomb('Failed to update click AppArmor rules')

    def satisfy_dependencies_string(self, deps, what, recommends=False,
                                    build_dep=False, shell_on_failure=False):
        '''Install dependencies from a string into the testbed'''

        adtlog.debug('%s: satisfying %s' % (what, deps))

        # ignore ":native" tags, apt cannot parse them and deps_parse() does
        # not seem to have an option to get rid of them; we always test on the
        # native platform
        deps = deps.replace(':native', '')

        # resolve arch specific dependencies; don't use universal_newlines
        # here, it's broken for stdin on Python 3.2
        if build_dep:
            extra_args = ', reduce_profiles => $supports_profiles, build_dep => 1'
        else:
            extra_args = ''
        perl = subprocess.Popen(['perl', '-'], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE)
        code = '''use Dpkg::Deps;
                  $supports_profiles = ($Dpkg::Deps::VERSION gt '1.04' or 0);
                  $origdeps = '%s';
                  $origdeps =~ s/(^|,)[^<,]+<[^!,>]+>//g if (!$supports_profiles);
                  $dep = deps_parse($origdeps, reduce_arch => 1, host_arch => '%s' %s);
                  $out = $dep->output();
                  # fall back to ignoring build profiles
                  $out =~ s/ <![^ >]+>//g if (!$supports_profiles);
                  print $out, "\\n";
                  ''' % (deps, self.dpkg_arch, extra_args)
        deps = perl.communicate(code.encode('UTF-8'))[0].decode('UTF-8').strip()
        if perl.returncode != 0:
            self.bomb('failed to run perl for parsing dependencies')
        adtlog.debug('%s: architecture resolved: %s' % (what, deps))

        # check if we can use apt-get
        can_apt_get = False
        if 'root-on-testbed' in self.caps:
            rc = self.execute(['test', '-w', '/var/lib/dpkg/status'])[0]
            if rc == 0:
                can_apt_get = True
        adtlog.debug('can use apt-get on testbed: %s' % can_apt_get)

        if can_apt_get:
            self.install_apt(deps, recommends, shell_on_failure)
        else:
            self.install_tmp(deps, recommends)

    def run_shell(self, cwd=None, extra_env=[]):
        '''Run shell in testbed for debugging tests'''

        adtlog.info(' - - - - - - - - - - running shell - - - - - - - - - -')
        self.command('shell', [cwd or '/'] + self.install_tmp_env + extra_env)

    def run_test(self, tree, test, extra_env=[], shell_on_failure=False,
                 shell=False, build_parallel=None):
        '''Run given test in testbed

        tree (a Path) is the source tree root.
        '''
        def _info(m):
            adtlog.info('test %s: %s' % (test.name, m))

        self.last_test_name = test.name

        if test.path and not os.path.exists(os.path.join(tree.host, test.path)):
            self.badpkg('%s does not exist' % test.path)

        for c in test.clicks:
            self.install_click(c)
        need_click_restore = self.apparmor_click(test.clicks, test.installed_clicks)

        # record installed package versions
        if self.output_dir and self.execute(['which', 'dpkg-query'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)[0] == 0:
            pkglist = TempPath(self, test.name + '-packages.all', autoclean=False)
            self.check_exec([
                'sh', '-ec', "dpkg-query --show -f '${Package}\\t${Version}\\n' > %s" % pkglist.tb])
            pkglist.copyup()

            # filter out packages from the base system
            with open(pkglist.host[:-4], 'w') as out:
                join = subprocess.Popen(['join', '-v2', '-t\t',
                                         os.path.join(self.output_dir, 'testbed-packages'), pkglist.host],
                                        stdout=out, env={})
                join.communicate()
                if join.returncode != 0:
                    self.badpkg('failed to call join for test specific package list, code %d' % join.returncode)
            os.unlink(pkglist.host)

        # ensure our tests are in the testbed
        tree.copydown(check_existing=True)

        # stdout/err files in testbed
        so = TempPath(self, test.name + '-stdout', autoclean=False)
        se = TempPath(self, test.name + '-stderr', autoclean=False)

        # create script to run test
        test_artifacts = '%s/%s-artifacts' % (self.scratch, test.name)
        autopkgtest_tmp = '%s/autopkgtest_tmp' % (self.scratch)
        assert self.nproc is not None
        script = 'set -e; ' \
                 'export USER=`id -nu`; ' \
                 '. /etc/profile >/dev/null 2>&1 || true; ' \
                 ' . ~/.profile >/dev/null 2>&1 || true; ' \
                 'buildtree="%(t)s"; ' \
                 'mkdir -p -m 1777 -- "%(a)s"; ' \
                 'export AUTOPKGTEST_ARTIFACTS="%(a)s"; ' \
                 'export ADT_ARTIFACTS="$AUTOPKGTEST_ARTIFACTS"; ' \
                 'mkdir -p -m 755 "%(tmp)s"; export AUTOPKGTEST_TMP="%(tmp)s"; ' \
                 'export ADTTMP="$AUTOPKGTEST_TMP"; ' \
                 'export DEBIAN_FRONTEND=noninteractive; ' \
                 'export LANG=C.UTF-8; ' \
                 '''export DEB_BUILD_OPTIONS=parallel=%(cpu)s; ''' \
                 'unset LANGUAGE LC_CTYPE LC_NUMERIC LC_TIME LC_COLLATE '\
                 '  LC_MONETARY LC_MESSAGES LC_PAPER LC_NAME LC_ADDRESS '\
                 '  LC_TELEPHONE LC_MEASUREMENT LC_IDENTIFICATION LC_ALL;' \
                 'rm -f /tmp/autopkgtest_script_pid; set -C; echo $$ > /tmp/autopkgtest_script_pid; set +C; ' \
                 'trap "rm -f /tmp/autopkgtest_script_pid" EXIT INT QUIT PIPE; '\
                 'cd "$buildtree"; '\
                 % {'t': tree.tb, 'a': test_artifacts, 'tmp': autopkgtest_tmp,
                    'cpu': build_parallel or self.nproc}

        if 'needs-root' in test.restrictions and self.user is not None:
            script += 'export AUTOPKGTEST_NORMAL_USER=%s; ' % self.user
            script += 'export ADT_NORMAL_USER=%s; ' % self.user

        for e in extra_env:
            script += 'export \'%s\'; ' % e
        # there's no way to tell su to not reset $PATH, for install-tmp mode;
        # we also need it to amend fixed values in /etc/environment
        for e in self.install_tmp_env:
            script += 'export %s; ' % e
        # if we have an user upstart session, poke the environment into it
        if self.install_tmp_env:
            script += 'if [ -n "$UPSTART_SESSION" ]; then '
            for e in self.install_tmp_env:
                script += ' initctl --user set-env "%s"; ' % e
            script += 'fi; '

        if test.path:
            test_cmd = os.path.join(tree.tb, test.path)
            script += 'chmod +x %s; ' % test_cmd
        else:
            test_cmd = "bash -ec '%s'" % test.command

        script += 'touch %(o)s %(e)s; ' \
                  '%(t)s 2> >(tee -a %(e)s >&2) > >(tee -a %(o)s);' \
                  % {'t': test_cmd, 'o': so.tb, 'e': se.tb}

        if 'needs-root' not in test.restrictions and self.user is not None:
            if 'root-on-testbed' not in self.caps:
                self.bomb('cannot change to user %s without root-on-testbed' % self.user,
                          adtlog.AutopkgtestError)
            # we don't want -l here which resets the environment from
            # self.execute(); so emulate the parts that we want
            # FIXME: move "run as user" as an argument of execute()/check_exec() and run with -l
            test_argv = ['su', '-s', '/bin/bash', self.user, '-c']

            if 'rw-build-tree' in test.restrictions:
                self.check_exec(['chown', '-R', self.user, tree.tb])
        else:
            # this ensures that we have a PAM/logind session for root tests as
            # well; with some interfaces like ttyS1 or lxc_attach we don't log
            # in to the testbed
            if 'root-on-testbed' in self.caps:
                test_argv = ['su', '-s', '/bin/bash', 'root', '-c']
            else:
                test_argv = ['bash', '-c']

        # run test script
        if test.command:
            _info(test.command)
        _info('[-----------------------')

        # tests may reboot, so we might need to run several times
        self.last_reboot_marker = ''
        timeout = False
        while True:
            if self.last_reboot_marker:
                script_prefix = 'export AUTOPKGTEST_REBOOT_MARK="%s"; export ADT_REBOOT_MARK="$AUTOPKGTEST_REBOOT_MARK"; ' % self.last_reboot_marker
            else:
                script_prefix = ''
            try:
                rc = self.execute(test_argv + [script_prefix + script], kind='test')[0]
            except VirtSubproc.Timeout:
                rc = 1
                timeout = True
                break

            # did the test invoke autopkgtest-reboot?
            if os.WIFSIGNALED(rc) and os.WTERMSIG(rc) == signal.SIGKILL and 'reboot' in self.caps:
                adtlog.debug('test process SIGKILLed, checking for reboot marker')
                (code, reboot_marker, err) = self.execute(
                    ['cat', '/run/autopkgtest-reboot-mark'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if code == 0:
                    self.last_reboot_marker = reboot_marker.strip()
                    adtlog.info('test process requested reboot with marker %s' % self.last_reboot_marker)
                    self.reboot()
                    continue

                adtlog.debug('test process SIGKILLed, checking for prepare-reboot marker')
                (code, reboot_marker, err) = self.execute(
                    ['cat', '/run/autopkgtest-reboot-prepare-mark'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if code == 0:
                    self.last_reboot_marker = reboot_marker.strip()
                    adtlog.info('test process requested preparation for reboot with marker %s' % self.last_reboot_marker)
                    self.reboot(prepare_only=True)
                    continue

                adtlog.debug('no reboot marker, considering a failure')
            break

        # give the setup_trace() cats some time to catch up
        sys.stdout.flush()
        sys.stderr.flush()
        time.sleep(0.3)
        _info('-----------------------]')
        adtlog.debug('testbed executing test finished with exit status %i' % rc)

        # copy stdout/err files to host
        try:
            so.copyup()
            se.copyup()
            se_size = os.path.getsize(se.host)
        except adtlog.TestbedFailure:
            if timeout:
                # if the test timed out, it's likely that the test destroyed
                # the testbed, so ignore this and call it a failure
                adtlog.warning('Copying up test output timed out, ignoring')
                se_size = 0
                so.host = None
                se.host = None
            else:
                # smells like a tmpfail
                raise

        # avoid mixing up stdout (from report) and stderr (from logging) in output
        sys.stdout.flush()
        sys.stderr.flush()
        time.sleep(0.1)

        _info(' - - - - - - - - - - results - - - - - - - - - -')

        if timeout:
            test.failed('timed out')
        elif rc != 0:
            test.failed('non-zero exit status %d' % rc)
        elif se_size != 0 and 'allow-stderr' not in test.restrictions:
            with open(se.host, encoding='UTF-8') as f:
                stderr_top = f.readline().rstrip('\n \t\r')
            test.failed('stderr: %s' % stderr_top)
        else:
            test.passed()

        sys.stdout.flush()
        sys.stderr.flush()

        # skip the remaining processing if the testbed got broken
        if se.host is None:
            adtlog.debug('Skipping remaining log processing and testbed restore after timeout')
            return

        if os.path.getsize(so.host) == 0:
            # don't produce empty -stdout files in --output-dir
            so.autoclean = True

        if se_size != 0 and 'allow-stderr' not in test.restrictions:
            # give tee processes some time to catch up, to avoid mis-ordered logs
            time.sleep(0.2)
            _info(' - - - - - - - - - - stderr - - - - - - - - - -')
            with open(se.host, 'rb') as f:
                while True:
                    block = f.read1(1000000)
                    if not block:
                        break
                    sys.stderr.buffer.write(block)
            sys.stderr.buffer.flush()
        else:
            # don't produce empty -stderr files in --output-dir
            if se_size == 0:
                se.autoclean = True

        # copy artifacts to host, if we have --output-dir
        if self.output_dir:
            ap = Path(self, os.path.join(self.output_dir, 'artifacts'),
                      test_artifacts, is_dir=True)
            ap.copyup()
            # don't keep an empty artifacts dir around
            if not os.listdir(ap.host):
                os.rmdir(ap.host)

        if shell or (shell_on_failure and not test.result):
            self.run_shell(tree.tb, ['AUTOPKGTEST_ARTIFACTS="%s"' % test_artifacts,
                                     'AUTOPKGTEST_TMP="%s"' % autopkgtest_tmp])

        # clean up artifacts and AUTOPKGTEST_TMP dirs
        self.check_exec(['rm', '-rf', test_artifacts, autopkgtest_tmp])

        if need_click_restore:
            self.apparmor_restore_click(test.clicks, test.installed_clicks)
        else:
            adtlog.debug('no need to restore click AppArmor profiles')

    #
    # helper methods
    #

    def _create_apt_pinning_for_packages(self, pocket, pkglist):
        '''Create apt pinning for --apt-pocket=pocket=pkglist'''

        # sort pkglist into source and binary packages
        binpkgs = []
        srcpkgs = []
        for i in pkglist.split(','):
            i = i.strip()
            if i.startswith('src:'):
                srcpkgs.append(i[4:])
            else:
                binpkgs.append(i)

        # get release name
        script = 'SRCS=$(ls /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null|| true); '
        script += '''REL=$(sed -rn '/^(deb|deb-src) .*(ubuntu.com|debian.org|ftpmaster|file:\/\/\/tmp\/testarchive)/ { s/^[^ ]+ +(\[.*\] *)?[^ ]* +([^ -]+) +.*$/\\2/p}' $SRCS | head -n1); '''

        script += 'mkdir -p /etc/apt/preferences.d; '
        script += 'PKGS="%s"; ' % ' '.join(binpkgs)

        # translate src:name entries into binaries of that source
        if srcpkgs:
            script += 'PKGS="$PKGS $(apt-cache showsrc %s | ' \
                '''awk '/^Package-List:/ { show=1; next } (/^ / && show==1) { print $1; next } { show=0 }' |''' \
                '''sort -u | tr '\\n' ' ')"; ''' % \
                ' '.join(srcpkgs)

        # prefer given packages from pocket, other packages from
        # default $REL (prio 900), but make $REL-pocket available for
        # dependency resolution (prio 800)
        script += 'printf "Package: $PKGS\\nPin: release a=${REL}-%(pocket)s\\nPin-Priority: 990\\n\\nPackage: *\\nPin: release a=$REL\\nPin-Priority: 900\\n\\nPackage: *\\nPin: release a=${REL}-updates\\nPin-Priority: 900\\n\\nPackage: *\\nPin: release a=${REL}-%(pocket)s\\nPin-Priority: 800\\n" > /etc/apt/preferences.d/autopkgtest-${REL}-%(pocket)s; ' % \
            {'pocket': pocket}
        self.check_exec(['sh', '-ec', script])
        self.apt_pin_for_pockets.append(pocket)


class Path:
    '''Represent a file/dir with a host and a testbed path'''

    def __init__(self, testbed, host, tb, is_dir=None):
        '''Create a Path object.

        The object itself is just a pair of file names, nothing more. They do
        not need to exist until you call copyup() or copydown() on them.

        testbed: the Testbed object which this refers to
        host: path of the file on the host
        tb: path of the file in testbed
        is_dir: whether path is a directory; None for "unspecified" if you only
                need copydown()
        '''
        self.testbed = testbed
        self.host = host
        self.tb = tb
        self.is_dir = is_dir

    def copydown(self, check_existing=False):
        '''Copy file from the host to the testbed

        If check_existing is True, don't copy if the testbed path already
        exists.
        '''
        if check_existing and self.testbed.execute(['test', '-e', self.tb])[0] == 0:
            adtlog.debug('copydown: tb path %s already exists' % self.tb)
            return

        # create directory on testbed
        self.testbed.check_exec(['mkdir', '-p', os.path.dirname(self.tb)])

        if os.path.isdir(self.host):
            # directories need explicit '/' appended for VirtSubproc
            self.testbed.command('copydown', (self.host + '/', self.tb + '/'))
        else:
            self.testbed.command('copydown', (self.host, self.tb))

        # we usually want our files be readable for the non-root user
        if self.testbed.user:
            rc = self.testbed.execute(['chown', '-R', self.testbed.user, '--', self.tb],
                                      stderr=subprocess.PIPE)[0]
            if rc != 0:
                # chowning doesn't work on all shared downtmps, try to chmod
                # instead
                self.testbed.check_exec(['chmod', '-R', 'go+rwX', '--', self.tb])

    def copyup(self, check_existing=False):
        '''Copy file from the testbed to the host

        If check_existing is True, don't copy if the host path already
        exists.
        '''
        if check_existing and os.path.exists(self.host):
            adtlog.debug('copyup: host path %s already exists' % self.host)
            return

        os.makedirs(os.path.dirname(self.host), exist_ok=True, mode=0o2755)
        assert self.is_dir is not None
        if self.is_dir:
            self.testbed.command('copyup', (self.tb + '/', self.host + '/'))
        else:
            self.testbed.command('copyup', (self.tb, self.host))

    def copyup_rec(self, check_existing=False, rec_level=-1):
        '''Recursively copy files from the testbed to the host

        If check_existing is True, don't copy if the host path already
        exists.
        '''
        assert self.is_dir is not None
        if self.is_dir and (rec_level == -1 or rec_level > 0):
            os.makedirs(self.host, exist_ok=True, mode=0o2755)
            #self.testbed.command('copyup', (self.tb + '/', self.host + '/'))
            r, o, e = self.testbed.execute(['ls', '--file-type', '-1', self.tb],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for f in o.split('\n'):
                if f.endswith('/'):
                    is_dir = True
                else:
                    is_dir = False
                if f.endswith('/') or f.endswith('@'):
                    newp = Path(self.testbed,
                                self.host + '/' + f[:-1],
                                self.tb + '/' + f[:-1],
                                is_dir)
                else:
                    newp = Path(self.testbed,
                                self.host + '/' + f,
                                self.tb + '/' + f,
                                False)
                new_rec = rec_level if rec_level == -1 else rec_level-1
                newp.copyup_rec(check_existing, new_rec)
        elif not self.is_dir:
            if check_existing and (os.path.exists(self.host)
                                   or os.path.islink(self.host)):
                adtlog.debug('copyup: host path %s already exists' % self.host)
                return
            self.testbed.command('copyupnolink', (self.tb, self.host))
        

class TempPath(Path):
    '''Represent a file in the hosts'/testbed's temporary directories

    These are only guaranteed to exit within one testbed run.
    '''
    def __init__(self, testbed, name, is_dir=False, autoclean=True):
        '''Create a temporary Path object.

        The object itself is just a pair of file names, nothing more. They do
        not need to exist until you call copyup() or copydown() on them.

        testbed: the Testbed object which this refers to
        name: name of the temporary file (without path); host and tb
              will then be derived from that
        is_dir: whether path is a directory; None for "unspecified" if you only
                need copydown()
        autoclean: If True (default), remove file when test finishes. Should
                be set to False for files which you want to keep in the
                --output-dir which are useful for reporting results, like test
                stdout/err, log files, and binaries.
        '''
        # if the testbed supports a shared downtmp, use that to avoid
        # unnecessary copying, unless we want to permanently keep the file
        if testbed.shared_downtmp and (not testbed.output_dir or autoclean):
            host = testbed.shared_downtmp
        else:
            host = testbed.output_dir
        self.autoclean = autoclean
        Path.__init__(self, testbed, os.path.join(host, name),
                      os.path.join(testbed.scratch, name),
                      is_dir)

    def __del__(self):
        if self.autoclean:
            if os.path.exists(self.host):
                try:
                    os.unlink(self.host)
                except OSError as e:
                    if e.errno == errno.EPERM:
                        self.testbed.check_exec(['rm', '-rf', self.tb])
                    else:
                        raise

#
# Helper functions
#


def child_ps(pid):
    '''Get all child processes of pid'''

    try:
        out = subprocess.check_output(['ps', '-o', 'pid=', '--ppid', str(pid)])
        return [int(p) for p in out.split()]
    except subprocess.CalledProcessError:
        return []


def killtree(pid):
    '''Recursively kill pid and all of its children'''

    for child in child_ps(pid):
        killtree(child)
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
