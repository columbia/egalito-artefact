Autopkgtest - Running tests
===========================

This document gives an overview how to run tests with autopkgtest. It
does not cover each detail, please consult the individual manpages like
autopkgtest(1), autopkgtest-schroot(1), etc. for all available options.

Ingredients for Debian packages:

-  A source package which defines tests in ``debian/tests/``. See
   README.package-tests for how to define them.

   There are plenty of existing package tests in Debian/Ubuntu which you
   can use as examples and inspiration, just look for a source package
   with a ``Testsuite: autopkgtest`` header, or the automatic test
   running services `in Debian <http://ci.debian.net/>`_ and
   `Ubuntu <http://autopkgtest.ubuntu.com>`_.

-  A location for the source/tests: This can be a local source tree, a
   local .dsc, or "download with apt-get source".

-  Optionally some pre-built binary packages which should be tested.

Ingredients for Click packages:

- A binary .click package (local ``*.click`` file or already installed)
  whose manifest specifies tests and their metadata. See
  README.click-tests.rst for details.

- The corresponding click source package which contains the tests
  defined in the manifest.

Finally you need a virtualization server, which creates the environment
in which the test runs.  Depending on how intrusive the test is this can
provide various degrees of isolation, from "run on my local system"
(fastest, but unsafe) to "run in a temporary virtual machine" (slowest,
but highest possible isolation). These are described in detail below.

autopkgtest
-----------
The ``autopkgtest`` program is the main program to run tests which gets all
these ingredients as arguments, in the following form:

::

    autopkgtest [options] <source package> [<binary package> ...] -- <virt-server> [<virt-server options>]

Specifying tests and packages
-----------------------------

All possible options are explained in the autopkgtest(1) manpage. This
section shows the most common scenarios, with using "mysrc" as source
package name. Note that specifying the virtualization server and its
options is handled in the following section, and it is independent of
specifying tests and packages, so it is merely abbreviated as
*virt-server* here.

-  Run tests from the Debian source package in the distribution. This
   calls ``apt-get source mysrc`` in the virt-server, thus will use
   whichever distribution/release that ``/etc/apt/sources.list``
   configures:

   ``autopkgtest mysrc --`` *virt-server*

-  Run tests from a local source tree, using the binary packages
   from the distribution. This is useful if you are creating or fixing
   tests, but the actual binary packages are fine:

   ``autopkgtest -B packages/mysrc --`` *virt-server*

   If the source tree is already built, then tests which declare the
   ``build-needed`` restriction (see README.package-tests) don't need to
   re-build the source in the virt-server.

-  Build a local source package in the virt-server, then run its tests
   against the built binaries. This is useful if you need to fix a bug
   in the actual packages to make the tests succeed:

   ``autopkgtest packages/mysrc --`` *virt-server*

-  Same as above, but with specifying a built source package instead of
   a source tree:

   ``autopkgtest packages/mysrc_*.dsc --`` *virt-server*

