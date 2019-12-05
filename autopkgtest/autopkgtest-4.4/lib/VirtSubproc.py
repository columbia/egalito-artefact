# VirtSubproc is part of autopkgtest
# autopkgtest is a tool for testing Debian binary packages
#
# autopkgtest is Copyright (C) 2006-2007 Canonical Ltd.
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

import __main__

import sys
import os
from urllib.parse import quote as url_quote
from urllib.parse import unquote as url_unquote
import signal
import subprocess
import traceback
import errno
import time
import pipes
import socket
import shutil

import adtlog

progname = "<VirtSubproc>"
devnull_read = open('/dev/null', 'rb')
caller = __main__
copy_timeout = int(os.getenv('AUTOPKGTEST_VIRT_COPY_TIMEOUT', '300'))

downtmp_open = None  # downtmp after opening testbed
downtmp = None  # current downtmp (None after close)
auxverb = None  # prefix to run command argv in testbed
cleaning = False
in_mainloop = False


class Quit(RuntimeError):

    def __init__(self, ec, m):
        self.ec = ec
        self.m = m


class Timeout(RuntimeError):
    pass


def alarm_handler(*a):
    raise Timeout()


def timeout_start(to):
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(to)


def timeout_stop():
    signal.alarm(0)


class FailedCmd(RuntimeError):

    def __init__(self, e):
        self.e = e


def bomb(m):
    if in_mainloop:
        raise Quit(12, progname + ": failure: %s" % m)
    else:
        sys.stderr.write(m)
        sys.stderr.write('\n')
        sys.exit(1)


def ok():
    print('ok')


def cmdnumargs(c, ce, nargs=0, noptargs=0):
    if len(c) < 1 + nargs:
        bomb("too few arguments to command `%s'" % ce[0])
    if noptargs is not None and len(c) > 1 + nargs + noptargs:
        bomb("too many arguments to command `%s'" % ce[0])


def cmd_capabilities(c, ce):
    cmdnumargs(c, ce)
    return caller.hook_capabilities()


def cmd_quit(c, ce):
    cmdnumargs(c, ce)
    raise Quit(0, '')


def cmd_close(c, ce):
    cmdnumargs(c, ce)
    if not downtmp:
        bomb("`close' when not open")
    cleanup()


def cmd_print_execute_command(c, ce):
    global auxverb

    cmdnumargs(c, ce)
    if not downtmp:
        bomb("`print-execute-command' when not open")
    return [','.join(map(url_quote, auxverb))]


def execute_timeout(instr, timeout, *popenargs, **popenargsk):
    '''Popen wrapper with timeout supervision

    If instr is given, it is fed into stdin, otherwise stdin will be /dev/null.

    Return (status, stdout, stderr)
    '''
    adtlog.debug('execute-timeout: ' + ' '.join(popenargs[0]))
    if instr is None:
        popenargsk['stdin'] = devnull_read
    else:
        instr = instr.encode('UTF-8')
    sp = subprocess.Popen(*popenargs,
                          **popenargsk)
    timeout_start(timeout)
    try:
        (out, err) = sp.communicate(instr)
        if out is not None:
            out = out.decode('UTF-8', 'replace')
        if err is not None:
            err = err.decode('UTF-8', 'replace')
    except Timeout:
        try:
            sp.kill()
            sp.wait()
        except OSError as e:
            adtlog.error('WARNING: Cannot kill timed out process %s: %s' %
                         (popenargs[0], e))
        raise
    timeout_stop()
    status = sp.wait()
    return (status, out, err)


def check_exec(argv, downp=False, outp=False, timeout=0, fail_on_stderr=True):
    '''Run successful command (argv list)

    Command must succeed (exit code 0) and not produce any stderr. If downp is
    True, command is run in testbed. If outp is True, stdout will be captured
    and returned. stdin is set to /dev/null.

    Returns stdout (or None if outp is False).
    '''
    global auxverb

    if downp:
        real_argv = auxverb + argv
    else:
        real_argv = argv
    if outp:
        stdout = subprocess.PIPE
    else:
        stdout = None

    (status, out, err) = execute_timeout(None, timeout, real_argv,
                                         stdout=stdout, stderr=subprocess.PIPE)

    if status:
        bomb("%s%s failed (exit status %d, stderr %r)" %
             ((downp and "(down) " or ""), argv, status, err))
    if fail_on_stderr and err:
        bomb("%s unexpectedly produced stderr output `%s'" %
             (argv, err))

    if outp and out and out[-1] == '\n':
        out = out[:-1]
    return out


