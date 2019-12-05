Autopkgtest Virtualisation Service Interface
============================================

The virtualisation server provides a single executable program which is
used by the tester core to request virtualisation facilities.

The server has the following states:

Closed
    there is no particular testbed. This is the initial state.

Open
    the testbed is running and can be communicated with (and, if
    applicable, is not being used by any other concurrent test run)

Note that these are the states of the server, in the tester core to
server protocol. The actual testbed will probably have more states,
including for example Closed, Open (and therefore busy), Modified,
Broken, etc. Ideally the virtualisation server will prevent multiple
concurrent uses of the same testbed; the tester core is allowed to
assume that either its caller or the virtualisation server will ensure
that it has exclusive use of the testbed.

The server program speaks a protocol on its stdin/stdout. The protocol
is line-based. In the future other ways of invoking the server may be
defined; the current server should of course reject such invocations.

Initial response from virtualization server after starting is ``ok``.
This response is also the response from any of the commands listed
below, unless otherwise specified.

Command: capabilities
---------------------

Response, for example:

::

    ok gnomovision-server revert ...

where the words after ``ok`` are features that not all servers support.
Valid in all states.

Currently defined capabilities:

revert
    The ``revert`` command is supported. The base semantics are that the
    following aspects of the testbed are reverted:

    - the set of installed packages
    - the contents of the root filesystem, BUT
    - *not* the contents of ``/home``
    - *not* the contents of ``/tmp``
    - *not* the set of running processes

    The testbed will actually revert when it is closed. If this feature
    is not mentioned then changes to the testbed are persistent (so
    destructive tests should not be performed).

revert-full-system
    The ``revert`` and ``close`` commands will completely revert the
    testbed to the state after ``open``. This reversion is done with
    some kind of virtualisation, and includes (without limitation) the
    contents of all the testbed filesystems, its running processes,
    network configuration, etc.

reboot
    The testbed supports (re)booting, to pick up updated kernels and/or
    init system scripts from ``--setup-commands``, or from explicit
    reboot requests from tests.

root-on-testbed
    Commands run through ``print-execute-command`` will be run as root
    on the testbed, and copyup/copydown will have full access to the
    filesystem. Unless this capability is advertised, root access is not
    (or may not be) available.

suggested-normal-user=\ *username*
    The caller is advised that *username* would be a good user to use
    for running tests (and doing other operations) when root is not
    required. The advertised account will exist on the testbed already.
    Several ``suggested-normal-user=`` capabilities (with distinct user
    names) may be advertised in which case more than one such user is
    available.

downtmp-host=\ *path*
    If the testbed has the ability of setting up a shared directory with
    the host, this gives the host directory path of the "downtmp"
    directory as reported by the virt server's ``hook_downtmp()``
    function. This makes copying files in and out much more efficient.

isolation-container
    The testbed runs in a Linux cgroup/container (nspawn, LXC, docker,
    etc.) and thus tests have full control over starting services and
    opening network ports.

isolation-machine
    The testbed runs in a complete (virtual or real) machine on its own
    (qemu or bare metal) and thus tests have full control over starting
    services, opening network ports, interacting with the kernel (e. g.
    modprobe), rebooting, and accessing hardware.

Command: open
-------------

Response:

::

    ok testbed-scratchspace

State: Closed to Open

Checks that the testbed is present and reserves it (waiting for other
uses of the testbed to finish first, if necessary).
``testbed-scratchspace`` is a pathname on the testbed which can be used
freely by the test scripts and which is valid until the next ``close``,
``revert``, or ``quit``.

Command: revert
---------------

Response:

::

    ok testbed-scratchspace

State: Open, remains Open

Restores the testbed, undoing all of the changes made so far. Only
available if the ``revert`` capability is advertised. If possible, the
testbed's set of running processes will also be restored to the initial
state.

Command: reboot
---------------

Response:

::

    ok testbed-scratchspace

State: Open, remains Open

Reboots the testbed, without reverting any changes to the files. Only
available if the ``reboot`` capability is advertised.

Command: close
--------------

Response:

::

    ok

State: Open to Closed

Stops the testbed and undoes filesystem changes (if ``revert`` is
advertised).

Command: print-execute-command
------------------------------

Response:

::

    ok program,arg,arg... [keyword-info ...]

Prints a command that can be executed by the caller to run a command on
the testbed.

The program has the following properties:

-  The caller is expected to url-decode ``program`` and each ``arg``,
   append the command to be run on the testbed, and call ``execve()`` on
   the resulting argv list.
-  That command might need to convert the argument list into a shell
   string with appropriate quoting if it implements the execute command
   with programs that take shell commands instead of argv lists, like
   ssh.
-  The testbed program's stdin, stdout and stderr will be plumbed
   through to the stdin, stdout and stderr passed to ``program``; this
   may involve fd passing, or indirection via pipes or sockets. The
   testbed program may not assume that the descriptors it receives are
   seekable even if the originals are.
-  It is not defined whether other file descriptors, environment
   variables, and process properties in general, are inherited by the
   testbed command.
-  ``program`` may exit as soon as the testbed command does, or it may
   wait until every copy of the stdout and stderr descriptors passed to
   the testbed command have been closed on the testbed.
-  ``program``'s exit status will be that of the testbed command if the
   latter exits with a value from 0..125. If the testbed command dies
   due to a signal, then either (i) ``program`` will exit with the
   signal number with 128 added, or (ii) ``program`` will die with the
   same signal (although it may fail to dump core even if the testbed
   program did), or (iii) ``program`` will fail. If ``program`` fails it
   will exit 254 or 255; of course ``program`` may die to a some signals
   other than because the testbed program died with the same signal.
-  The caller may run several of these at once, subject to limitation of
   resources (e. g. file descriptors or processes)
-  The behaviour if a command is running when the testbed is closed or
   reverted is not defined. However, if the testbed advertises
   ``revert`` then after the testbed is closed or reverted any such
   ``program`` invocation will not have any further effect on the
   testbed.
-  Sending ``program`` signals in an attempt to terminate it may not
   terminate all of the relevant processes and may not have any effect
   on the testbed.
-  The behaviour if no testbed command is specified (i. e., if just the
   specified ``program`` and ``arg``\ s is passed to exec) is not
   defined.
-  Currently no ``keyword-info``\ s are defined; they work the same way
   as capabilities in that unrecognised ones should be ignored by the
   caller.

The response is only valid between ``open`` and the next subsequent
``close``, ``revert`` or ``quit``. Using it at other times has undefined
behaviour.

Commands: copyup/copydown
-------------------------

Command:

::

    copydown host-path testbed-path
    copyup testbed-path host-path

Response:

::

    ok

Either

1. Both paths end in ``/``, in which case the source must be an existing
   directory.

2. Neither path ends in ``/``, in which case the source must be an
   existing file.

Both filenames are URL-encoded.

Command: quit
-------------

Reponse:

::

    ok

The server exits with status 0, after closing the testbed if applicable.

Command: shell
--------------

Response: one of

::

    ok
    not supported by virt server

Runs a shell in the testbed (as root, if available), while the testbed
is open. This is intended for interactively debugging problems with
tests. The virt server has to provide a ``hook_shell()`` function for
this, otherwise this command is not supported.

On any error including signals to the server or EOF on stdin the testbed
is unreserved and restored to its original state (ie, closed), and the
server will print a message to stderr (unless it is dying with a
signal).

..  vim: ft=rst tw=72


