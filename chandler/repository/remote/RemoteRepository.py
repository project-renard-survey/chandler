
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2002 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"


from repository.persistence.XMLRepository import XMLRepository, XMLStore
from repository.persistence.XMLRepositoryView import XMLRepositoryView
from repository.remote.Transport import SOAPTransport, JabberTransport
from repository.remote.RemoteFilter import RemoteFilter
from repository.util.UUID import UUID


class RemoteRepository(XMLRepository):

    def __init__(self, dbHome, protocol, *args, **kwds):
        'Construct an RemoteRepository giving it a transport handler'
        
        super(RemoteRepository, self).__init__(dbHome)
        
        if protocol == 'soap':
            self.transport = SOAPTransport(self, *args, **kwds)
        elif protocol == 'jabber':
            self.transport = JabberTransport(self, *args, **kwds)
        else:
            raise NotImplementedError, '%s protocol' %(protocol)

    def _createStore(self):

        return RemoteStore(self, self.transport)
    

class RemoteStore(XMLStore):

    def __init__(self, repository, transport):

        super(RemoteStore, self).__init__(repository)
        self.transport = transport

    def open(self, create=False):

        super(RemoteStore, self).open(create=create)
        self.transport.open()

    def close(self):

        super(RemoteStore, self).close()
        self.transport.close()

    def loadItem(self, version, uuid):

        doc = super(RemoteStore, self).loadItem(version, uuid)
        if doc is None:
            versionId = self._versions.getVersionId(self.itsUUID)
            remoteVersion = self._versions.getVersion(versionId)
            xml = self.transport.serveItem(remoteVersion, uuid)
            if xml is not None:
                filter = RemoteFilter(self, versionId)
                self.transport.parseDoc(xml, filter)
                doc = filter.getDocument()

        return doc

    def loadChild(self, version, uuid, name):

        doc = super(RemoteStore, self).loadChild(version, uuid, name)
        if doc is None:
            versionId = self._versions.getVersionId(self.itsUUID)
            remoteVersion = self._versions.getVersion(versionId)
            xml = self.transport.serveChild(remoteVersion, uuid, name)
            if xml is not None:
                filter = RemoteFilter(self, versionId)
                self.transport.parseDoc(xml, filter)
                doc = filter.getDocument()

        return doc

    def getVersion(self):

        version = super(RemoteStore, self).getVersion()
        versions = self._versions
        
        if version == 0:
            versionId, version = self.transport.getVersionInfo()

            txnStarted = False
            try:
                txnStarted = self.startTransaction()
                versions.setVersion(version)
                versions.setVersion(version, versionId)
                versions.setVersionId(versionId, self.itsUUID)
            except:
                if txnStarted:
                    txnStarted = self.abortTransaction()
                raise
            else:
                if txnStarted:
                    txnStarted = self.commitTransaction()
                
        return version

    itsUUID = UUID('200a5564-a60f-11d8-fb65-000393db837c')

