# adt_run_args is part of autopkgtest
# autopkgtest is a tool for testing Debian binary packages
#
# autopkgtest is Copyright (C) 2006-2014 Canonical Ltd.
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
import re
import argparse
from glob import glob

import adtlog
import testdesc
import adt_testbed

__all__ = ['parse_args']


def is_click_src(path):
    '''Check if path is a click source tree'''

    if os.path.isdir(os.path.join(path, 'click')):
        return True
    if glob(os.path.join(path, 'manifest.json*')):
        return True
    return False


def interpret_implicit_args(parser, args):
    '''Heuristically translate positional arguments to actions'''

    known_suffix = {
        '.dsc': '--source',
        '.deb': '--binary',
        '.changes': '--changes',
        '.click': '--click',
    }
    pos = 0
    result = []

    while pos < len(args):
        # jump over option args
        if args[pos] == '-B':
            args[pos] = '--no-built-binaries'
        if args[pos].startswith('--') and 'binaries' in args[pos]:
            result.append(args[pos])
            pos += 1
            continue

        if args[pos].startswith('--'):
            result.append(args[pos])
            if '=' not in args[pos]:
                try:
                    result.append(args[pos + 1])
                except IndexError:
                    pass
                pos += 1
            pos += 1
            continue

        # actions based on file name suffix
        for suffix, action in known_suffix.items():
            if args[pos].endswith(suffix):
                result += [action, args[pos]]
                break
        else:
            if is_click_src(args[pos]):
                result += ['--click-source', args[pos]]
            elif os.path.isdir(args[pos]) and args[pos].endswith('//'):
                result += ['--unbuilt-tree', args[pos]]
            elif os.path.isdir(args[pos]) and args[pos].endswith('/'):
                result += ['--built-tree', args[pos]]
            # actions based on patterns
            elif re.match('[0-9a-z][0-9a-z.+-]+$', args[pos]):
                result += ['--apt-source', args[pos]]
            else:
                parser.error('%s: unsupported action argument' % args[pos])

        pos += 1

    return result


actions = None
built_binaries = None


class ArgumentParser(argparse.ArgumentParser):
    '''autopkgtest ArgumentParser

    It enables include files with '@' and trims whitespace from their lines.
    '''
    def __init__(self, **kwargs):
        super(ArgumentParser, self).__init__(fromfile_prefix_chars='@',
                                             **kwargs)

    def convert_arg_line_to_args(self, arg_line):
        return [arg_line.strip()]


class ActionArg(argparse.Action):
    def __call__(self, parser, args, value, option_string):
        global actions, built_binaries
        if option_string == '--changes':
            try:
                files = testdesc.parse_rfc822(value).__next__()['Files']
            except (StopIteration, KeyError):
                parser.error('%s is invalid and does not contain Files:'
                             % value)
            dsc_dir = os.path.dirname(value)
            act_bin = []
            act_src = []
            for f in files.split():
                if '.' in f and '_' in f:
                    fpath = os.path.join(dsc_dir, f)
                    if f.endswith('.deb'):
                        act_bin.append(('binary', fpath, None))
                    elif f.endswith('.dsc'):
                        act_src.append(('source', fpath, False))

            # we need to register the binaries before the source
            actions += act_bin + act_src
            return

        if option_string in ('--apt-source', '--built-tree'):
            bins = False
        # these are the only types where built_binaries applies
        elif option_string in ('--unbuilt-tree', '--source', '--git-source'):
            bins = built_binaries
        else:
            bins = None
        actions.append((option_string.lstrip('-'), value, bins))


class BinariesArg(argparse.Action):
    def __call__(self, parser, args, value, option_string=None):
        global built_binaries

        if option_string == '--no-built-binaries':
            built_binaries = False
        elif option_string == '--built-binaries':
            built_binaries = True
        else:
            raise NotImplementedError('cannot handle BinariesArg ' +
                                      option_string)


