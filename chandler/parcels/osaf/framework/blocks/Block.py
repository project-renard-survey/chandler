__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2003-2004 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import application.Globals as Globals
from repository.item.Item import Item
from repository.util.UUID import UUID
from osaf.framework.notifications.schema.Event import Event
import wx
import logging


class Block(Item):
    def __init__(self, *arguments, **keywords):
        super (Block, self).__init__ (*arguments, **keywords)
        """
          We currently have to initialize this data here because of
        limitations of our repository/XML parcel. We should fix
        these limitations so we can initialize them in the parcel
        XML -- DJA
        """
        self.childrenBlocks = []
        self.styles = []

    def Post (self, event, args):
        """
          Events that are posted by the block pass along the block
        that sent it.
        """
        args['sender'] = self
        event.Post (args)

    subscribedBlocks = {}              # A dictionary mapping block UUIDS to event subscription clientIDs

    def render (self):
        try:
            instantiateWidgetMethod = getattr (self, "instantiateWidget")
        except AttributeError:
            return
        else:
            oldIgnoreSynchronizeWidget = Globals.wxApplication.ignoreSynchronizeWidget
            Globals.wxApplication.ignoreSynchronizeWidget = True
            try:
                widget = instantiateWidgetMethod()
            finally:
                Globals.wxApplication.ignoreSynchronizeWidget = oldIgnoreSynchronizeWidget
            """
              Store a non persistent pointer to the widget in the block and pin the block
            to keep it in memory. Store a pointer to the block in the widget. Undo all this
            when the widget is destroyed.
            """

            if widget:
                self.setPinned()
                self.widget = widget
                widget.blockItem = self
                """
                  After the blocks are wired up, call OnInit if it exists.
                """
                try:
                    OnInitMethod = getattr (widget, "OnInit")
                except AttributeError:
                    pass
                else:
                    OnInitMethod()
                """
                  For those blocks with contents, we need to subscribe to notice changes
                to items in the contents.
                """
                if self.hasAttributeValue ('contents'):
                    events = [Globals.repository.findPath('//parcels/osaf/contentmodel/collection_changed')]
                    Globals.notificationManager.Subscribe(events, id(widget), self.onCollectionChanged)

                """
                  For those blocks with subscribeWhenVisibleEvents or subscribeAlwaysEvents,
                we need to subscribe to them.
                """
                try:
                    subscribeWhenVisibleEvents = self.subscribeWhenVisibleEvents
                except AttributeError:
                    pass
                else:
                    if  widget.IsShown():
                        widget.subscribeWhenVisibleEventsUUID = UUID()
                        Globals.notificationManager.Subscribe (subscribeWhenVisibleEvents,
                                                               widget.subscribeWhenVisibleEventsUUID,
                                                               Globals.mainView.dispatchEvent)

                try:
                    subscribeAlwaysEvents = self.subscribeAlwaysEvents
                except:
                    pass
                else:
                    if not subscribedBlocks.has_key (self.itsUUID):
                        subscribedBlocks [self.itsUUID] = UUID()
                        Globals.notificationManager.Subscribe (subscribeAlwaysEvents,
                                                               subscribedBlocks [self.itsUUID],
                                                               Globals.mainView.dispatchEvent)

                doFreeze = isinstance (widget, wx.Window)
                if doFreeze:
                    widget.Freeze()
                for child in self.childrenBlocks:
                    child.render()
                """
                  After the blocks are wired up give the window a chance
                to synchronize itself to any persistent state.
                """
                oldIgnoreSynchronizeWidget = Globals.wxApplication.ignoreSynchronizeWidget
                Globals.wxApplication.ignoreSynchronizeWidget = False
                try:
                    self.synchronizeWidget()
                finally:
                    Globals.wxApplication.ignoreSynchronizeWidget = oldIgnoreSynchronizeWidget
                if doFreeze:
                    widget.Thaw()

    def rerender (self):
        """ 
        Tear down and rebuild the widgets for all blocks starting at self.
        Used by ReloadParcels
        """
        import osaf.framework.blocks.DynamicContainerBlocks as DynamicContainerBlocks
        for child in self.childrenBlocks:
            # Menus are not contined in the widget hierarchy, so
            #  we need to handle them specially.
            if isinstance(child, DynamicContainerBlocks.MenuBar):
                # flag rebuild of dynamic containers including menus
                Globals.mainView.lastDynamicParent = False
            else:
                # destroy a widget
                child.widget.Destroy ()
                child.render ()
        self.synchronizeWidget ()

    def onCollectionChanged (self, notification):
        """
          When our item collection has changed, we need to synchronize
        """
        if self.contents.itsUUID == notification.data['collection']:
            self.synchronizeWidget()

    IdToUUID = []               # A list mapping Ids to UUIDS
    UUIDtoIds = {}              # A dictionary mapping UUIDS to Ids

    MINIMUM_WX_ID = 2500
    MAXIMUM_WX_ID = 4999

    def onDestroyWidget (self):
        """
          Called just before a widget is destroyed. It is the opposite of
        instantiateWidget.
        """
        if self.hasAttributeValue ('contents'):
            Globals.notificationManager.Unsubscribe (id(self.widget))

        try:
            subscribeWhenVisibleEventsUUID = self.widget.subscribeWhenVisibleEventsUUID
        except AttributeError:
            pass
        else:
            Globals.notificationManager.Unsubscribe (self.widget.subscribeWhenVisibleEventsUUID)
            delattr (self.widget, 'subscribeWhenVisibleEventsUUID')

        delattr (self, 'widget')
        self.setPinned (False)

    def widgetIDToBlock (theClass, wxID):
        """
          Given a wxWindows Id, returns the corresponding Chandler block
        """
        return Globals.repository.find (theClass.IdToUUID [wxID - theClass.MINIMUM_WX_ID])
 
    widgetIDToBlock = classmethod (widgetIDToBlock)

    def getWidgetID (theClass, object):
        """
          wxWindows needs a integer for a id. Commands between
        wxID_LOWEST and wxID_HIGHEST are reserved. wxPython doesn't export
        wxID_LOWEST and wxID_HIGHEST, which are 4999 and 5999 respectively.
        Passing -1 for an ID will allocate a new ID starting with 0. So
        I will use the range starting at 2500 for our events.
          Use IdToUUID to lookup the Id for a event's UUID. Use UUIDtoIds to
        lookup the UUID of a block that corresponds to an event id -- DJA
        """
        UUID = object.itsUUID
        try:
            id = Block.UUIDtoIds [UUID]
        except KeyError:
            length = len (Block.IdToUUID)
            Block.IdToUUID.append (UUID)
            id = length + Block.MINIMUM_WX_ID
            assert (id <= Block.MAXIMUM_WX_ID)
            assert not Block.UUIDtoIds.has_key (UUID)
            Block.UUIDtoIds [UUID] = id
        return id
    getWidgetID = classmethod (getWidgetID)

    def onShowHideEvent(self, notification):
        self.isShown = not self.isShown
        self.synchronizeWidget()
        self.parentBlock.synchronizeWidget()

    def onShowHideEventUpdateUI(self, notification):
        notification.data['Check'] = self.isShown

    def onModifyContentsEvent(self, notification):
        event = notification.event
        operation = event.operation
        for item in event.items:
            if event.copyItems:
                item = item.copy (None, #NewName
                                  Globals.repository.findPath('//userdata')) #parent
                """
                  Hack to work around Stuarts bug #1568 -- DJA
                """
                item.contents._ItemCollection__refresh()               
            if operation == 'toggle':
                try:
                    index = self.contents.index (item)
                except ValueError:
                    operation = 'add'
                else:
                    operation = 'remove'
            method = getattr (self.contents, operation)
            method (item)

    def synchronizeWidget (self):
        """
          synchronizeWidget's job is to make the wxWidget match the state of
        the data persisted in the block. There's a tricky problem that occurs: Often
        we add a handler to the wxWidget of a block to, for example, get called
        when the user changes the selection, which we use to update the block's selection
        and post a selection changed notification. It turns out that while we are in
        synchronizeWidget, changes to the wxWidget cause these handlers to be
        called, and in this case we don't want to post a notification. So we wrap calls
        to synchronizeWidget and set a flag indicating that we're inside
        synchronizeWidget so the handlers can tell when not to post selection
        changed events. We use this flag in other similar situations, for example,
        during shutdown to ignore events caused by the framework tearing down wxWidgets.
        """
        try:
            method = getattr (self.widget, 'wxSynchronizeWidget')
        except AttributeError:
            pass
        else:
            if not Globals.wxApplication.ignoreSynchronizeWidget:
                oldIgnoreSynchronizeWidget = Globals.wxApplication.ignoreSynchronizeWidget
                Globals.wxApplication.ignoreSynchronizeWidget = True
                try:
                    method()
                finally:
                    Globals.wxApplication.ignoreSynchronizeWidget = oldIgnoreSynchronizeWidget