-  Test new built binaries with a new source and avoid rebuilding them
   in virt-server. This is useful if you e. g. update a package to a new
   version and now want to check whether its tests still succeed:

   ``autopkgtest -B packages/*.deb packages/mysrc_*.dsc --`` *virt-server*

-  The previous case can be simplified if you have a binary .changes
   from a previous build:

   ``autopkgtest packages/*.changes --`` *virt-server*

-  Run tests for a locally built click package:

   ``autopkgtest myclickapp/ myclickapp_0.1_all.click --`` *virt-server*

   Note that for this you need to specify a virt-server which has
   "click" itself and the click app's required framework already
   installed. To run this on an actual Ubuntu phone, you can use the SSH
   testbed server:

   ::

     autopkgtest ubuntu-calculator-app/ com.ubuntu.calculator_1.3.283_all.click -- ssh -s adb

   (This is using the shipped ``adb`` setup script in
   ``/usr/share/autopkgtest/ssh-setup/``.)

   If you aren't running the test on an Ubuntu touch device, you can
   approximate the environment in a normal schroot/LXC/QEMU testbed with
   the ``--setup-commands`` scripts that autopkgtest provides (note that
   you do not need to specify the full
   ``/usr/share/autopkgtest/setup-commands/`` path for shipped scripts):

   ::

     autopkgtest --setup-commands ubuntu-touch-session \
             --setup-commands ro-apt \
             myclickapp/ myclickapp_0.1_all.click -- lxc autopkgtest-xenial

   See the comments in the setup-commands scripts for details.

- Run tests for an already installed click package:

   ``autopkgtest --installed-click=com.example.myapp --`` *virt-server*

  This will work for click apps which have an ``x-source/vcs-bzr`` entry
  in their manifest. If that's not the case, you will need to explicitly
  specify the click source directory as above.

Output
------

Unless you specify some options, autopkgtest just writes the logging, test
outputs, and test results to stdout/stderr and exits with code 0 on
success, or some non-zero code if there were skipped or failed tests or
problems with the virt-server. (See autopkgtest(1) for defined codes).

For getting output files you have three choices:

-  If you just want the "testname: PASS/FAIL" results, use

   ``--summary-file=/path/to/summary.txt``.

-  If you want the complete output of autopkgtest in a file, use

   ``-l /path/to/test.log`` (or the long option ``--log-file``)

-  If you want the log file, the individual test stdout and stderr
   output, and built binaries (if any) in a directory, use

   ``-o /path/to/test-output/`` (or the long option ``--output-dir``).

You can also combine these.

Virtualization server
---------------------

schroot
~~~~~~~
::

    autopkgtest ... -- schroot schroot-name

Run tests in the specified schroot. You can use mk-sbuild(1) to
conveniently create schroots, and run this as normal user if you
configured schroot accordingly.

This server is the fastest available that provides "proper" file system
isolation and revert, but it does not provide enough isolation for tests
that need to start services, reconfigure the network, or open TCP ports
which are already open at the host. If your test does not need to do
these things this is the recommended server, as schroots are also useful
for other tasks like building packages with sbuild.

See autopkgtest-schroot(1) manpage.

LXC
~~~
::

    autopkgtest ... -- lxc container-name

Run tests in the specified LXC container. Containers provide full
service and network isolation, but tests or packages cannot change the
kernel or hardware configuration. If your test does not need that, this
is the recommended server as it is faster than QEMU and works on all
Linux architectures.

``container-name`` will be cloned or be called with a temporary overlay
file system if you specify the ``-e`` (``--ephemeral``) option, thus it
will never be modified and you can run several tests in parallel safely.
Unless your test or architecture or RAM availability doesn't work with
overlayfs, using -e is highly recommended for better performance.

If your user can get root privileges with sudo, you can call autopkgtest as
your normal user and specify ``-s`` (``--sudo``) so that the container
can be started as root.

See autopkgtest-virt-lxc(1) manpage. This also explains how to build containers.

QEMU
~~~~
::

    autopkgtest ... -- qemu path/to/image

Run tests with QEMU/KVM using the specified image. The image will be run
with a temporary overlay file system, thus it will never be modified and
you can run several tests in parallel safely.

If your test needs a full machine including kernel/hardware access, this
is the recommended runner; it provides complete system isolation, revert
and breaks-testbed capabilities. But it is also the one with the biggest
overhead and only works well on architectures with KVM acceleration (i.
e. mostly x86).

See autopkgtest-virt-qemu(1) manpage. This also explains how to build suitable
images, and the requirements of the guest.

null
~~~~
::

    autopkgtest ... -- null

This does not do any virtualization, but runs tests straight on the
host. Beware that this will leave some clutter on your system (installed
test or build dependency packages, configuration changes that the tests
might make, etc.). It is not able to run tests with the "breaks-testbed"
restriction. See autopkgtest-virt-null(1) manpage.

chroot
~~~~~~
::

    autopkgtest ... -- chroot /path/to/chroot

Run tests in the specified chroot. You need to call autopkgtest as root for
this. There is no automatic cleanup or revert for the chroot, so unless
you can provide this by some other means, don't use this.

ssh
~~~
::

    autopkgtest ... -- ssh -l joe -H testhost.example.com

This is a generic runner for an externally set up testbed which assumes
nothing else than a working ssh connection. This can call a "setup
script" to create/configure a testbed (such as spinning up a cloud VM
with nova or setting up SSH on a phone through ADB). See the manpage for
details. autopkgtest ships setup scripts for an adb host (mostly for
Ubuntu Touch), for nova (for cloud instances) and for MaaS
currently; see their comment headers in
``/usr/share/autopkgtest/ssh-setup/``.

..  vim: ft=rst tw=72
