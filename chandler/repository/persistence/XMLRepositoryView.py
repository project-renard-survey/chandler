
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2002 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import cStringIO

from datetime import datetime
from struct import pack, unpack

from bsddb.db import DBLockDeadlockError, DBNotFoundError
from bsddb.db import DB_DIRTY_READ, DB_LOCK_WRITE
from dbxml import XmlDocument

from repository.item.Item import Item
from repository.item.ItemRef import RefDict, TransientRefDict
from repository.persistence.Repository import Repository, RepositoryError
from repository.persistence.Repository import VersionConflictError
from repository.persistence.Repository import OnDemandRepositoryView
from repository.util.UUID import UUID
from repository.util.SAX import XMLGenerator
from repository.util.Lob import Text, Binary


class XMLRepositoryView(OnDemandRepositoryView):

    def __init__(self, repository):

        super(XMLRepositoryView, self).__init__(repository)
        self._log = []

    def getRoots(self):
        'Return a list of the roots in the repository.'

        self.repository.store.loadRoots(self.version)
        return super(XMLRepositoryView, self).getRoots()

    def logItem(self, item):
        
        if super(XMLRepositoryView, self).logItem(item):
            self._log.append(item)
            return True
        
        return False

    def dirlog(self):

        for item in self._log:
            print item.getItemPath()

    def cancel(self):

        self.repository.store._abortTransaction()

        for item in self._log:
            if item.isDeleted():
                del self._deletedRegistry[item.getUUID()]
                item._status &= ~Item.DELETED
            else:
                item.setDirty(0)
                item._unloadItem()

        del self._log[:]

    def queryItems(self, query, load=True):

        store = self.repository.store
        items = []
        
        for doc in store.queryItems(self.version, query):
            uuid = store.getDocUUID(doc)
            if not uuid in self._deletedRegistry:
                items.append(self.find(uuid, load=load and doc))

        return items


class XMLRepositoryLocalView(XMLRepositoryView):

    def createRefDict(self, item, name, otherName, persist):

        if persist:
            return XMLRefDict(self, item, name, otherName)
        else:
            return TransientRefDict(item, name, otherName)

    def getLobType(self, mode):

        if mode == 'text':
            return XMLText
        if mode == 'binary':
            return XMLBinary

        raise ValueError, mode

    def commit(self):

        repository = self.repository
        store = repository.store
        data = store._data
        versions = store._versions
        history = store._history
        env = repository._env

        before = datetime.now()
        count = len(self._log)
        txnStarted = False
        lock = None
        
        while True:
            try:
                txnStarted = store._startTransaction()

                newVersion = versions.getVersion()
                if count > 0:
                    lock = env.lock_get(env.lock_id(), self.ROOT_ID._uuid,
                                        DB_LOCK_WRITE)
                    newVersion += 1
                    versions.put(self.ROOT_ID._uuid, pack('>l', ~newVersion))

                    ood = {}
                    for item in self._log:
                        if not item.isNew():
                            uuid = item._uuid
                            version = versions.getDocVersion(uuid)
                            assert version is not None
                            if version > item._version:
                                ood[uuid] = item

                    if ood:
                        self._mergeItems(ood, self.version, newVersion,
                                         history)
                
                    for item in self._log:
                        self._saveItem(item, newVersion,
                                       data, versions, history)

            except DBLockDeadlockError:
                self.logger.info('restarting commit aborted by deadlock')
                if txnStarted:
                    store._abortTransaction()
                if lock:
                    env.lock_put(lock)
                    lock = None

                continue
            
            except:
                self.logger.exception('aborting transaction')
                if txnStarted:
                    store._abortTransaction()
                if lock:
                    env.lock_put(lock)

                raise

            else:
                if self._log:
                    for item in self._log:
                        item._setSaved(newVersion)
                    del self._log[:]

                self.logger.debug('refreshing view from version %d to %d',
                                  self.version, newVersion)

                if newVersion > self.version:
                    try:
                        oldVersion = self.version
                        self.version = newVersion

                        def unload(uuid, version, (docId, dirty)):
                            item = self._registry.get(uuid)
                            if item is not None and item._version < newVersion:
                                if self.isDebug():
                                    self.logger.debug('unloading version %d of %s',
                                                      item._version,
                                                      item.getItemPath())
                                item._unloadItem()
                            
                        history.apply(unload, oldVersion, newVersion)

                    except:
                        if txnStarted:
                            store._abortTransaction()
                        raise
            
                if txnStarted:
                    store._commitTransaction()

                if lock:
                    env.lock_put(lock)

                if count > 0:
                    self.logger.info('%s committed %d items in %s',
                                     self, count, datetime.now() - before)
                return

    def _saveItem(self, item, newVersion, data, versions, history):

        uuid = item._uuid

        if item.isDeleted():
            del self._deletedRegistry[uuid]
            if not item.isNew():
                if self.isDebug():
                    self.logger.debug('Removing version %d of %s',
                                      item._version, item.getItemPath())
                versions.setDocVersion(uuid, newVersion, 0)
                history.writeVersion(uuid, newVersion, 0, item.getDirty())

        else:
            if self.isDebug():
                self.logger.debug('Saving version %d of %s',
                                  newVersion, item.getItemPath())

            out = cStringIO.StringIO()
            generator = XMLGenerator(out, 'utf-8')
            generator.startDocument()
            item._saveItem(generator, newVersion)
            generator.endDocument()

            doc = XmlDocument()
            doc.setContent(out.getvalue())
            out.close()
            docId = data.putDocument(doc)
            versions.setDocVersion(uuid, newVersion, docId)
            history.writeVersion(uuid, newVersion, docId, item.getDirty())

    def _mergeItems(self, items, oldVersion, newVersion, history):

        def check(uuid, version, (docId, dirty)):
            item = items.get(uuid)
            if item is not None:
                if item.getDirty() & dirty:
                    raise VersionConflictError, item

        history.apply(check, oldVersion, newVersion)

        for item in items.itervalues():
            self.logger.info('Item %s is out of date but is mergeable',
                             item.getItemPath())
        raise NotImplementedError, 'item merging not yet implemented'


