__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2003 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import time
import application.Globals as Globals
from application.Application import mixinAClass
from Block import *
from ContainerBlocks import *
from Styles import Font
from repository.util.UUID import UUID
from wxPython.wx import *
from wxPython.gizmos import *
from wxPython.html import *
import webbrowser # for opening external links

class Button(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        try:
            id = Block.getwxID(self)
        except AttributeError:
            id = 0

        if self.buttonKind == "Text":
            button = wxButton(parentWindow, id, self.title,
                              wxDefaultPosition,
                              (self.minimumSize.width, self.minimumSize.height))
        elif self.buttonKind == "Image":
            image = wxImage(self.icon, wxBITMAP_TYPE_PNG)
            bitmap = image.ConvertToBitmap()
            button = wxBitmapButton(parentWindow, id, bitmap,
                              wxDefaultPosition,
                              (self.minimumSize.width, self.minimumSize.height))
        elif self.buttonKind == "Toggle":
            if wxPlatform == '__WXMAC__': # @@@ Toggle buttons are not supported under OSX
                button = wxButton(parentWindow, id, self.title,
                                  wxDefaultPosition,
                                  (self.minimumSize.width, self.minimumSize.height))
            else:
                button = wxToggleButton(parentWindow, id, self.title,
                                        wxDefaultPosition,
                                        (self.minimumSize.width, self.minimumSize.height))
        elif __debug__:
            assert False, "unknown buttonKind"

        EVT_BUTTON(parentWindow, id, self.buttonPressed)
        self.parentBlock.addToContainer(parent, button, self.stretchFactor,
                                        self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return button, None, None

    def buttonPressed(self, event):
        try:
            event = self.event
        except AttributeError:
            pass
        else:
            self.Post(event, {'item':self})

                              
class Choice(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        choice = wxChoice(parentWindow, -1, 
                              wxDefaultPosition,
                              (self.minimumSize.width, self.minimumSize.height),
                              self.choices)
        self.parentBlock.addToContainer(parent, choice, self.stretchFactor, 
                                        self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return choice, None, None


class ComboBox(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        comboBox = wxComboBox(parentWindow, -1, self.selection, 
                              wxDefaultPosition,
                              (self.minimumSize.width, self.minimumSize.height),
                              self.choices)
        self.parentBlock.addToContainer(parent, comboBox, self.stretchFactor, 
                                        self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return comboBox, None, None


class wxEditText(wxTextCtrl):
    def __init__(self, *arguments, **keywords):
        wxTextCtrl.__init__ (self, *arguments, **keywords)
        EVT_TEXT_ENTER(self, self.GetId(), self.OnEnterPressed)

    def OnEnterPressed(self, event):
        counterpart = Globals.repository.find (self.counterpartUUID)
        counterpart.Post (Globals.repository.find('//parcels/OSAF/framework/blocks/Events/EnterPressed'),
                          {'text':self.GetValue()})

            
class EditText(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        style = 0
        if self.textAlignmentEnum == "Left":
            style |= wxTE_LEFT
        elif self.textAlignmentEnum == "Center":
            style |= wxTE_CENTRE
        elif self.textAlignmentEnum == "Right":
            style |= wxTE_RIGHT

        if self.lineStyleEnum == "MultiLine":
            style |= wxTE_MULTILINE
        else:
            style |= wxTE_PROCESS_ENTER

        if self.textStyleEnum == "RichText":
            style |= wxTE_RICH2

        if self.readOnly:
            style |= wxTE_READONLY

        editText = wxEditText (parentWindow,
                               -1,
                               "",
                               wxDefaultPosition,
                               (self.minimumSize.width, self.minimumSize.height),
                               style=style, name=self._name)

        editText.SetFont(Font (self.characterStyle))
        self.parentBlock.addToContainer(parent,
                                        editText,
                                        self.stretchFactor, 
                                        self.Calculate_wxFlag(),
                                        self.Calculate_wxBorder())
        return editText, None, None



class wxHTML(wxHtmlWindow):
    def OnLinkClicked(self, link):
        webbrowser.open(link.GetHref())
    
class HTML(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        htmlWindow = wxHTML(parentWindow,
                            Block.getwxID(self),
                            wxDefaultPosition,
                            (self.minimumSize.width,
                             self.minimumSize.height))
        if self.url:
            htmlWindow.LoadPage(self.url)

        self.parentBlock.addToContainer(parent,
                                        htmlWindow,
                                        self.stretchFactor,
                                        self.Calculate_wxFlag(),
                                        self.Calculate_wxBorder())
        return htmlWindow, None, None

 
class ListDelegate:
    """
      Default delegate for Lists that use the block's contentSpec. Override
    to customize your behavior.
    """
    def ElementText (self, index, column):
        counterpart = Globals.repository.find (self.counterpartUUID)
        result = counterpart.contentSpec[item]
        column = counterpart.columnHeadings[column]
        try:
            return str (result.getAttributeValue(column))
        except AttributeError:
            return ""

    def ElementCount (self):
        counterpart = Globals.repository.find (self.counterpartUUID)
        return counterpart.contentSpec.len()


class wxListBlock(wxListCtrl):
    def __init__(self, *arguments, **keywords):
        wxListCtrl.__init__(self, *arguments, **keywords)
        EVT_LIST_ITEM_SELECTED(self, self.GetId(), self.On_wxSelectionChanged)
        EVT_IDLE(self, self.OnIdle)
        EVT_SIZE(self, self.OnSize)
        self.scheduleUpdate = False
        self.lastUpdateTime = 0

    def OnIdle(self, event):
        """
          Wait a second after a update is first scheduled before updating
        and don't update more than once a second.
        """
        if self.scheduleUpdate:
            if (time.time() - self.lastUpdateTime) > 1.0:
                counterpart = Globals.repository.find (self.counterpartUUID)
                counterpart.SynchronizeFramework()
        else:
            lastupdateTime = time.time()
        event.Skip()

    def OnSize(self, event):
        if not Globals.wxApplication.insideSynchronizeFramework:
            size = event.GetSize()
            widthMinusLastColumn = 0
            assert self.GetColumnCount() > 0, "We're assuming that there is at least one column"
            for column in range (self.GetColumnCount() - 1):
                widthMinusLastColumn += self.GetColumnWidth (column)
            lastColumnWidth = size.width - widthMinusLastColumn
            if lastColumnWidth > 0:
                self.SetColumnWidth (self.GetColumnCount() - 1, lastColumnWidth)
            event.Skip()

    def On_wxSelectionChanged(self, event):
        if not Globals.wxApplication.insideSynchronizeFramework:
            counterpart = Globals.repository.find (self.counterpartUUID)
            item = counterpart.contentSpec [event.GetIndex()]
            if counterpart.selection != item:
                counterpart.selection = item
            counterpart.Post (Globals.repository.find('//parcels/OSAF/framework/blocks/Events/SelectionChanged'),
                              {'item':item})


    def wxSynchronizeFramework(self):
        counterpart = Globals.repository.find (self.counterpartUUID)
        elementDelegate = counterpart.elementDelegate
        if not elementDelegate:
            elementDelegate = '//parcels/OSAF/framework/blocks/ControlBlocks/ListDelegate'
        mixinAClass (self, elementDelegate)

        queryItem = counterpart.contentSpec
        queryItem.resultsStale = True
        self.Freeze()
        self.ClearAll()
        for index in range (len(counterpart.columnHeadings)):
            self.InsertColumn(index,
                              str(counterpart.columnHeadings[index]),
                              width = counterpart.columnWidths[index])

        self.SetItemCount (self.ElementCount())
        self.Thaw()
        try:
            subscription = self.subscriptionUUID
        except AttributeError:
            counterpart = Globals.repository.find (self.counterpartUUID)
            events = [Globals.repository.find('//parcels/OSAF/framework/item_changed'),
                      Globals.repository.find('//parcels/OSAF/framework/item_added'),
                      Globals.repository.find('//parcels/OSAF/framework/item_deleted')]
            self.subscriptionUUID = UUID()
            Globals.notificationManager.Subscribe (events,
                                                   self.subscriptionUUID,
                                                   queryItem.onItemChanges)
                
        if counterpart.selection:
            self.GoToItem (counterpart.selection)

        self.scheduleUpdate = False
        self.lastUpdateTime = time.time()
        
    def __del__(self):
        Globals.notificationManager.Unsubscribe(self.subscriptionUUID)
        del Globals.association [self.counterpartUUID]


    def OnGetItemText (self, index, column):
        """
          OnGetItemText won't be called if it's in the delegate -- WxPython won't
        call it if it's in a base class
        """
        return self.ElementText (index, column)

    def GoToItem(self, item):
        counterpart = Globals.repository.find (self.counterpartUUID)
        index = counterpart.contentSpec.index (item)
        self.Select (index)


class List(RectangularChild):
    def __init__(self, *arguments, **keywords):
        super (List, self).__init__ (*arguments, **keywords)
        self.selection = None

    def renderOneBlock (self, parent, parentWindow):
        list = wxListBlock(parentWindow,
                           Block.getwxID(self),
                           style=self.Calculate_wxStyle())
        self.parentBlock.addToContainer(parent,
                                        list,
                                        self.stretchFactor,
                                        self.Calculate_wxFlag(),
                                        self.Calculate_wxBorder())
        return list, None, None

    def Calculate_wxStyle (self):
        style = wxLC_REPORT|wxLC_VIRTUAL|wxSUNKEN_BORDER|wxLC_EDIT_LABELS
        return style

    def NeedsUpdate(self):
        wxWindow = Globals.association[self.itsUUID]
        wxWndow.scheduleUpdate = True    

    def OnSelectionChangedEvent (self, notification):
        """
          Display the item in the wxWindow counterpart.
        """
        self.selection = notification.data['item']
        self.GoToItem (self.selection)


class RadioBox(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        if self.radioAlignEnum == "Across":
            dimension = wxRA_SPECIFY_COLS
        elif self.radioAlignEnum == "Down":
            dimension = wxRA_SPECIFY_ROWS
        elif __debug__:
            assert False, "unknown radioAlignEnum"
                                    
        radioBox = wxRadioBox(parentWindow, -1, self.title,
                              wxDefaultPosition, 
                              (self.minimumSize.width, self.minimumSize.height),
                              self.choices, self.itemsPerLine, dimension)
        self.parentBlock.addToContainer(parent, radioBox, self.stretchFactor, 
                                        self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return radioBox, None, None


class ScrolledWindow(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        return None, None, None


class StaticText(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        if self.textAlignmentEnum == "Left":
            style = wxALIGN_LEFT
        elif self.textAlignmentEnum == "Center":
            style = wxALIGN_CENTRE
        elif self.textAlignmentEnum == "Right":
            style = wxALIGN_RIGHT

        staticText = wxStaticText (parentWindow,
                                   -1,
                                   self.title,
                                   wxDefaultPosition,
                                   (self.minimumSize.width, self.minimumSize.height),
                                   style)

        staticText.SetFont(Font (self.characterStyle))
        self.parentBlock.addToContainer(parent, staticText,
                                        self.stretchFactor,
                                        self.Calculate_wxFlag(),
                                        self.Calculate_wxBorder())
        return staticText, None, None


class StatusBar(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        frame = Globals.wxApplication.mainFrame
        assert (frame.GetStatusBar () == None), "mainFrame already has a StatusBar"
        frame.CreateStatusBar ()
        
        return None, None, None
    

class ToolbarItem(RectangularChild):
    """
      Under construction
    """
    def renderOneBlock (self, parent, parentWindow):
        # @@@ Must use self.toolbarLocation rather than wxMainFrame.GetToolBar()
        tool = None
        wxToolbar = Globals.wxApplication.mainFrame.GetToolBar()
        toolbar = Globals.repository.find(wxToolbar.counterpartUUID)
        id = Block.getwxID(self)
        if self.toolbarItemKind == 'Button':
            bitmap = wxImage (self.bitmap, wxBITMAP_TYPE_PNG).ConvertToBitmap()
            tool = wxToolbar.AddSimpleTool (id, bitmap, 
                                            self.title, self.statusMessage)
            EVT_TOOL(parentWindow, id, toolbar.toolPressed)
        elif self.toolbarItemKind == 'Separator':
            wxToolbar.AddSeparator()
        elif self.toolbarItemKind == 'Check':
            pass
        elif self.toolbarItemKind == 'Radio':
            pass
        elif self.toolbarItemKind == 'Text':
            tool = wxTextCtrl (wxToolbar, id, "", 
                               wxDefaultPosition, 
                               wxSize(300,-1), 
                               wxTE_PROCESS_ENTER)
            tool.SetName(self.title)
            wxToolbar.AddControl (tool)
            EVT_TEXT_ENTER(tool, id, toolbar.toolEnterPressed)
        elif __debug__:
            assert False, "unknown toolbarItemKind"

        wxToolbar.Realize()

        return tool, None, None


class wxTreeAndList:
    def __init__(self, *arguments, **keywords):
        EVT_TREE_ITEM_EXPANDING(self, self.GetId(), self.OnExpanding)
        EVT_TREE_ITEM_COLLAPSING(self, self.GetId(), self.OnCollapsing)
        EVT_LIST_COL_END_DRAG(self, self.GetId(), self.OnColumnDrag)
        EVT_TREE_SEL_CHANGED(self, self.GetId(), self.On_wxSelectionChanged)
        EVT_IDLE(self, self.OnIdle)
        EVT_SIZE(self, self.OnSize)
        self.scheduleUpdate = False
        self.lastUpdateTime = 0

    def OnIdle(self, event):
        """
          Wait a second after a update is first scheduled before updating
        and don't update more than once a second.
        """
        if self.scheduleUpdate:
           if (time.time() - self.lastUpdateTime) > 0.5:
               counterpart = Globals.repository.find (self.counterpartUUID)
               counterpart.SynchronizeFramework()
        else:
            lastupdateTime = time.time()
        event.Skip()

    def OnSize(self, event):
        if not Globals.wxApplication.insideSynchronizeFramework:
            size = event.GetSize()
            if isinstance (self, wxTreeListCtrl):
                widthMinusLastColumn = 0
                assert self.GetColumnCount() > 0, "We're assuming that there is at least one column"
                for column in range (self.GetColumnCount() - 1):
                    widthMinusLastColumn += self.GetColumnWidth (column)
                lastColumnWidth = size.width - widthMinusLastColumn
                if lastColumnWidth > 0:
                    self.SetColumnWidth (self.GetColumnCount() - 1, lastColumnWidth)
            else:
                assert isinstance (self, wxTreeCtrl), "We're assuming the only other choice is a wxTree"
                self.SetSize (size)
            event.Skip()

    def OnExpanding(self, event):
        self.LoadChildren(event.GetItem())

    def LoadChildren(self, parentId):
        """
          Load the items in the tree only when they are visible.
        """
        child, cookie = self.GetFirstChild (parentId, 0)
        if not child.IsOk():
            
            counterpart = Globals.repository.find (self.counterpartUUID)
    
            parentUUID = self.GetPyData (parentId)
            for child in self.ElementChildren (Globals.repository [parentUUID]):
                cellValues = self.ElementCellValues (child)
                childNodeId = self.AppendItem (parentId,
                                               cellValues.pop(0),
                                               -1,
                                               -1,
                                               wxTreeItemData (child.itsUUID))
                index = 1
                for value in cellValues:
                    self.SetItemText (childNodeId, value, index)
                    index += 1
                self.SetItemHasChildren (childNodeId, self.ElementHasChildren (child))
    
            counterpart.openedContainers [parentUUID] = True

    def OnCollapsing(self, event):
        counterpart = Globals.repository.find (self.counterpartUUID)
        id = event.GetItem()
        """
          if the data passed in has a UUID we'll keep track of the
        state of the opened tree
        """
        try:
            del counterpart.openedContainers [self.GetPyData(id)]
        except AttributeError:
            pass
        self.CollapseAndReset (id)

    def OnColumnDrag(self, event):
        if not Globals.wxApplication.insideSynchronizeFramework:
            counterpart = Globals.repository.find (self.counterpartUUID)
            columnIndex = event.GetColumn()
            try:
                counterpart.columnWidths [columnIndex] = self.GetColumnWidth (columnIndex)
            except AttributeError:
                pass

    def On_wxSelectionChanged(self, event):
        if not Globals.wxApplication.insideSynchronizeFramework:
            counterpart = Globals.repository.find (self.counterpartUUID)
    
            itemUUID = self.GetPyData(self.GetSelection())
            selection = Globals.repository.find (itemUUID)
            if counterpart.selection != selection:
                counterpart.selection = selection
        
                counterpart.Post (Globals.repository.find('//parcels/OSAF/framework/blocks/Events/SelectionChanged'),
                                  {'item':selection})

    def wxSynchronizeFramework(self):
        def ExpandContainer (self, openedContainers, id):
            try:
                expand = openedContainers [self.GetPyData(id)]
            except KeyError:
                return

            self.LoadChildren(id)
            if self.IsVisible(id):
                self.Expand(id)
            child, cookie = self.GetFirstChild (id, 0)
            while child.IsOk():
                ExpandContainer (self, openedContainers, child)
                child = self.GetNextSibling (child)

        counterpart = Globals.repository.find (self.counterpartUUID)
        mixinAClass (self, counterpart.elementDelegate)
        
        try:
            counterpart.columnHeadings
        except AttributeError:
            pass # A wxTreeCtrl won't use columnHeadings
        else:
            for index in xrange(self.GetColumnCount()):
                self.RemoveColumn (0)
    
            info = wxTreeListColumnInfo()
            for index in range (len(counterpart.columnHeadings)):
                info.SetText (counterpart.columnHeadings[index])
                info.SetWidth (counterpart.columnWidths[index])
                self.AddColumnInfo (info)

        self.DeleteAllItems()

        root = counterpart.rootPath
        if not root:
            root = self.ElementChildren (None)
        cellValues = self.ElementCellValues (root)
        rootNodeId = self.AddRoot (cellValues.pop(0),
                                   -1,
                                   -1,
                                   wxTreeItemData (root.itsUUID))
        self.SetItemHasChildren (rootNodeId, self.ElementHasChildren (root))
        self.LoadChildren(rootNodeId)
        ExpandContainer (self, counterpart.openedContainers, self.GetRootItem ())

        selection = counterpart.selection
        if not selection:
            selection = root
        self.GoToItem (selection)

        try:
            subscription = self.subscriptionUUID
        except AttributeError:
            events = [Globals.repository.find('//parcels/OSAF/framework/item_changed'),
                      Globals.repository.find('//parcels/OSAF/framework/item_added'),
                      Globals.repository.find('//parcels/OSAF/framework/item_deleted')]
            counterpart = Globals.repository.find (self.counterpartUUID)
            self.subscriptionUUID = UUID()
            Globals.notificationManager.Subscribe (events,
                                                   self.subscriptionUUID,
                                                   self.NeedsUpdate)
        self.scheduleUpdate = False
        self.lastUpdateTime = time.time()
        
    def __del__(self):
        Globals.notificationManager.Unsubscribe(self.subscriptionUUID)
        del Globals.association [self.counterpartUUID]

    def GoToItem(self, item):
        def ExpandTreeToItem (self, item):
            parent = self.ElementParent (item)
            if parent:
                id = ExpandTreeToItem (self, parent)
                self.LoadChildren(id)
                if self.IsVisible(id):
                    self.Expand(id)
                itemUUID = item.itsUUID
                child, cookie = self.GetFirstChild (id, 0)
                while child.IsOk():
                    if self.GetPyData(child) == itemUUID:
                        return child
                    child = self.GetNextSibling (child)
                assert False, "Didn't find the item in the tree"
                return None
            else:
                return self.GetRootItem()

        id = ExpandTreeToItem (self, item)
        self.SelectItem (id)
        self.ScrollTo (id)

 
class wxTree(wxTreeCtrl, wxTreeAndList):
    def __init__(self, *arguments, **keywords):
        wxTreeCtrl.__init__ (self, *arguments, **keywords)
        wxTreeAndList.__init__ (self, *arguments, **keywords)
    

class wxTreeList(wxTreeListCtrl, wxTreeAndList):
    def __init__(self, *arguments, **keywords):
        wxTreeListCtrl.__init__ (self, *arguments, **keywords)
        wxTreeAndList.__init__ (self, *arguments, **keywords)
    

class Tree(RectangularChild):
    def __init__(self, *arguments, **keywords):
        super (Tree, self).__init__ (*arguments, **keywords)
        self.openedContainers = {}
        self.rootPath = None
        self.selection = None

    def renderOneBlock(self, parent, parentWindow, nativeWindow=None):
        if nativeWindow:
            tree = nativeWindow
        else:
            try:
                self.columnHeadings
            except AttributeError:
                tree = wxTree (parentWindow, Block.getwxID(self), style = self.Calculate_wxStyle())
            else:
                tree = wxTreeList (parentWindow, Block.getwxID(self), style = self.Calculate_wxStyle())
        self.parentBlock.addToContainer(parent,
                                        tree,
                                        self.stretchFactor,
                                        self.Calculate_wxFlag(),
                                        self.Calculate_wxBorder())
        return tree, None, None

    def OnSelectionChangedEvent (self, notification):
        wxCounterpart = Globals.association[self.itsUUID]
        wxCounterpart.GoToItem (notification.GetData()['item'])

    def Calculate_wxStyle (self):
        style = wxTR_DEFAULT_STYLE|wxNO_BORDER
        if self.hideRoot:
            style |= wxTR_HIDE_ROOT
        if self.noLines:
            style |= wxTR_NO_LINES
        if self.useButtons:
            style |= wxTR_HAS_BUTTONS
        else:
            style |= wxTR_NO_BUTTONS
        return style


class wxItemDetail(wxHtmlWindow):
    def OnLinkClicked(self, wx_linkinfo):
        """
          Clicking on an item changes the selection (post notification).
          Clicking on a URL loads the page in a separate browser.
        """
        itemURL = wx_linkinfo.GetHref()
        item = Globals.repository.find(itemURL)
        if not item:
            webbrowser.open(itemURL)
        else:
            event = Globals.repository.find('//parcels/OSAF/framework/blocks/Events/SelectionChanged')
            event.Post({'item':item, 'type':'Normal'})

    def wxSynchronizeFramework(self):
        counterpart = Globals.repository.find (self.counterpartUUID)
        if counterpart.selection:
            self.SetPage(counterpart.getHTMLText(counterpart.selection))
        else:
            self.SetPage('<html><body></body></html>')


class ItemDetail(RectangularChild):
    def __init__(self, *arguments, **keywords):
        super (ItemDetail, self).__init__ (*arguments, **keywords)
        self.selection = None

    def renderOneBlock (self, parent, parentWindow):
        htmlWindow = wxItemDetail(parentWindow,
                                  Block.getwxID(self),
                                  wxDefaultPosition,
                                  (self.minimumSize.width,
                                   self.minimumSize.height))
        
        
        self.parentBlock.addToContainer(parent,
                                        htmlWindow,
                                        self.stretchFactor,
                                        self.Calculate_wxFlag(),
                                        self.Calculate_wxBorder())
        
        return htmlWindow, None, None

    def getHTMLText(self, item):
        return '<body><html><h1>%s</h1></body></html>' % item.getDisplayName()

    def OnSelectionChangedEvent (self, notification):
        """
          Display the item in the wxWindow counterpart.
        """
        self.selection = notification.data['item']
        self.SynchronizeFramework ()