class timeout:
    def __init__(self, secs, exit_msg=None):
        '''Context manager that times out after given number of seconds.

        If exit_msg is given, the program bomb()s with that message,
        otherwise it raises a Timeout exception.
        '''
        self.secs = secs
        self.exit_msg = exit_msg

    def __enter__(self):
        timeout_start(self.secs)

    def __exit__(self, type_, value, traceback):
        timeout_stop()
        if type_ is Timeout and self.exit_msg:
            bomb(self.exit_msg)
            return True
        return False


def get_unix_socket(path):
    '''Open a connected client socket to given Unix socket with a 5s timeout'''

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    with timeout(5, 'Timed out waiting for %s socket\n' % path):
        while True:
            try:
                s.connect(path)
                break
            except socket.error:
                continue
    return s


def expect(sock, search_bytes, timeout_sec, description=None, echo=False):
    adtlog.debug('expect: "%s"' % (search_bytes or b'<none>').decode())
    what = '"%s"' % (description or search_bytes or 'data')
    out = b''
    with timeout(timeout_sec,
                 description and ('timed out waiting for %s' % what) or None):
        while True:
            block = sock.recv(4096)
            if not block:
                time.sleep(0.1)
                continue
            if echo:
                sys.stderr.buffer.write(block)
            out += block
            if search_bytes is None or search_bytes in out:
                adtlog.debug('expect: found "%s"' % what)
                break

    return out


def cmd_open(c, ce):
    global auxverb, downtmp, downtmp_open
    cmdnumargs(c, ce)
    if downtmp:
        bomb("`open' when already open")
    caller.hook_open()
    adtlog.debug("auxverb = %s, downtmp = %s" % (str(auxverb), downtmp))
    downtmp = caller.hook_downtmp(downtmp_open)
    if downtmp_open and downtmp_open != downtmp:
        bomb('virt-runner failed to restore downtmp path %s, gave %s instead'
             % (downtmp_open, downtmp))
    downtmp_open = downtmp
    return [downtmp]


def downtmp_mktemp(path):
    '''Generate a downtmp

    When a path is given, this is the downtmp that we created when opening the
    testbed the first time. We always want to keep the same path between
    resets, as built package trees sometimes refer to absolute paths and thus
    fail if they get moved around.
    '''
    if path:
        check_exec(['mkdir', '--mode=1777', '--parents', downtmp_open],
                   downp=True)
        return path
    else:
        d = check_exec(['mktemp', '--directory', '--tmpdir', 'autopkgtest.XXXXXX'],
                       downp=True, outp=True)
        check_exec(['chmod', '1777', d], downp=True)
        return d


def downtmp_remove():
    global downtmp, auxverb
    if downtmp:
        execute_timeout(None, copy_timeout,
                        auxverb + ['rm', '-rf', '--', downtmp])
        downtmp = None


def cmd_revert(c, ce):
    global auxverb, downtmp, downtmp_open
    cmdnumargs(c, ce)
    if not downtmp:
        bomb("`revert' when not open")
    if 'revert' not in caller.hook_capabilities():
        bomb("`revert' when `revert' not advertised")
    caller.hook_revert()
    downtmp = caller.hook_downtmp(downtmp_open)
    if downtmp_open and downtmp_open != downtmp:
        bomb('virt-runner failed to restore downtmp path %s, gave %s instead'
             % (downtmp_open, downtmp))
    adtlog.debug("auxverb = %s, downtmp = %s" % (str(auxverb), downtmp))

    return [downtmp]


