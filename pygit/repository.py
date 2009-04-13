import re
import os
import subprocess

from . import branch
from . import commit
from . import exceptions
from . import ref
from .utils import quote_for_shell

class Repository(object):
    def getBranches(self):
        raise NotImplementedError()
    ############################# internal methods #############################
    def _getWorkingDirectory(self):
        return '.'
    def _executeGitCommand(self, command, cwd=None):
        if cwd is None:
            cwd = self._getWorkingDirectory()
        returned = subprocess.Popen(command,
                                    shell=True,
                                    cwd=cwd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        returned.wait()
        return returned
    def _executeGitCommandAssertSuccess(self, command, **kwargs):
        returned = self._executeGitCommand(command, **kwargs)
        assert returned.returncode is not None
        if returned.returncode != 0:
            raise exceptions.GitCommandFailedException(command, returned)
        return returned
    def _getOutputAssertSuccess(self, command, **kwargs):
        return self._executeGitCommandAssertSuccess(command, **kwargs).stdout.read()

############################## remote repositories #############################
class RemoteRepository(Repository):
    def __init__(self, url):
        super(RemoteRepository, self).__init__()
        self.url = url
    def getRefs(self):
        output = self._executeGitCommandAssertSuccess("git ls-remote %s" % (self.url,))
        for output_line in output.stdout:
            commit, refname = output_line.split()
            for prefix, cls in [('refs/heads/', branch.Branch),
                                ('refs/tags/', None),
                                ('refs/remotes/', None),
                                ('', ref.Ref)]:
                if refname.startswith(prefix):
                    if cls is not None:
                        yield cls(self, refname[len(prefix):])
                    break
    def getBranches(self):
        return [ref for ref in self.getRefs()
                if isinstance(ref, branch.Branch)]

############################## local repositories ##############################
class LocalRepository(Repository):
    def __init__(self, path):
        super(LocalRepository, self).__init__()
        self.path = path
    def _getWorkingDirectory(self):
        return self.path
    def _getCommitByRefName(self, name):
        return commit.Commit(self, self._getOutputAssertSuccess("git rev-parse %s" % name).strip())
    def _getCommitByPartialHash(self, sha):
        return self._getCommitByRefName(sha)
    ########################### Initializing a repository ##########################
    def init(self, bare=False):
        if not os.path.exists(self.path):
            os.mkdir(self.path)
        if not os.path.isdir(self.path):
            raise exceptions.GitException("Cannot create repository in %s - "
                               "not a directory" % self.path)
        self._executeGitCommandAssertSuccess("git init %s" % ("--bare" if bare else ""))
    def _asURL(self, repo):
        if isinstance(repo, LocalRepository):
            repo = repo.path
        elif isinstance(repo, RemoteRepository):
            repo = repo.url
        elif not isinstance(repo, basestring):
            raise TypeError("Cannot clone from %r" % (repo,))
        return repo
    def clone(self, repo):
        self._executeGitCommandAssertSuccess("git clone %s %s" % (self._asURL(repo), self.path), cwd=".")
    ########################### Querying repository refs ###########################
    def getBranches(self):
        for branch_name in self._executeGitCommandAssertSuccess("git branch").stdout:
            branch_name = strip()
            if branch_name.startswith("*"):
                brach_name = brach_name[1:]
            yield branch.Branch(self, brach_name.strip())
    def getRefs(self):
        raise NotImplementedError()
    ################################ Querying Status ###############################
    def containsCommit(self, commit):
        try:
            self._getCommitByRefName(commit)
        except exceptions.GitException:
            return False
        return True
    def getHead(self):
        return self._getCommitByRefName("HEAD")
    def _getFiles(self, *flags):
        flags = ["--exclude-standard"] + list(flags)
        return [f.strip()
                for f in self._getOutputAssertSuccess("git ls-files %s" % (" ".join(flags))).splitlines()]
    def getStagedFiles(self):
        return self._getFiles("--cached")
    def getUnchangedFiles(self):
        return self._getFiles()
    def getUntrackedFiles(self):
        return self._getFiles("--others")
    def __contains__(self, thing):
        if isinstance(thing, basestring) or isinstance(thing, commit.Commit):
            return self.containsCommit(thing)
        raise NotImplementedError()
    ################################ Staging content ###############################
    def add(self, path):
        self._executeGitCommandAssertSuccess("git add %s" % quote_for_shell(path))
    def addAll(self):
        return self.add('.')
    ################################## Committing ##################################
    def _deduceNewCommitFromCommitOutput(self, output):
        for pattern in [
            # new-style commit pattern
            r"^\[\S+\s+(?:\(root-commit\)\s+)?(\S+)\]",
                        ]:
            match = re.search(pattern, output)
            if match:
                return commit.Commit(self, match.group(1))
        return None
    def commit(self, message):
        output = self._getOutputAssertSuccess("git commit -m %s" % quote_for_shell(message))
        return self._deduceNewCommitFromCommitOutput(output)
    ################################ Changing state ################################
    def _reset(self, thing, flag=None):
        if isinstance(thing, ref.Ref):
            thing = thing.name
        if flag is None:
            flag = ""
        else:
            flag = "--%s" % flag
        self._executeGitCommandAssertSuccess("git reset %s %s" % (flag, thing))
    def resetSoft(self, thing):
        return self._reset(thing, "soft")
    def resetHard(self, thing):
        return self._reset(thing, "hard")
    def resetMixed(self, thing):
        return self._reset(thing, "mixed")
    ################################# collaboration ################################
    def fetch(self, repo=None):
        command = "git fetch"
        if repo is not None:
            command += " "
            command += self._asURL(repo)
        self._executeGitCommandAssertSuccess(command)
    def pull(self, repo=None):
        command = "git pull"
        if repo is not None:
            command += " "
            command += self._asURL(repo)
        self._executeGitCommandAssertSuccess(command)
