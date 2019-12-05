'''Provide a fake package archive for testing'''

# (C) 2012-2015 Martin Pitt <martin.pitt@ubuntu.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import tempfile
import shutil
import os
import subprocess
import atexit


class Archive:
    def __init__(self, path=None, pooldir='pool', series=None, component=None):
        '''Construct a local package test archive.

        If series and component are given, Packages.gz will be placed into
        'dists/series/component/binary-<arch>/'.  By default it is created in
        the root of the temporary directory, so that the apt source will just
        use '/' for the suite and no components.

        The archive is initially empty. You can create new packages with
        create_deb(). self.path contains the path of the archive, and
        self.apt_source provides an apt source "deb" line.

        If path is None (default), it is kept in a temporary directory which
        gets removed when the Archive object gets deleted. Otherwise the given
        path is used, which is useful for creating multiple series/components;
        then you should use a different pooldir.
        '''
        if path:
            self.path = path
        else:
            self.path = tempfile.mkdtemp(prefix='testarchive.')
            atexit.register(shutil.rmtree, self.path)
        self.pooldir = pooldir

        arch = subprocess.check_output(['dpkg', '--print-architecture'],
                                       universal_newlines=True).strip()
        self.series = series
        self.component = component
        if series:
            assert component, 'must specify both series and component'
            self.index_dir = os.path.join(
                'dists', series, component, 'binary-' + arch)
            os.makedirs(os.path.join(self.path, self.index_dir))
            self.apt_source = 'deb [trusted=yes arch=%s] file://%s %s %s' % \
                (arch, self.path, series, component)
        else:
            assert component is None, 'must specify both series and component'
            self.apt_source = 'deb [trusted=yes arch=%s] file://%s /' % \
                (arch, self.path)
            self.index_dir = ''

    def create_deb(self, name, version='1', architecture='all',
                   dependencies={}, description='test package', extra_tags={},
                   files={}, component='main', srcpkg=None, update_index=True):
        '''Build a deb package and add it to the archive.

        The only mandatory argument is the package name. You can additionally
        specify the package version (default '1'), architecture (default
        'all'), a dictionary with dependencies (empty by default; for example
        {'Depends': 'foo, bar', 'Conflicts: baz'}, a short description
        (default: 'test package'), and arbitrary extra tags.

        By default the package is empty. It can get files by specifying a
        path -> contents dictionary in 'files'. Paths must be relative.
        Example: files={'etc/foo.conf': 'enable=true'}

        The newly created deb automatically gets added to the "Packages" index,
        unless update_index is False.

        Return the path to the newly created deb package, in case you only need
        the deb itself, not the archive.
        '''
        d = tempfile.mkdtemp()
        os.mkdir(os.path.join(d, 'DEBIAN'))
        with open(os.path.join(d, 'DEBIAN', 'control'), 'w') as f:
            f.write('''Package: %s
Maintainer: Test User <test@example.com>
Version: %s
Priority: optional
Section: devel
Architecture: %s
''' % (name, version, architecture))

            if srcpkg:
                f.write('Source: %s\n' % srcpkg)

            for k, v in dependencies.items():
                f.write('%s: %s\n' % (k, v))

            f.write('''Description: %s
 Test dummy package.
''' % description)

            for k, v in extra_tags.items():
                f.write('%s: %s\n' % (k, v))

        for path, contents in files.items():
            if type(contents) == bytes:
                mode = 'wb'
            else:
                mode = 'w'
            pathdir = os.path.join(d, os.path.dirname(path))
            if not os.path.isdir(pathdir):
                os.makedirs(pathdir)
            with open(os.path.join(d, path), mode) as f:
                f.write(contents)

        if srcpkg is None:
            srcpkg = name
        if srcpkg.startswith('lib'):
            prefix = srcpkg[:4]
        else:
            prefix = srcpkg[0]
        dir = os.path.join(self.path, self.pooldir, component, prefix, srcpkg)
        if not os.path.isdir(dir):
            os.makedirs(dir)

        debpath = os.path.join(dir, '%s_%s_%s.deb' % (name, version,
                                                      architecture))
        subprocess.check_call(['dpkg', '-b', d, debpath],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        shutil.rmtree(d)
        assert os.path.exists(debpath)

        if update_index:
            self.update_index()

        return debpath

    def add_sources(self, name, binaries, version='1'):
        '''Add source package entry to the Sources index'''

        if self.index_dir:
            srcindex_dir = os.path.join(self.path,
                                        os.path.dirname(self.index_dir),
                                        'source')
        else:
            srcindex_dir = self.index_dir
        if not os.path.isdir(srcindex_dir):
            os.makedirs(srcindex_dir)

        if name.startswith('lib'):
            prefix = name[:4]
        else:
            prefix = name[0]

        with open(os.path.join(srcindex_dir, 'Sources'), 'a') as f:
            f.write('''Package: %s
Binary: %s
Version: %s
Priority: optional
Architecture: any
Format: 1.0
Directory: %s
Package-List:
''' % (name, ', '.join(binaries), version, os.path.join(self.pooldir, self.component, prefix, name)))
            for b in binaries:
                f.write(' %s deb admin optional\n' % b)
            f.write('Standards-Version: 1.0\n\n')

    def update_index(self):
        '''Update the Packages index and Release file.

        This usually gets done automatically by create_deb(), but needs to be
        done if you manually copy debs into the archive or call create_deb with
        update_index==False.
        '''
        old_cwd = os.getcwd()
        try:
            os.chdir(self.path)
            with open(os.path.join(self.index_dir, 'Packages'), 'wb') as f:
                subprocess.check_call(['apt-ftparchive', 'packages',
                                       self.pooldir], stdout=f)
            if self.series:
                rp = os.path.join(self.path, 'dists', self.series, 'Release')
                try:
                    os.unlink(rp)
                except OSError:
                    pass
                release = subprocess.check_output(
                    ['apt-ftparchive', 'release', '-o',
                     'APT::FTPArchive::Release::Suite=' + self.series,
                     os.path.dirname(rp)])
                with open(rp, 'wb') as f:
                    f.write(release)
        finally:
            os.chdir(old_cwd)


if __name__ == '__main__':
    r = Archive(series='testy', component='main')
    r.create_deb('vanilla')
    r.create_deb('libvanilla0', srcpkg='vanilla')
    r.create_deb('chocolate', dependencies={'Depends': 'vanilla'})
    print(r.apt_source)
    r.add_sources('vanilla', ['vanilla', 'libvanilla0'])

    p = Archive(path=r.path, pooldir='pool-proposed', series='testy-proposed',
                component='main')
    p.create_deb('vanilla', '2')
    r.create_deb('libvanilla0', '2', srcpkg='vanilla')
    p.create_deb('chocolate', '2', dependencies={'Depends': 'vanilla (>= 2)'})
    print(p.apt_source)
    p.add_sources('vanilla', ['vanilla', 'libvanilla0'], '2')

    subprocess.call(['bash', '-i'], cwd=r.path)