def cmd_reboot(c, ce):
    global downtmp
    cmdnumargs(c, ce, 0, 1)
    if not downtmp:
        bomb("`reboot' when not open")
    if 'reboot' not in caller.hook_capabilities():
        bomb("`reboot' when `reboot' not advertised")

    # save current downtmp; try a few locations, as /var/cache might be r/o
    # (argh Ubuntu touch)
    directories = '/var/cache /home'
    check_exec(['sh', '-ec', 'for d in %s; do if [ -w $d ]; then '
                '  tar --warning=none --create --absolute-names '
                '''    -f $d/autopkgtest-tmpdir.tar '%s'; '''
                '  rm -f /run/autopkgtest-reboot-prepare-mark; '
                '  exit 0; fi; done; exit 1''' % (directories, downtmp)],
               downp=True, timeout=copy_timeout)
    adtlog.debug('cmd_reboot: saved current downtmp, rebooting')

    try:
        caller.hook_prepare_reboot()
    except AttributeError:
        pass

    # reboot
    if len(c) > 1 and c[1] == 'prepare-only':
        adtlog.info('state saved, waiting for testbed to reboot...')
    else:
        execute_timeout(None, 30, auxverb +
                        ['sh', '-c', '(sleep 3; reboot) >/dev/null 2>&1 &'])
    caller.hook_wait_reboot()

    # restore downtmp
    check_exec(['sh', '-ec', 'for d in %s; do '
                'if [ -e $d/autopkgtest-tmpdir.tar ]; then '
                ' tar --warning=none --extract --absolute-names '
                '     -f $d/autopkgtest-tmpdir.tar;'
                ' rm $d/autopkgtest-tmpdir.tar; exit 0; '
                'fi; done; exit 1' % directories],
               downp=True, timeout=copy_timeout)
    adtlog.debug('cmd_reboot: restored downtmp after reboot')


def get_downtmp_host():
    '''Return host directory of the testbed's downtmp dir, if supported'''

    for cap in caller.hook_capabilities():
        if cap.startswith('downtmp-host='):
            return cap.split('=', 1)[1]
    return None


def copytree(src, dst):
    '''Like shutils.copytree(), but merges with existing dst'''

    if not os.path.exists(dst):
        shutil.copytree(src, dst, symlinks=True)
        return

    for f in os.listdir(src):
        fsrc = os.path.join(src, f)
        subprocess.check_call(['cp', '-r', '--preserve=timestamps,links',
                               '--target-directory', dst, fsrc])


def copyup_shareddir(tb, host, is_dir, downtmp_host, follow_symlinks=True):
    adtlog.debug('copyup_shareddir: tb %s host %s is_dir %s downtmp_host %s'
                 % (tb, host, is_dir, downtmp_host))

    host = os.path.normpath(host)
    tb = os.path.normpath(tb)
    downtmp_host = os.path.normpath(downtmp_host)

    timeout_start(copy_timeout)
    try:
        tb_tmp = None
        if tb.startswith(downtmp):
            # translate into host path
            tb = downtmp_host + tb[len(downtmp):]
        else:
            tb_tmp = os.path.join(downtmp, os.path.basename(host))
            adtlog.debug('copyup_shareddir: tb path %s is not already in '
                         'downtmp, copying to %s' % (tb, tb_tmp))
            check_exec(['cp', '-r', '--preserve=timestamps,links', tb, tb_tmp],
                       downp=True)
            # translate into host path
            tb = os.path.join(downtmp_host, os.path.basename(host))

        if tb == host:
            tb_tmp = None
        else:
            adtlog.debug('copyup_shareddir: tb(host) %s is not already at '
                         'destination %s, copying' % (tb, host))
            if is_dir:
                copytree(tb, host)
            else:
                shutil.copy(tb, host, follow_symlinks=follow_symlinks)

        if tb_tmp:
            adtlog.debug('copyup_shareddir: rm intermediate copy: %s' % tb)
            check_exec(['rm', '-rf', tb_tmp], downp=True)
    finally:
        timeout_stop()


def copydown_shareddir(host, tb, is_dir, downtmp_host):
    adtlog.debug('copydown_shareddir: host %s tb %s is_dir %s downtmp_host %s'
                 % (host, tb, is_dir, downtmp_host))

    host = os.path.normpath(host)
    tb = os.path.normpath(tb)
    downtmp_host = os.path.normpath(downtmp_host)

    timeout_start(copy_timeout)
    try:
        host_tmp = None
        if host.startswith(downtmp_host):
            # translate into tb path
            host = downtmp + host[len(downtmp_host):]
        else:
            host_tmp = os.path.join(downtmp_host, os.path.basename(tb))
            if is_dir:
                if os.path.exists(host_tmp):
                    try:
                        shutil.rmtree(host_tmp)
                    except OSError as e:
                        adtlog.warning('cannot remove old %s, moving it '
                                       'instead: %s' % (host_tmp, e))
                        # some undeletable files? hm, move it aside instead
                        counter = 0
                        while True:
                            p = host_tmp + '.old%i' % counter
                            if not os.path.exists(p):
                                os.rename(host_tmp, p)
                                break
                            counter += 1

                shutil.copytree(host, host_tmp, symlinks=True)
            else:
                shutil.copy(host, host_tmp)
            # translate into tb path
            host = os.path.join(downtmp, os.path.basename(tb))

        if host == tb:
            host_tmp = None
        else:
            check_exec(['rm', '-rf', tb], downp=True)
            check_exec(['cp', '-r', '--preserve=timestamps,links', host, tb],
                       downp=True)
        if host_tmp:
            (is_dir and shutil.rmtree or os.unlink)(host_tmp)
    finally:
        timeout_stop()


