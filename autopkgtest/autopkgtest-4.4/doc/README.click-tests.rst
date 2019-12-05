Autopkgtest - Defining tests for Click packages
===============================================

This document describes how autopkgtest interprets and executes
tests found in
`Click packages <https://click.readthedocs.org/en/latest/>`_.

Overview
--------

A click package's manifest defines tests and their metadata in the
"x-test" dictionary. Each entry's key is the test name, and the value is
a test executable or a dictionary that specifies the test command,
dependencies, and restrictions. For example, a manifest might look like
this:

::

    {
        "name": "testclick",
        "title": "autopkgtest test click app",
        [... other manifest entries ...]
        "x-test": {
            "test1": "tests/simple",

            "test2": {
                "path": "tests/test-ui",
                "depends": ["ubuntu-ui-toolkit-autopilot"],
                "restrictions": ["allow-stderr"],
            },

            "test3": {
                "command": "echo hello"
            }
        }
        "x-source": {
            "vcs-bzr": "lp:testclick-app"
        }
    }

The complete manifest usually gets generated during building and thus is
read from the .click binary package. However, the tests are run from the
click package *source* as usually they are not shipped in the binary.
If the manifest has an ``x-source`` key with a ``vcs-bzr`` link (the
only supported VCS at the moment), autopkgtest will check out that
branch and run the tests from it; Otherwise you have to specify the
click source directory and the built .click binary package (in that
order) to ``autopkgtest``.

The tests are run with the corresponding click package being installed
into the virtualization server. Note that this may fail if the testbed
does not have "click" itself or the click package's requested framework
installed.

The cwd of each test is guaranteed to be the root of the click source
package, which will have been unpacked but not built. *However* note
that the tests must test the *installed* version of the click package.
Tests may not modify the source tree (and may not have write access to
it).

During execution of the test, the environment variable
``$AUTOPKGTEST_TMP`` will point to a directory for the execution of this
particular test, which starts empty and will be deleted afterwards (so
there is no need for the test to clean up files left there).

If tests want to create artifacts which are useful to attach to test
results, such as additional log files or screenshots, they can put them
into the directory specified by the ``$AUTOPKGTEST_ARTIFACTS``
environment variable. When using the ``--output-dir`` option, they will
be copied into ``outputdir/artifacts/``.

Control fields
--------------

The test fields which may appear in each test definition dictionary are:

path
    (string) Specifies a path to an executable relative to the click
    source tree which runs the test.

command
    (string) Shell command which is passed verbatim to bash

autopilot_module
    (string) Python module name in ``app/tests/autopilot`` or
    ``tests/autopilot`` which is an Autopilot test. See below for details.

*Exactly one* of ``path``, ``command``, or ``autopilot_module`` must be
given for each test. All other fields below are optional, and assumed to
be empty lists of not present.

depends
    (list of strings) Debian package dependencies. Every list entry is a
    single package name or ``|``-separated alternatives, and may contain
    the usual Debian version and/or architecture restrictions. Note that
    with testbeds which are system image based you cannot install
    additional Debian packages, so for these this can merely ensure that
    the test dependencies are already installed.

restrictions
    (list of strings) List of test restrictions as defined in
    README.package-tests.rst.

features
    (list of strings) List of test features as defined in
    README.package-tests.rst.

classes
    (list of strings) List of test class names, see
    README.package-tests.rst.

Simple test specification
-------------------------

If a test does not need any additional dependencies, restrictions etc.,
and just consists of a path to an executable, it can be specified as

::

    "testname": "tests/testscript"

which is equivalent to

::

    "testname": {
        "path": "tests/testscript"
    }

Autopilot tests
---------------
For autopilot tests you can use the ``autopilot_module`` test field,
which will be interpreted as a Python module name under
``app/tests/autopilot`` or ``tests/autopilot``. An appropriate test
command and default dependencies are automatically provided. Thus a test
description

::

    "testname": {
        "autopilot_module": "foo_tests",
        "depends": ["python3-dateutil"],
        "restrictions": ["allow-stderr"]
    }

expands to

::

    "testname": {
        "command": "PYTHONPATH=app/tests/autopilot:tests/autopilot:$PYTHONPATH python3 -m autopilot.run run foo_tests",
        "depends": ["ubuntu-ui-toolkit-autopilot", "autopilot-touch", "python3-dateutil"],
        "restrictions": ["allow-stderr"]
    }

As a special case, if the test name is "autopilot" and the value is a single
identifier, it is interpreted as an ``autopilot_module``. Thus the
description

::

    "autopilot": "foo_tests"

is equivalent to

::

    "autopilot": {
        "autopilot_module": "foo_tests"
    }

which further expands to a complete description like above.

..  vim: ft=rst tw=72