class ContainerChild(Block):
    pass

    
class wxRectangularChild (wx.Panel):
    def __init__(self, *arguments, **keywords):
        super (wxRectangularChild, self).__init__ (*arguments, **keywords)

    def wxSynchronizeWidget(self):
        if self.blockItem.isShown != self.IsShown():
            self.Show (self.blockItem.isShown)

    def CalculateWXBorder(self, block):
        border = 0
        spacerRequired = False
        for edge in (block.border.top, block.border.left, block.border.bottom, block.border.right):
            if edge != 0:
                if border == 0:
                    border = edge
                elif border != edge:
                    spacerRequired = False
                    break
        """
          wxWindows sizers only allow borders with the same width, or no width, however
        blocks allow borders of different sizes for each of the 4 edges, so we need to
        simulate this by adding spacers. I'm postponing this case for Jed to finish, and
        until then an assert will catch this case. DJA
        """
        assert not spacerRequired
        
        return int (border)
    CalculateWXBorder = classmethod(CalculateWXBorder)

    def CalculateWXFlag(self, block):
        if block.alignmentEnum == 'grow':
            flag = wx.GROW
        elif block.alignmentEnum == 'growConstrainAspectRatio':
            flag = wx.SHAPED
        elif block.alignmentEnum == 'alignCenter':
            flag = wx.ALIGN_CENTER
        elif block.alignmentEnum == 'alignTopCenter':
            flag = wx.ALIGN_TOP
        elif block.alignmentEnum == 'alignMiddleLeft':
            flag = wx.ALIGN_LEFT
        elif block.alignmentEnum == 'alignBottomCenter':
            flag = wx.ALIGN_BOTTOM
        elif block.alignmentEnum == 'alignMiddleRight':
            flag = wx.ALIGN_RIGHT
        elif block.alignmentEnum == 'alignTopLeft':
            flag = wx.ALIGN_TOP | wx.ALIGN_LEFT
        elif block.alignmentEnum == 'alignTopRight':
            flag = wx.ALIGN_TOP | wx.ALIGN_RIGHT
        elif block.alignmentEnum == 'alignBottomLeft':
            flag = wx.ALIGN_BOTTOM | wx.ALIGN_LEFT
        elif block.alignmentEnum == 'alignBottomRight':
            flag = wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT
        return flag
    CalculateWXFlag = classmethod(CalculateWXFlag)
    
class RectangularChild(ContainerChild):
    pass

    
class BlockEvent(Event):

    def includePolicyMethod(self, items, references, cloudAlias):
        """ Method for handling an endpoint's byMethod includePolicy """

        # Determine if we are a global event
        events = Globals.repository.findPath("//parcels/osaf/framework/blocks/Events")
        if self.itsParent is events:
            # Yes, global: don't copy me
            references[self.itsUUID] = self
            return []

        # No, not global: copy me
        items[self.itsUUID] = self
        return [self]
