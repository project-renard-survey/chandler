
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2002 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import Item
from model.util.UUID import UUID
from model.util.Path import Path


class ItemRef(object):
    'A wrapper around a bi-directional link between two items.'
    
    def __init__(self, item, name, other, otherName, otherCard=None):

        super(ItemRef, self).__init__()

        self._attach(item, name, other, otherName, otherCard)

    def __repr__(self):

        return "<ItemRef: %s>" %(str(self._other))

    def getItem(self):
        'Return the item this link was established from.'
        
        return self._item

    def getOther(self):
        'Return the opposite item this link was established from.'

        return self._other

    def _attach(self, item, name, other, otherName, otherCard=None):

        if item is None:
            raise ValueError, "Originating endpoint is None"

        self._item = item
        self._other = other

        if other is not None:
            if other.hasAttribute(otherName):
                old = other.getAttribute(otherName)
                if isinstance(old, RefDict):
                    old[item.refName(otherName)] = self
                    return
            else:
                if otherCard is None:
                    otherCard = other.getAttrAspect(otherName, 'Cardinality',
                                                    'single')
                if otherCard == 'dict':
                    old = RefDict(other, otherName, name)
                    other._references[otherName] = old
                    old[item.refName(otherName)] = self
                    return
                elif otherCard == 'list':
                    old = RefList(other, otherName, name)
                    other._references[otherName] = old
                    old[item.refName(otherName)] = self
                    return
            
            other.setAttribute(otherName, self)

    def _detach(self, item, name, other, otherName):

        if other is not None:
            old = other.getAttribute(name, _attrDict=other._references)
            if isinstance(old, RefDict):
                old._removeRef(item.refName(otherName))
            else:
                other._removeRef(otherName)

    def _reattach(self, item, name, old, new, otherName):

        self._detach(item, name, old, otherName)
        self._attach(item, name, new, otherName)

    def other(self, item):
        'Return the other end of the ref relative to item.'

        if self._item is item:
            return self._other
        elif self._other is item:
            return self._item
        else:
            return None

    def _refCount(self):

        return 1

    def _xmlValue(self, name, item, generator, withSchema):

        def typeName(value):
            
            if isinstance(value, UUID):
                return 'uuid'
            if isinstance(value, Path):
                return 'path'

            raise ValueError, "%s not supported here" %(str(type(value)))

        other = self.other(item)
        if other is None:
            raise ValueError, "dangling ref at %s.%s" %(str(item.getPath()),
                                                        name)

        attrs = { 'type': 'uuid' }

        if isinstance(name, UUID):
            attrs['nameType'] = "uuid"
            attrs['name'] = name.str64()
        elif not isinstance(name, str) and not isinstance(name, unicode):
            attrs['nameType'] = typeName(name)
            attrs['name'] = str(name)
        else:
            attrs['name'] = name

        if withSchema:
            otherName = item._otherName(name)
            attrs['otherName'] = otherName
            attrs['otherCard'] = other.getAttrAspect(otherName, 'Cardinality',
                                                     'single')

        generator.startElement('ref', attrs)
        generator.characters(other.getUUID().str64())
        generator.endElement('ref')


class RefDict(dict):

    def __init__(self, item, name, otherName, initialDict=None):

        super(RefDict, self).__init__()

        self._item = item
        self._name = name
        self._otherName = otherName
        
        if initialDict is not None:
            self.update(initialDict)

    def update(self, valueDict):

        for value in valueDict.iteritems():
            self[value[0]] = value[1]

    def clear(self):

        for key in self.keys():
            del self[key]

    def dir(self):

        for item in self:
            print item

    def __getitem__(self, key):

        value = super(RefDict, self).__getitem__(key)
        if value is not None:
            value = value.other(self._item)

        return value

    def __setitem__(self, key, value):

        old = super(RefDict, self).get(key)
        isItem = isinstance(value, Item.Item)

        if isinstance(old, ItemRef):
            if isItem:
                old._reattach(self._item, self._name,
                              old.other(self._item), value, self._otherName)
            else:
                old._detach(self._item, self._name,
                            old.other(self._item), self._otherName)
        else:
            if isItem:
                value = ItemRef(self._item, self._name, value, self._otherName)
            
            super(RefDict, self).__setitem__(key, value)

    def __delitem__(self, key):

        value = self._getRef(key)
        value._detach(self._item, self._name,
                      value.other(self._item), self._otherName)
        self._removeRef(key)

    def _removeRef(self, key):

        super(RefDict, self).__delitem__(key)

    def _getRef(self, key):

        return super(RefDict, self).get(key)

    def get(self, key, default=None):

        value = super(RefDict, self).get(key, default)
        if value is not default:
            value = value.other(self._item)

        return value

    def __iter__(self):

        class keyIter(object):

            def __init__(self, refDict):

                super(keyIter, self).__init__()

                self._iter = refDict.iterkeys()
                self._refDict = refDict

            def next(self):

                return self._refDict[self._iter.next()]

        return keyIter(self)

    def others(self):
        'Return the list of other ends of the refs relative to item.'

        others = []
        for item in self:
            other.append(item)

        return others

    def _refCount(self):

        return len(self)

    def _getCard(self):

        return 'dict'

    def _xmlValue(self, name, item, generator, withSchema):

        if len(self) > 0:

            if withSchema:
                for other in self:
                    break

            attrs = { 'name': name }
            if withSchema:
                otherName = item._otherName(name)
                otherCard = other.getAttrAspect(otherName, 'Cardinality',
                                                'single')
                attrs['cardinality'] = self._getCard()
                attrs['otherName'] = otherName
                attrs['otherCard'] = otherCard

            generator.startElement('ref', attrs)
            for ref in self.iteritems():
                ref[1]._xmlValue(ref[0], item, generator, False)
            generator.endElement('ref')


class RefList(RefDict):

    def __init__(self, item, name, otherName, initialList=None):

        super(RefList, self).__init__(item, name, otherName, None)

        self._keys = []

        if initialList is not None:
            self.extend(initialList)

    def extend(self, valueList):

        for value in valueList:
            self.append(value)

    def append(sef, value):

        self[value.refName(self._name)] = value

    def dir(self):

        for key in self._keys:
            print self[key]

    def __getitem__(self, key):

        if isinstance(key, int):
            key = self._keys[key]
            
        return super(RefList, self).__getitem__(key)

    def __setitem__(self, key):

        if isinstance(key, int):
            key = self._keys[key]
            
        super(RefList, self).__setitem__(key, value)

    def __setitem__(self, key, value):

        hasKey = self.has_key(key)
        super(RefList, self).__setitem__(key, value)

        if not hasKey:
            self._keys.append(key)
    
    def __delitem__(self, key):

        if isinstance(key, int):
            key = self._keys[key]
            
        super(RefList, self).__delitem__(key)

        if not self.has_key(key):
            self._keys.remove(key)

    def _removeRef(self, key):

        super(RefList, self)._removeRef(key)
        
        if not self.has_key(key):
            self._keys.remove(key)

    def __iter__(self):

        class keyIter(object):

            def __init__(self, refList):

                super(keyIter, self).__init__()

                self._iter = refList._keys.__iter__()
                self._refList = refList

            def next(self):

                return self._refList[self._iter.next()]

        return keyIter(self)

    def _getCard(self):

        return 'list'
