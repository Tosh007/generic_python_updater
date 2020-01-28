import sys, os, yaml
import urllib.request
import simplejson as json
import yaml
import collections
import traceback
import config

# possible update situations:
# for files:
# 1) new file on repo, not yet existing offline -> localsha is None -> download and write file to path
# 2) file deleted from repo, still existing offline -> sha is None -> delete file at path
# 3) file updated on repo, offline is outdated -> sha != localsha -> download and write file to path
# 4) nothing happened since last update -> sha==localsha -> pass
# for dir, only #1 and #2 are relevant.

def loadJsonFromUrl(url):
    f = urllib.request.urlopen(url)
    d = f.read()
    f.close()
    data = d.decode("utf-8")
    return json.loads(data)

class Node:
    _nodes = {}
    def __init__(self, name, path, download_url, sha, type):
        self.name=name
        self.type=type
        self.path=path
        self.url=download_url
        self.sha=sha
        self.localsha=None
        self._nodes[path]=self
        if type=="dir":
            url = config.repo_url+path
            print("dir found: "+path)
            urlsToCheck.append(url)
        elif type=="file":
            print("file found: "+path)
    def __str__(self):
        s=""
        for i in "name","type","path","url","sha":
            s+=i+": "+self.__dict__[i]+"\n"
        return s
    def __eq__(self,other):
        return self.path==other.path
    def __hash__(self):
        return hash(self.path)

    @staticmethod
    def fromDict(d):
        #extract required args with defaults
        data = {"sha":None,"name":None,"download_url":None,"type":None,"path":None}
        for key in d.keys():
            if key in data.keys():
                data[key] = d[key]
        if data["type"] == "dir":
            data["sha"]="dir"
        return Node(**data)
    @staticmethod
    def ReadLocalMetaData(f):
        for line in f:
            line=line.split("|")
            path = line[0]
            sha = line[1]
            t = line[2].strip()
            try:
                Node._nodes[path].localsha = sha
            except KeyError:
                # the node does not exist online anymore
                yield Node(path.split("/")[-1],path,None,None,t)
    @staticmethod
    def WriteLocalMetaData(f):
        for path in Node._nodes:
            n = Node._nodes[path]
            if n.localsha is None:continue
            f.write(path+"|"+n.localsha+"|"+n.type+"\n")
    @staticmethod
    def updateCache(s):
        Node._nodes = {}
        for n in s:
            Node._nodes[n.path] = n
    @staticmethod
    def sortByPathDepth(obj):
        return obj.path.count("/")
    def update(self):
        if self.type=="dir" and self.localsha is None:
            os.mkdir(config.program_path+self.path)
            self.localsha = "dir"
        elif (self.sha != self.localsha):   # first establish folder structure then update files, update from github
            print("downloading file: "+self.name+" from url "+self.url)
            f = urllib.request.urlopen(self.url)
            d = f.read()
            f.close()
            f = open(os.path.join(config.program_path,self.path),"wb")
            f.write(d)
            f.close()
            self.localsha = self.sha


try:
    if input("check for updates? (y/N)") == "y":
        if (not os.path.exists(config.program_path)):
            os.mkdir(config.program_path)
        nodes = set()
        urlsToCheck = collections.deque()
        urlsToCheck.append(config.repo_url)
        onlineNodes=set()
        # load file/hash list from repo
        while len(urlsToCheck)!=0:
            url = urlsToCheck.popleft()
            jd = loadJsonFromUrl(url)
            newNodes = set()
            for meta in jd:
                onlineNodes|=set((Node.fromDict(meta),))
            nodes |=onlineNodes
        # load path / hash list from local file
        if not os.path.exists(config.shacachename):
            f=open(config.shacachename,"w")
            f.close()
        f = open(config.shacachename)
        nodesToDelete = set(Node.ReadLocalMetaData(f)) # files that are no longer on repo (deleted) but still there locally
        f.close()
        print("-"*30)
        print("loading complete")
        print("nodes to delete: "+str(len(nodesToDelete)))
        for n in nodesToDelete:
            try:
                print("path")
                os.shutil.rmtree(os.path.join(config.program_path,n.path),True)
                n.localsha = None
            except BaseException as e:
                print(e)
        print("nodes to update: "+str(len(nodes)))
        Node.updateCache(nodes) # ignore all nodes that were deleted in last step
        l = list(nodes)
        l.sort(key=Node.sortByPathDepth)
        for n in l:
            n.update()
        print("writing local metadata file")
        f=open(config.shacachename,"w")
        Node.WriteLocalMetaData(f)
        f.close()
        print("update complete")
        input("press enter to continue")
    sys.path.append(os.path.abspath(config.program_path))
except SystemExit:pass
except BaseException as e:
    print("ERROR:")
    traceback.print_tb(e.__traceback__)
    print(e)
    input("press enter to close")