def copyupdown(c, ce, upp, follow_symlinks=True):
    cmdnumargs(c, ce, 2)
    copyupdown_internal(ce[0], c[1:], upp, follow_symlinks)


def copyupdown_internal(wh, sd, upp, follow_symlinks=True):
    '''Copy up/down a file or dir.

    wh: 'copyup' or 'copydown'
    sd: (source, destination) paths
    upp: True for copyup, False for copydown
    '''
    if not downtmp:
        bomb("%s when not open" % wh)
    if not sd[0] or not sd[1]:
        bomb("%s paths must be nonempty" % wh)
    dirsp = sd[0][-1] == '/'
    if dirsp != (sd[1][-1] == '/'):
        bomb("%s paths must agree about directoryness"
             " (presence or absence of trailing /)" % wh)

    # if we have a shared directory, we just need to copy it from/to there; in
    # most cases, it's testbed end is already in the downtmp dir
    downtmp_host = get_downtmp_host()
    if downtmp_host:
        try:
            if upp:
                copyup_shareddir(sd[0], sd[1], dirsp, downtmp_host, follow_symlinks)
            else:
                copydown_shareddir(sd[0], sd[1], dirsp, downtmp_host)
            return
        except Timeout:
            raise FailedCmd(['timeout'])
        except (shutil.Error, subprocess.CalledProcessError) as e:
            adtlog.debug('Cannot copy %s to %s through shared dir: %s, falling back to tar' %
                         (sd[0], sd[1], str(e)))

    isrc = 0
    idst = 1
    ilocal = 0 + upp
    iremote = 1 - upp

    deststdout = devnull_read
    srcstdin = devnull_read
    remfileq = pipes.quote(sd[iremote])
    if not dirsp:
        rune = 'cat %s%s' % ('><'[upp], remfileq)
        if upp:
            deststdout = open(sd[idst], 'wb')
        else:
            srcstdin = open(sd[isrc], 'rb')
            status = os.fstat(srcstdin.fileno())
            if status.st_mode & 0o111:
                rune += '; chmod +x -- %s' % (remfileq)
        localcmdl = ['cat']
    else:
        taropts = [None, None]
        taropts[isrc] = '--warning=none -c .'
        taropts[idst] = '--warning=none --preserve-permissions --extract ' \
                        '--no-same-owner'

        rune = 'cd %s; tar %s -f -' % (remfileq, taropts[iremote])
        if upp:
            try:
                os.mkdir(sd[ilocal])
            except (IOError, OSError) as oe:
                if oe.errno != errno.EEXIST:
                    raise
        else:
            rune = ('if ! test -d %s; then mkdir -- %s; fi; ' % (
                remfileq, remfileq)
            ) + rune

        localcmdl = ['tar', '--directory', sd[ilocal]] + (
            ('%s -f -' % taropts[ilocal]).split()
        )
    downcmdl = auxverb + ['sh', '-ec', rune]

    if upp:
        cmdls = (downcmdl, localcmdl)
    else:
        cmdls = (localcmdl, downcmdl)

    adtlog.debug(str(["cmdls", str(cmdls)]))
    adtlog.debug(str(["srcstdin", str(srcstdin), "deststdout",
                      str(deststdout), "devnull_read", devnull_read]))

    subprocs = [None, None]
    adtlog.debug(" +< %s" % ' '.join(cmdls[0]))
    subprocs[0] = subprocess.Popen(cmdls[0], stdin=srcstdin,
                                   stdout=subprocess.PIPE)
    adtlog.debug(" +> %s" % ' '.join(cmdls[1]))
    subprocs[1] = subprocess.Popen(cmdls[1], stdin=subprocs[0].stdout,
                                   stdout=deststdout)
    subprocs[0].stdout.close()
    try:
        timeout_start(copy_timeout)
        for sdn in [1, 0]:
            adtlog.debug(" +" + "<>"[sdn] + "?")
            status = subprocs[sdn].wait()
            if not (status == 0 or (sdn == 0 and status == -13)):
                timeout_stop()
                bomb("%s %s failed, status %d" %
                     (wh, ['source', 'destination'][sdn], status))
        timeout_stop()
    except Timeout:
        for sdn in [1, 0]:
            subprocs[sdn].kill()
            subprocs[sdn].wait()
        raise FailedCmd(['timeout'])