def parse_args(arglist=None):
    '''Parse adt-run command line arguments.

    Return (options, actions, virt-server-args).
    '''
    global actions, built_binaries

    actions = []
    built_binaries = True

    # action parser; instantiated first to use generated help
    action_parser = argparse.ArgumentParser(usage=argparse.SUPPRESS,
                                            add_help=False)
    action_parser.add_argument(
        '--unbuilt-tree', action=ActionArg, metavar='DIR or DIR//',
        help='run tests from unbuilt Debian source tree DIR')
    action_parser.add_argument(
        '--built-tree', action=ActionArg, metavar='DIR or DIR/',
        help='run tests from built Debian source tree DIR')
    action_parser.add_argument(
        '--source', action=ActionArg, metavar='DSC or some/pkg.dsc',
        help='build DSC and use its tests and/or generated binary packages')
    action_parser.add_argument(
        '--git-source', action=ActionArg, metavar='GITURL [branchname]',
        help='check out git URL (optionally a non-default branch), build it '
        'if necessary, and run its tests')
    action_parser.add_argument(
        '--binary', action=ActionArg, metavar='DEB or some/pkg.deb',
        help='use binary package DEB for subsequent tests')
    action_parser.add_argument(
        '--changes', action=ActionArg, metavar='CHANGES or some/pkg.changes',
        help='run tests from dsc and binary debs from a .changes file')
    action_parser.add_argument(
        '--apt-source', action=ActionArg, metavar='SRCPKG or somesrc',
        help='download with apt-get source in testbed and use its tests')
    action_parser.add_argument(
        '--click-source', action=ActionArg, metavar='CLICKSRC or some/src',
        help='click source tree for subsequent --click package')
    action_parser.add_argument(
        '--click', action=ActionArg, metavar='CLICKPKG or some/pkg.click',
        help='install click package into testbed (path to *.click) or '
        'use an already installed click package ("com.example.myapp") '
        'and run its tests (from manifest\'s x-source or preceding '
        '--click-source)')
    action_parser.add_argument(
        '--override-control', action=ActionArg,
        metavar='CONTROL', help='run tests from control file/manifest CONTROL'
        ' instead in the next package')
    action_parser.add_argument(
        '--testname', action=ActionArg,
        help='run only given test name in the next package')
    action_parser.add_argument(
        '-B', '--no-built-binaries', nargs=0, action=BinariesArg,
        help='do not use any binaries from subsequent --source, '
        '--git-source, or --unbuilt-tree actions')
    action_parser.add_argument(
        '--built-binaries', nargs=0, action=BinariesArg,
        help='use binaries from subsequent --source, --git-source, or '
        '--unbuilt-tree actions')

    # main / options parser
    usage = '%(prog)s [options] action [action ...] --- virt-server [options]'
    description = '''Test installed binary packages using the tests in the source package.

Actions specify the source and binary packages to test, or change
what happens with package arguments:
%s
''' % action_parser.format_help().split('\n', 1)[1]

    epilog = '''The --- argument separates the adt-run actions and options from the
virt-server which provides the testbed. See e. g. man autopkgtest-schroot for
details.'''

    parser = argparse.ArgumentParser(
        usage=usage, description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog,
        add_help=False)
    # logging
    g_log = parser.add_argument_group('logging options')
    g_log.add_argument('-o', '--output-dir',
                       help='Write test artifacts (stdout/err, log, debs, etc)'
                       ' to OUTPUT-DIR (must not exist or be empty)')
    g_log.add_argument('-l', '--log-file', dest='logfile',
                       help='Write the log LOGFILE, emptying it beforehand,'
                       ' instead of using OUTPUT-DIR/log')
    g_log.add_argument('--summary-file', dest='summary',
                       help='Write a summary report to SUMMARY, emptying it '
                       'beforehand')
    g_log.add_argument('-q', '--quiet', action='store_const', dest='verbosity',
                       const=0, default=1,
                       help='Suppress all messages from %(prog)s itself '
                       'except for the test results')

    # test bed setup
    g_setup = parser.add_argument_group('test bed setup options')
    g_setup.add_argument('--setup-commands', metavar='COMMANDS_OR_PATH',
                         action='append', default=[],
                         help='Run these commands after opening the testbed '
                         '(e. g. "apt-get update" or adding apt sources); '
                         'can be a string with the commands, or a file '
                         'containing the commands')
    g_setup.add_argument('--setup-commands-boot', metavar='COMMANDS_OR_PATH',
                         action='append', default=[],
                         help='Run these commands after --setup-commands, '
                         'and also every time the testbed is rebooted')
    # ensure that this fails with something other than 100, as apt-get update
    # failures are usually transient
    g_setup.add_argument('-U', '--apt-upgrade', dest='setup_commands',
                         action='append_const',
                         const='(apt-get update || (sleep 15; apt-get update)'
                         ' || (sleep 60; apt-get update) || false)'
                         ' && $(which eatmydata || true) apt-get dist-upgrade -y -o '
                         'Dpkg::Options::="--force-confnew"',
                         help='Run apt update/dist-upgrade before the tests')
    g_setup.add_argument('--apt-pocket', action='append',
                         metavar='POCKETNAME[=pkgname,src:srcname,...]',
                         default=[],
                         help='Enable additional apt source for POCKETNAME. '
                         'If packages are given, set up apt pinning to use '
                         'only those packages from POCKETNAME; src:srcname '
                         ' expands to all binaries of srcname')
    g_setup.add_argument('--copy', metavar='HOSTFILE:TESTBEDFILE',
                         action='append', default=[],
                         help='Copy file or dir from host into testbed after '
                         'opening')
    g_setup.add_argument('--env', metavar='VAR=value',
                         action='append', default=[],
                         help='Set arbitrary environment variable for builds and test')

    # privileges
    g_priv = parser.add_argument_group('user/privilege handling options')
    g_priv.add_argument('-u', '--user',
                        help='run tests as USER (needs root on testbed)')
    g_priv.add_argument('--gain-root', dest='gainroot',
                        help='Command to gain root during package build, '
                        'passed to dpkg-buildpackage -r')

    # debugging
    g_dbg = parser.add_argument_group('debugging options')
    g_dbg.add_argument('-d', '--debug', action='store_const', dest='verbosity',
                       const=2,
                       help='Show lots of internal adt-run debug messages')
    g_dbg.add_argument('-s', '--shell-fail', action='store_true',
                       help='Run a shell in the testbed after any failed '
                       'build or test')
    g_dbg.add_argument('--shell', action='store_true',
                       help='Run a shell in the testbed after every test')

    # timeouts
    g_time = parser.add_argument_group('timeout options')
    for k, v in adt_testbed.timeouts.items():
        g_time.add_argument(
            '--timeout-' + k, type=int, dest='timeout_' + k, metavar='T',
            help='set %s timeout to T seconds (default: %us)' %
            (k, v))
    g_time.add_argument(
        '--timeout-factor', type=float, metavar='FACTOR', default=1.0,
        help='multiply all default timeouts by FACTOR')

    # locale
    g_loc = parser.add_argument_group('locale options')
    g_loc.add_argument('--set-lang', metavar='LANGVAL',
                       help='set LANG on testbed to LANGVAL '
                       '(default: C.UTF-8')

    # misc
    g_misc = parser.add_argument_group('other options')
    g_misc.add_argument(
        '--no-auto-control', dest='auto_control', action='store_false',
        default=True,
        help='Disable automatic test generation with autodep8')
    g_misc.add_argument('--build-parallel', metavar='N',
                        help='Set "parallel=N" DEB_BUILD_OPTION for building '
                        'packages (default: number of available processors)')
    g_misc.add_argument(
        '-h', '--help', action='help', default=argparse.SUPPRESS,
        help='show this help message and exit')

    # first, expand argument files
    file_parser = ArgumentParser(add_help=False)
    arglist = file_parser.parse_known_args(arglist)[1]

    # split off virt-server args
    try:
        sep = arglist.index('---')
        virt_args = arglist[sep + 1:]
        arglist = arglist[:sep]
    except ValueError:
        # still allow --help
        virt_args = None

    # parse options first
    (args, action_args) = parser.parse_known_args(arglist)
    adtlog.verbosity = args.verbosity
    adtlog.debug('Parsed options: %s' % args)
    adtlog.debug('Remaining arguments: %s' % action_args)

    # now turn implicit "bare" args into option args, so that we can parse them
    # with argparse, and split off the virt-server args
    action_args = interpret_implicit_args(parser, action_args)
    adtlog.debug('Interpreted actions: %s' % action_args)
    adtlog.debug('Virt runner arguments: %s' % virt_args)

    if not virt_args:
        parser.error('You must specify --- <virt-server>...')

    if virt_args and '/' not in virt_args[0]:
        # for backwards compat, vserver can be given with "adt-virt-" prefix
        if virt_args[0].startswith('adt-virt-'):
            virt_args[0] = virt_args[0][9:]
        # autopkgtest-virt-* prefix can be skipped
        if not virt_args[0].startswith('autopkgtest-virt-'):
            virt_args[0] = 'autopkgtest-virt-' + virt_args[0]

    action_parser.parse_args(action_args)

    # verify --env validity
    for e in args.env:
        if '=' not in e:
            parser.error('--env must be KEY=value')

    if args.set_lang:
        args.env.append('LANG=' + args.set_lang)

    # set (possibly adjusted) timeout defaults
    for k in adt_testbed.timeouts:
        v = getattr(args, 'timeout_' + k)
        if v is None:
            adt_testbed.timeouts[k] = int(adt_testbed.timeouts[k] * args.timeout_factor)
        else:
            adt_testbed.timeouts[k] = v

    # this timeout is for the virt server, so pass it down via environment
    os.environ['AUTOPKGTEST_VIRT_COPY_TIMEOUT'] = str(adt_testbed.timeouts['copy'])

    if not actions:
        parser.error('You must specify at least one action')

    # if we have --setup-commands and it points to a file, read its contents
    for i, c in enumerate(args.setup_commands):
        # shortcut for shipped scripts
        if '/' not in c:
            shipped = os.path.join('/usr/share/autopkgtest/setup-commands', c)
            if os.path.exists(shipped):
                c = shipped
        if os.path.exists(c):
            with open(c, encoding='UTF-8') as f:
                args.setup_commands[i] = f.read().strip()

    # parse --copy arguments
    copy_pairs = []
    for arg in args.copy:
        try:
            (host, tb) = arg.split(':', 1)
        except ValueError:
            parser.error('--copy argument must be HOSTPATH:TESTBEDPATH: %s'
                         % arg)
        if not os.path.exists(host):
            parser.error('--copy host path %s does not exist' % host)
        copy_pairs.append((host, tb))
    args.copy = copy_pairs

    return (args, actions, virt_args)
