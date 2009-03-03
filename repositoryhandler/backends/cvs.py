# cvs.py
#
# Copyright (C) 2007 Carlos Garcia Campos <carlosgc@gsyc.escet.urjc.es>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os

from repositoryhandler.Command import Command
from repositoryhandler.backends import Repository, RepositoryInvalidWorkingCopy, register_backend
from repositoryhandler.backends.watchers import *

def get_repository_from_path (path):
    # Just in case path is a file
    if os.path.isfile(path):
        path = os.path.dirname (path)
        
    cvsroot = os.path.join (path, 'CVS', 'Root')

    try:
        uri = open (cvsroot, 'r').read ().strip ()
    except IOError:
        raise RepositoryInvalidWorkingCopy ('"%s" does not appear to be a CVS working copy' % path)

    return 'cvs', uri

class CVSRepository (Repository):
    '''CVS Repository'''

    def __init__ (self, uri):
        Repository.__init__ (self, uri, 'cvs')

    def get_uri_for_path (self, path):
        self._check_srcdir (path)

        if os.path.isfile (path):
            path = os.path.dirname (path)

        repository = os.path.join (path, 'CVS', 'Repository')
        
        try:
            rpath = open (repository, 'r').read ().strip ()
        except IOError:
            raise RepositoryInvalidWorkingCopy ('"%s" does not appear to be a CVS working copy' % path)

        return os.path.join (self.uri, rpath)
        
    def _check_srcdir (self, srcuri):
        # srcuri can be a module, directory or file
        if os.path.isfile (srcuri):
            srcdir  = os.path.dirname (srcuri)
        else:
            srcdir = srcuri
                    
        type, uri = get_repository_from_path (srcdir)

        if uri != self.uri:
            raise RepositoryInvalidWorkingCopy ('"%s" does not appear to be a CVS working copy '
                    '(expected %s but got %s)' % (srcdir, self.uri, uri))

    def checkout (self, uri, rootdir, newdir = None, branch = None, rev = None):
        '''Checkout a module or path from repository

        @param uri: Module or path to check out. When using as a path
            it should be relative to the module being the module name
            the root. modulename/path/to/file
        '''
        
        # TODO: In CVS branch and rev are incompatible, we should 
        # raise an exception if both parameters are provided and 
        # use them, it doesn't matter which, when only one is provided.
        if newdir is not None:
            srcdir = os.path.join (rootdir, newdir)
        elif newdir == '.' or uri == '.':
            srcdir = rootdir
        else:
            srcdir = os.path.join (rootdir, uri)
        if os.path.exists (srcdir):
            try:
                self.update (srcdir, rev)
                return
            except RepositoryInvalidWorkingCopy:
                # If srcdir is not a valid working copy,
                # continue with the checkout
                pass

        cmd = ['cvs', '-z3', '-q', '-d', self.uri, 'checkout', '-P']

        if rev is not None:
            cmd.extend (['-r', rev])

        if newdir is not None:
            cmd.extend (['-d', newdir])
        
        cmd.append (uri)
        command = Command (cmd, rootdir)
        self._run_command (command, CHECKOUT)

    def update (self, uri, rev = None):
        self._check_srcdir (uri)

        cmd = ['cvs', '-z3', '-q', '-d', self.uri, 'update', '-P', '-d']

        if rev is not None:
            cmd.extend (['-r', rev])

        if os.path.isfile (uri):
            directory = os.path.dirname (uri)
            cmd.append (os.path.basename (uri))
        else:
            directory = uri
            cmd.append ('.')
            
        command = Command (cmd,directory)
        self._run_command (command, UPDATE)

    def log (self, uri, rev = None, files = None):
        self._check_srcdir (uri)

        cmd = ['cvs', '-z3', '-q', '-d', self.uri, 'log']

        if rev is not None:
            cmd.extend (['-r', rev])

        if os.path.isfile (uri):
            directory = os.path.dirname (uri)
        else:
            directory = uri

        if files is not None:
            for file in files:
                cmd.append (file)
        else:
            cmd.append ('.')

        command = Command (cmd, directory)
        self._run_command (command, LOG)

    def rlog (self, module, rev = None, files = None):
        cmd = ['cvs', '-z3', '-q', '-d', self.uri, 'rlog']

        if rev is not None:
            cmd.extend (['-r', rev])

        if files is not None:
            for file in files:
                cmd.append (os.path.join (module, file))
        else:
            cmd.append (module)

        command = Command (cmd)
        self._run_command (command, LOG)

    def diff (self, uri, branch = None, revs = None, files = None):
        self._check_srcdir (uri)

        cmd = ['cvs', '-z3', '-q', '-d', self.uri, 'diff', '-uN']

        if revs is not None:
            for rev in revs:
                cmd.extend (['-r', rev])

        if os.path.isfile (uri):
            cwd = os.path.dirname (uri)
        else:
            cwd = uri

        if files is not None:
            for file in files:
                cmd.append (file)
        else:
            cmd.append ('.')

        command = Command (cmd, cwd)
        self._run_command (command, DIFF)

    def blame (self, uri, rev = None, files = None):
        # In cvs rev already includes the branch info
        # so no need for a branch parameter
        self._check_srcdir (uri)

        cmd = ['cvs', '-z3', '-q', '-d', self.uri, 'annotate']

        if rev is not None:
            cmd.extend (['-r', rev])

        if os.path.isfile (uri):
            directory = os.path.dirname (uri)
            target = os.path.basename (uri)
        else:
            directory = uri
            target = '.'

        if files is not None:
            for file in files:
                cmd.append (file)
        else:
            cmd.append (target)

        command = Command (cmd, directory)
        self._run_command (command, BLAME)

    def get_modules (self):
        #Not supported by CVS
        return []

    def get_last_revision (self, uri):
        self._check_srcdir (uri)

        if not os.path.isfile (uri):
            return None

        filename = os.path.basename (uri)
        path = os.path.dirname (uri)
        
        cmd = ['cvs', 'status', filename]
        command = Command (cmd, path)
        out = command.run_sync ()

        retval = None
        for line in out.splitlines ():
            if "Working revision:" in line:
                retval = line.split (":", 1)[1].strip ().split ()[0]
            
        return retval

register_backend ('cvs', CVSRepository)

