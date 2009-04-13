class Ref(object):
    def __init__(self, repo, name):
        super(Ref, self).__init__()
        self.repo = repo
        self.name = name
    def getCommits(self):
        commit = self.repo._getCommitByRefName(self.name)
    def __repr__(self):
        return "%s@%s" % (self.repo, self.name)