def cmd_copydown(c, ce):
    copyupdown(c, ce, False)


def cmd_copyup(c, ce):
    copyupdown(c, ce, True)

def cmd_copyupnolink(c, ce):
    copyupdown(c, ce, True, follow_symlinks=False)


def cmd_shell(c, ce):
    cmdnumargs(c, ce, 1, None)
    if not downtmp:
        bomb("`shell' when not open")
    # runners can provide a hook if they need a special treatment
    try:
        caller.hook_shell(*c[1:])
    except AttributeError:
        adtlog.debug('cmd_shell: using default shell command, dir %s' % c[1])
        cmd = 'cd "%s"; ' % c[1]
        for e in c[2:]:
            cmd += 'export "%s"; ' % e
        # use host's $TERM to provide a sane shell
        try:
            cmd += 'export TERM="%s"; ' % os.environ['TERM']
        except KeyError:
            pass
        cmd += 'bash -i'
        try:
            with open('/dev/tty', 'rb') as sin:
                with open('/dev/tty', 'wb') as sout:
                    with open('/dev/tty', 'wb') as serr:
                        subprocess.call(auxverb + ['sh', '-c', cmd],
                                        stdin=sin, stdout=sout, stderr=serr)
        except (OSError, IOError) as e:
            adtlog.error('Cannot run shell: %s' % e)


def command():
    sys.stdout.flush()
    while True:
        try:
            ce = sys.stdin.readline().strip()
            # FIXME: This usually means EOF (as checked below), but with Python
            # 3 we often get empty strings here even though this is supposed to
            # block for new input.
            if ce == '':
                time.sleep(0.1)
                continue
            break
        except IOError as e:
            if e.errno == errno.EAGAIN:
                time.sleep(0.1)
                continue
            else:
                raise
    if not ce:
        bomb('end of file - caller quit?')
    ce = ce.rstrip().split()
    c = list(map(url_unquote, ce))
    if not c:
        bomb('empty commands are not permitted')
    adtlog.debug('executing ' + ' '.join(ce))
    c_lookup = c[0].replace('-', '_')
    try:
        f = globals()['cmd_' + c_lookup]
    except KeyError:
        bomb("unknown command `%s'" % ce[0])
    try:
        r = f(c, ce)
        if not r:
            r = []
        r.insert(0, 'ok')
    except FailedCmd as fc:
        r = fc.e
    print(' '.join(r))


signal_list = [	signal.SIGHUP, signal.SIGTERM,
                signal.SIGINT, signal.SIGPIPE]


def sethandlers(f):
    for signum in signal_list:
        signal.signal(signum, f)


def cleanup():
    global downtmp, cleaning
    adtlog.debug("cleanup...")
    sethandlers(signal.SIG_DFL)
    # avoid recursion if something bomb()s in hook_cleanup()
    if not cleaning:
        cleaning = True
        if downtmp:
            caller.hook_cleanup()
        cleaning = False
        downtmp = None


def error_cleanup():
    try:
        ok = False
        try:
            cleanup()
            ok = True
        except Quit as q:
            sys.stderr.write(q.m)
            sys.stderr.write('\n')
        except:
            sys.stderr.write('Unexpected cleanup error:\n')
            traceback.print_exc()
            sys.stderr.write('\n')
        if not ok:
            sys.stderr.write('while cleaning up because of another error:\n')
    except:
        pass


def prepare():
    def handler(sig, *any):
        cleanup()
        os.kill(os.getpid(), sig)
    sethandlers(handler)


def cmd_auxverb_debug_fail(c, ce):
    cmdnumargs(c, ce)
    try:
        adtlog.info(caller.hook_debug_fail())
    except AttributeError:
        pass


def mainloop():
    global in_mainloop
    in_mainloop = True

    try:
        while True:
            command()
    except Quit as q:
        error_cleanup()
        if q.m:
            sys.stderr.write(q.m)
            sys.stderr.write('\n')
        sys.exit(q.ec)
    except:
        error_cleanup()
        sys.stderr.write('Unexpected error:\n')
        traceback.print_exc()
        sys.exit(16)
    finally:
        in_mainloop = False


def main():
    ok()
    prepare()
    mainloop()