class XMLRepositoryClientView(XMLRepositoryView):

    def createRefDict(self, item, name, otherName, persist):

        if persist:
            return XMLClientRefDict(self, item, name, otherName)
        else:
            return TransientRefDict(item, name, otherName)


class XMLRefDict(RefDict):

    class _log(list):

        def append(self, value):
            if len(self) == 0 or value != self[-1]:
                super(XMLRefDict._log, self).append(value)


    def __init__(self, view, item, name, otherName):
        
        self._log = XMLRefDict._log()
        self._item = None
        self._uuid = UUID()
        self.view = view
        self._deletedRefs = {}
        
        super(XMLRefDict, self).__init__(item, name, otherName)

    def _getRepository(self):

        return self.view

    def _loadRef(self, key):

        view = self.view
        
        if view is not view.repository.view:
            raise RepositoryError, 'current thread is not owning thread'

        if key in self._deletedRefs:
            return None

        return self._loadRef_(key)

    def _loadRef_(self, key):

        version = self._item._version
        cursorKey = self._packKey(key)

        return self.view.repository.store._refs.loadRef(version, key,
                                                        cursorKey)

    def _changeRef(self, key):

        if not self.view.isLoading():
            self._log.append((0, key))
        
        super(XMLRefDict, self)._changeRef(key)

    def _removeRef(self, key, _detach=False):

        if not self.view.isLoading():
            self._log.append((1, key))
            self._deletedRefs[key] = key
        else:
            raise ValueError, 'detach during load'

        super(XMLRefDict, self)._removeRef(key, _detach)

    def _writeRef(self, key, version, uuid, previous, next, alias):

        self._value.truncate(0)
        self._value.seek(0)
        if uuid is not None:
            self._writeValue(uuid)
            self._writeValue(previous)
            self._writeValue(next)
            self._writeValue(alias)
        else:
            self._writeValue(None)
        value = self._value.getvalue()
            
        self.view.repository.store._refs.put(self._packKey(key, version),
                                             value)

    def _writeValue(self, value):
        
        if isinstance(value, UUID):
            self._value.write('\0')
            self._value.write(value._uuid)

        elif isinstance(value, str) or isinstance(value, unicode):
            self._value.write('\1')
            self._value.write(pack('>H', len(value)))
            self._value.write(value)

        elif value is None:
            self._value.write('\2')

        else:
            raise NotImplementedError, "value: %s, type: %s" %(value,
                                                               type(value))

    def _eraseRef(self, key):

        self.view.repository.store._refs.delete(self._packKey(key))

    def _setItem(self, item):

        if self._item is not None and self._item is not item:
            raise ValueError, 'Item is already set'
        
        self._item = item
        if item is not None:
            self._prepareKey(item._uuid, self._uuid)

    def _packKey(self, key, version=None):

        self._key.truncate(32)
        self._key.seek(0, 2)
        self._key.write(key._uuid)
        if version is not None:
            self._key.write(pack('>l', ~version))

        return self._key.getvalue()

    def _prepareKey(self, uItem, uuid):

        self._uuid = uuid

        self._key = cStringIO.StringIO()
        self._key.write(uItem._uuid)
        self._key.write(uuid._uuid)

        self._value = cStringIO.StringIO()
            
    def _xmlValues(self, generator, version, mode):

        if mode == 'save':
            for entry in self._log:
                try:
                    value = self._get(entry[1])
                except KeyError:
                    value = None
    
                if entry[0] == 0:
                    if value is not None:
                        ref = value._value
                        previous = value._previousKey
                        next = value._nextKey
                        alias = value._alias
    
                        uuid = ref.other(self._item).getUUID()
                        self._writeRef(entry[1], version,
                                       uuid, previous, next, alias)
                        
                elif entry[0] == 1:
                    self._writeRef(entry[1], version, None, None, None, None)

                else:
                    raise ValueError, entry[0]
    
            del self._log[:]
            self._deletedRefs.clear()
            
            if len(self) > 0:
                if self._aliases:
                    for key, value in self._aliases.iteritems():
                        generator.startElement('alias', { 'name': key })
                        generator.characters(value.str64())
                        generator.endElement('alias')
                generator.startElement('db', {})
                generator.characters(self._uuid.str64())
                generator.endElement('db')

        elif mode == 'serialize':
            super(XMLRefDict, self)._xmlValues(generator, mode)

        else:
            raise ValueError, mode


class XMLClientRefDict(XMLRefDict):

    def _prepareKey(self, uItem, uuid):

        self._uItem = uItem
        self._uuid = uuid
            
    def _loadRef_(self, key):

        return self.view.repository.store.loadRef(self._item._version,
                                                  self._uItem, self._uuid, key)

    def _writeRef(self, key, version, uuid, previous, next, alias):
        raise NotImplementedError, "XMLClientRefDict._writeRef"


class XMLText(Text):

    def __init__(self, *args, **kwds):

        super(XMLText, self).__init__(*args, **kwds)
        self._uuid = None
        self._view = None
        self._version = 0
        self._dirty = False
        
    def _xmlValue(self, view, generator):

        if self._uuid is None:
            self._uuid = UUID()
            self._dirty = True

        if self._dirty:
            self._version += 1
            view.repository.store._text.put(self._makeKey(), self._data)

        attrs = {}
        attrs['version'] = str(self._version)
        attrs['mimetype'] = self.mimetype
        attrs['encoding'] = self.encoding
        if self._compression:
            attrs['compression'] = self._compression
        attrs['type'] = 'uuid'
        
        generator.startElement('text', attrs)
        generator.characters(self._uuid.str64())
        generator.endElement('text')

    def _makeKey(self):

        return "%s%s" %(self._uuid._uuid, pack('>l', ~self._version))

    def _textEnd(self, view, data, attrs):

        self.mimetype = attrs.get('mimetype', 'text/plain')
        self._compression = attrs.get('compression', None)
        self._version = long(attrs.get('version', '0'))
        self._view = view

        if attrs.has_key('encoding'):
            self._encoding = attrs['encoding']

        if attrs.get('type', 'text') == 'text':
            writer = self.getWriter()
            writer.write(data)
            writer.close()
        else:
            self._uuid = UUID(data)

    def _setData(self, text):

        super(XMLText, self)._setData(text)
        self._dirty = True

    def _getData(self):

        if self._uuid is None:
            return super(XMLText, self)._getData()

        return self._view.repository.store._text.get(self._makeKey())


class XMLBinary(Binary):

    def __init__(self, *args, **kwds):

        super(XMLBinary, self).__init__(*args, **kwds)
        self._uuid = None
        self._view = None
        self._version = 0
        self._dirty = False
        
    def _xmlValue(self, view, generator):

        if self._uuid is None:
            self._uuid = UUID()
            self._dirty = True

        if self._dirty:
            self._version += 1
            view.repository.store._binary.put(self._makeKey(), self._data)

        attrs = {}
        attrs['version'] = str(self._version)
        attrs['mimetype'] = self.mimetype
        if self._compression:
            attrs['compression'] = self._compression
        attrs['type'] = 'uuid'
        
        generator.startElement('binary', attrs)
        generator.characters(self._uuid.str64())
        generator.endElement('binary')

    def _makeKey(self):

        return "%s%s" %(self._uuid._uuid, pack('>l', ~self._version))

    def _binaryEnd(self, view, data, attrs):

        self.mimetype = attrs.get('mimetype', 'text/plain')
        self._compression = attrs.get('compression', None)
        self._version = long(attrs.get('version', '0'))
        self._view = view

        if attrs.get('type', 'binary') == 'binary':
            writer = self.getWriter()
            writer.write(data)
            writer.close()
        else:
            self._uuid = UUID(data)

    def _setData(self, data):

        super(XMLBinary, self)._setData(data)
        self._dirty = True

    def _getData(self):

        if self._uuid is None:
            return super(XMLBinary, self)._getData()

        return self._view.repository.store._binary.get(self._makeKey())
