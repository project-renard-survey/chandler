import application.Globals as Globals
from Block import Block
from wxPython.wx import *
from wxPython.gizmos import *
from wxPython.html import *
from OSAF.framework.notifications.Notification import Notification


class Font(wxFont):
    def __init__(self, characterStyle):
        family = wxDEFAULT
        size = 12
        style = wxNORMAL
        underline = FALSE
        weight = wxNORMAL
        if characterStyle:
            if characterStyle.fontFamily == "SerifFont":
                family = wxROMAN
            elif characterStyle.fontFamily == "SanSerifFont":
                family = wxSWISS
            elif characterStyle.fontFamily == "FixedPitchFont":
                family = wxMODERN
    
            assert (size > 0)
            size = int (characterStyle.fontSize + 0.5) #round to integer

            for theStyle in characterStyle.fontStyle.split():
                lowerStyle = theStyle.lower()
                if lowerStyle == "bold":
                    weight = wxBOLD
                elif lowerStyle == "light":
                    weight = wxLIGHT
                elif lowerStyle == "italic":
                    style = wxITALIC
                elif lowerStyle == "underline":
                    underline = TRUE
                
        wxFont.__init__ (self,
                         size,
                         family,
                         style,
                         weight,
                         underline,
                         characterStyle.fontName)


class ContainerChild(Block):
    def render (self, parent, parentWindow):
        (window, parent, parentWindow) = self.renderOneBlock (parent, parentWindow)
        """
          Store the wxWindows version of the object in the association, so
        given the block we can find the associated wxWindows object.
        """
        if window:
            UUID = self.getUUID()
            assert not Globals.association.has_key(UUID)
            Globals.association[UUID] = window
            window.counterpartUUID = UUID
            for child in self.childrenBlocks:
                child.render (parent, parentWindow)
            self.handleChildren(window)
        return window, parent, parentWindow
                
    def getParentBlock(self, parentWindow):
        if self.parentBlock:
            return self.parentBlock
        return Globals.repository.find (parentWindow.counterpartUUID)

    def addToContainer(self, parent, child, id, flag, border):
        pass
    
    def removeFromContainer(self, parent, child):
        pass
    
    def handleChildren(self, window):
        pass

    
class RectangularChild(ContainerChild):
    def Calculate_wxFlag (self):
        if self.alignmentEnum == 'grow':
            flag = wxGROW
        elif self.alignmentEnum == 'growConstrainAspectRatio':
            flag = wxSHAPED
        elif self.alignmentEnum == 'alignCenter':
            flag = wxALIGN_CENTER
        elif self.alignmentEnum == 'alignTopCenter':
            flag = wxALIGN_TOP
        elif self.alignmentEnum == 'alignMiddleLeft':
            flag = wxALIGN_LEFT
        elif self.alignmentEnum == 'alignBottomCenter':
            flag = wxALIGN_BOTTOM
        elif self.alignmentEnum == 'alignMiddleRight':
            flag = wxALIGN_RIGHT
        elif self.alignmentEnum == 'alignTopLeft':
            flag = wxALIGN_TOP | wxALIGN_LEFT
        elif self.alignmentEnum == 'alignTopRight':
            flag = wxALIGN_TOP | wxALIGN_RIGHT
        elif self.alignmentEnum == 'alignBottomLeft':
            flag = wxALIGN_BOTTOM | wxALIGN_LEFT
        elif self.alignmentEnum == 'alignBottomRight':
            flag = wxALIGN_BOTTOM | wxALIGN_RIGHT
        return flag

    def Calculate_wxBorder (self):
        border = 0
        spacerRequired = False
        for edge in (self.border.top, self.border.left, self.border.bottom, self.border.right):
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


class BoxContainer(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        if self.orientationEnum == 'Horizontal':
            orientation = wxHORIZONTAL
        else:
            orientation = wxVERTICAL

        sizer = wxBoxSizer(orientation)
        sizer.SetMinSize((self.minimumSize.width, self.minimumSize.height))

        if self.parentBlock: 
            panel = wxPanel(parentWindow, -1)
            panel.SetSizer(sizer)
            self.getParentBlock(parentWindow).addToContainer(parent, panel, 1, 
                                            self.Calculate_wxFlag(), 
                                            self.Calculate_wxBorder())
            return panel, sizer, panel
        else:
            parent.SetSizer(sizer)
            return parent, sizer, parent
                
    def addToContainer(self, parent, child, weight, flag, border):
        parent.Add(child, int(weight), flag, border)
        
    def removeFromContainer(self, parent, child):
        parent.Remove(child)
        child.Destroy()
        parent.Layout()


class EmbeddedContainer(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        sizer = wxBoxSizer(wxHORIZONTAL)
        panel = wxPanel(parentWindow, -1)
        panel.SetSizer(sizer)
        self.getParentBlock(parentWindow).addToContainer(parent, panel, 1,
                                                         self.Calculate_wxFlag(),
                                                         self.Calculate_wxBorder())
        newChild = Globals.repository.find (self.contentSpec.data)
        if newChild:
            newChild.parentBlock = self
            return panel, sizer, panel
        return None, None, None

    def addToContainer (self, parent, child, weight, flag, border):
        parent.Add(child, int(weight), flag, border)
        
    def removeFromContainer(self, parent, child):
        parent.Remove (child)
        child.Destroy ()
        parent.Layout ()
    
    def OnSelectionChangedEvent (self, notification):
        # @@@ This isn't working yet.  For some reason, switching parcels
        #  causes an infinite number of UpdateUI notifications to be posted.
        return
        node = notification.data['node']
        name = node.treeList.GetItemText(node.nodeId)
        oldChild = Globals.repository.find (self.contentSpec.data)
        wxOldChild = Globals.association [oldChild.getUUID()]
        parent = wxOldChild.GetContainingSizer ()
        parentWindow = wxOldChild.GetParent()
        
        self.removeFromContainer(parent, wxOldChild)
        oldChild.parentBlock = None
        
        if name == "Demo":
            self.contentSpec.data = 'parcels/OSAF/views/demo/TabBox'
        else:
            self.contentSpec.data = 'parcels/OSAF/views/repositoryviewer/RepositoryBox'        
        
        newChild = Globals.repository.find (self.contentSpec.data)
        if newChild:
            newChild.parentBlock = self
            newChild.render (parent, parentWindow)
        
            
class Button(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        id = 0
        if self.hasAttributeValue ("clicked"):  # Repository bug/feature -- DJA
            id = self.clicked.getwxID()

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
            assert (False)

        self.getParentBlock(parentWindow).addToContainer(parent, button, self.stretchFactor,
                              self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return button, None, None


class Choice(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        choice = wxChoice(parentWindow, -1, 
                              wxDefaultPosition,
                              (self.minimumSize.width, self.minimumSize.height),
                              self.choices)
        self.getParentBlock(parentWindow).addToContainer(parent, choice, self.stretchFactor, 
                              self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return choice, None, None


class ComboBox(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        comboBox = wxComboBox(parentWindow, -1, self.selection, 
                              wxDefaultPosition,
                              (self.minimumSize.width, self.minimumSize.height),
                              self.choices)
        self.getParentBlock(parentWindow).addToContainer(parent, comboBox, self.stretchFactor, 
                              self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return comboBox, None, None

    
class EditText(RectangularChild):
    def __init__(self, *arguments, **keywords):
        super (EditText, self).__init__ (*arguments, **keywords)

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

        if self.textStyleEnum == "RichText":
            style |= wxTE_RICH2

        if self.readOnly:
            style |= wxTE_READONLY

        editText = wxTextCtrl (parentWindow,
                               -1,
                               "",
                               wxDefaultPosition,
                               (self.minimumSize.width, self.minimumSize.height),
                               style, name=self._name)

        editText.SetFont(Font (self.characterStyle))
        self.getParentBlock(parentWindow).addToContainer(parent,
                                                         editText,
                                                         self.stretchFactor, 
                                                         self.Calculate_wxFlag(),
                                                         self.Calculate_wxBorder())
        return editText, None, None


class HTML(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        htmlWindow = wxHtmlWindow(parentWindow,
                                  Block.getwxID(self),
                                  wxDefaultPosition,
                                  (self.minimumSize.width, self.minimumSize.height))
        if self.url:
            htmlWindow.LoadPage(self.url)
        
        self.getParentBlock(parentWindow).addToContainer(parent,
                                                         htmlWindow,
                                                         self.stretchFactor,
                                                         self.Calculate_wxFlag(),
                                                         self.Calculate_wxBorder())
        return htmlWindow, None, None


class List(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        return None, None, None


class RadioBox(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        id = 0
        if self.hasAttributeValue ("selectionChanged"):  # Repository bug/feature -- DJA
            id = self.selectionChanged.getwxID()

        if self.radioAlignEnum == "Across":
            dimension = wxRA_SPECIFY_COLS
        elif self.radioAlignEnum == "Down":
            dimension = wxRA_SPECIFY_ROWS
        elif __debug__:
            assert (False)
                                    
        radioBox = wxRadioBox(parentWindow, -1, self.title,
                              wxDefaultPosition, 
                              (self.minimumSize.width, self.minimumSize.height),
                              self.choices, self.itemsPerLine, dimension)
        self.getParentBlock(parentWindow).addToContainer(parent, radioBox, self.stretchFactor, 
                              self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return radioBox, None, None


class ScrolledWindow(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        return None, None, None


class wxSplitWindow(wxSplitterWindow):

    def __init__(self, *arguments, **keywords):
        wxSplitterWindow.__init__ (self, *arguments, **keywords)
        EVT_SPLITTER_SASH_POS_CHANGED(self, self.GetId(), self.OnSplitChanged)
 
    def OnSplitChanged(self, event):
        counterpart = Globals.repository.find (self.counterpartUUID)
        width, height = self.GetSizeTuple()
        position = float (event.GetSashPosition())
        splitMode = self.GetSplitMode()
        if splitMode == wxSPLIT_HORIZONTAL:
            counterpart.splitPercentage = position / height
        elif splitMode == wxSPLIT_VERTICAL:
            counterpart.splitPercentage = position / width

    def OnSize(self, event):
        """
          Calling Skip causes wxWindows to continue processing the event, which
        will cause the parent class to get a crack at the event.
        """
        event.Skip()
        counterpart = Globals.repository.find (self.counterpartUUID)
        counterpart.size.width = self.GetSize().x
        counterpart.size.height = self.GetSize().y
        counterpart.setDirty()   # Temporary repository hack -- DJA


class SplitWindow(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        splitWindow = wxSplitWindow(parentWindow,
                                    Block.getwxID(self), 
                                    wxDefaultPosition,
                                    (self.size.width, self.size.height),
                                    style=wxSP_3D|wxSP_LIVE_UPDATE|wxNO_FULL_REPAINT_ON_RESIZE)
        self.getParentBlock(parentWindow).addToContainer(parent, splitWindow, self.stretchFactor, 
                              self.Calculate_wxFlag(), self.Calculate_wxBorder())
        """
          Wire up onSize after __init__ has been called, otherwise it will
        call onSize
        """
        EVT_SIZE(splitWindow, splitWindow.OnSize)
        return splitWindow, splitWindow, splitWindow
                
    def addToContainer(self, parent, child, weight, flag, border):
        if not hasattr(self, 'childrenToAdd'):
            self.childrenToAdd = []
        self.childrenToAdd.append(child)
        
    def removeFromContainer(self, parent, child):
        # @@@ Must be implemented
        pass
        
    def handleChildren(self, window):
        assert (len (self.childrenToAdd) == 2)
        width, height = window.GetSizeTuple()
        assert self.splitPercentage >= 0.0 and self.splitPercentage < 1.0
        if self.orientationEnum == "Horizontal":
            window.SplitHorizontally(self.childrenToAdd[0],
                                     self.childrenToAdd[1],
                                     int (round (height * self.splitPercentage)))
        else:
            window.SplitVertically(self.childrenToAdd[0],
                                   self.childrenToAdd[1],
                                   int (round (width * self.splitPercentage)))
        return window
   

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
        self.getParentBlock(parentWindow).addToContainer(parent, staticText,
                                                         self.stretchFactor,
                                                         self.Calculate_wxFlag(),
                                                         self.Calculate_wxBorder())
        return staticText, None, None


class TabbedContainer(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        id = 0
        if self.hasAttributeValue ("selectionChanged"):  # Repository bug/feature -- DJA
            id = self.selectionChanged.getwxID()
            
        if self.tabPosEnum == "Top":
            style = 0
        elif self.tabPosEnum == "Bottom":
            style = wxNB_BOTTOM
        elif self.tabPosEnum == "Left":
            style = wxNB_LEFT
        elif self.tabPosEnum == "Right":
            style = wxNB_RIGHT
        elif __debug__:
            assert (False)
            
        tabbedContainer = wxNotebook(parentWindow, id, 
                                    wxDefaultPosition,
                                    (self.minimumSize.width, self.minimumSize.height),
                                     style = style)
        self.getParentBlock(parentWindow).addToContainer(parent, tabbedContainer, self.stretchFactor, 
                              self.Calculate_wxFlag(), self.Calculate_wxBorder())
        return tabbedContainer, tabbedContainer, tabbedContainer
                
    def addToContainer(self, parent, child, weight, flag, border):
        if not hasattr(self, 'childrenToAdd'):
            self.childrenToAdd = []
        self.childrenToAdd.append(child)
        
    def removeFromContainer(self, parent, child):
        # @@@ Must be implemented
        pass

    def handleChildren(self, window):
        if len (self.childrenToAdd) > 0:
            childNameIndex = 0
            for child in self.childrenToAdd:
                window.AddPage(child, self.tabNames[childNameIndex])
                childNameIndex = childNameIndex + 1

    def OnChooseTabEvent (self, notification):
        tabbedContainer = Globals.association[self.getUUID()]
        choice = notification.event.choice
        for index in xrange (tabbedContainer.GetPageCount()):
            if tabbedContainer.GetPageText(index) == choice:
                tabbedContainer.SetSelection (index)
                break


class Toolbar(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        toolbar = wxToolBar(Globals.wxApplication.mainFrame, -1)
        Globals.wxApplication.mainFrame.SetToolBar(toolbar)
        return toolbar, None, None
        

class ToolbarItem(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        # @@@ Must use self.toolbarLocation rather than wxMainFrame.GetToolBar()
        toolbar = Globals.wxApplication.mainFrame.GetToolBar()
        if self.toolbarItemKind == 'Button':
            bitmap = wxImage (self.bitmap, wxBITMAP_TYPE_BMP).ConvertToBitmap()
            toolbar.AddSimpleTool (0, bitmap, self.title, self.statusMessage)
        elif self.toolbarItemKind == 'Separator':
            toolbar.AddSeparator()
        elif self.toolbarItemKind == 'Check':
            pass
        elif self.toolbarItemKind == 'Radio':
            pass
        elif self.toolbarItemKind == 'Text':
            textBox = wxTextCtrl (toolbar, -1, "", wxDefaultPosition, wxSize(300,-1), wxTE_PROCESS_ENTER)
            textBox.SetName(self.title)
            toolbar.AddControl (textBox)
        elif __debug__:
            assert (False)

        toolbar.Realize()

        return None, None, None


class Tree(RectangularChild):
    def renderOneBlock (self, parent, parentWindow):
        return None, None, None


class TreeNode:
    def __init__(self, nodeId, treeList):
        self.nodeId = nodeId
        self.treeList = treeList

    def AddChildNode (self, data, names, hasChildren):
        childNodeId = self.treeList.AppendItem (self.nodeId,
                                                names.pop(0),
                                                -1,
                                                -1,
                                                wxTreeItemData (data))
        index = 1
        for name in names:
            self.treeList.SetItemText (childNodeId, name, index)
            index += 1

        self.treeList.SetItemHasChildren (childNodeId, hasChildren)

    def AddRootNode (self, data, names, hasChildren):
        rootNodeId = self.treeList.AddRoot (names.pop(0), -1, -1, wxTreeItemData (data))
        index = 1
        for name in names:
            SetItemText (rootNodeId, name, index)
            index += 1

        self.treeList.SetItemHasChildren (rootNodeId, hasChildren)
                                             
    def GetData (self):
        if self.nodeId:
            return self.treeList.GetPyData (self.nodeId)
        else:
            return None        


class wxTreeList(wxTreeListCtrl):

    def __init__(self, *arguments, **keywords):
        wxTreeListCtrl.__init__ (self, *arguments, **keywords)
        EVT_TREE_ITEM_EXPANDING(self, self.GetId(), self.OnExpanding)
        EVT_TREE_ITEM_COLLAPSING(self, self.GetId(), self.OnCollapsing)
        EVT_LIST_COL_END_DRAG(self, self.GetId(), self.OnColumnDrag)
        EVT_TREE_SEL_CHANGED(self, self.GetId(), self.OnItemActivated)
 
    def OnExpanding(self, event):
        """
          Load the items in the tree only when they are visible.
        """
        arguments = {'node':TreeNode (event.GetItem(), self),
                     'type':'Normal'}
        event = Globals.repository.find('//parcels/OSAF/framework/blocks/Events/GetTreeListData')
        notification = Notification(event, None, None)
        notification.SetData(arguments)
        Globals.notificationManager.PostNotification (notification)

    def OnCollapsing(self, event):
        self.DeleteChildren (event.GetItem())

    def OnColumnDrag(self, event):
        counterpart = Globals.repository.find (self.counterpartUUID)
        columnIndex = event.GetColumn()
        counterpart.columnWidths [columnIndex] = self.GetColumnWidth (columnIndex)

    def OnItemActivated(self, event):
        arguments = {'node':TreeNode (event.GetItem(), self),
                     'type':'Normal'}
        event = Globals.repository.find('//parcels/OSAF/framework/blocks/Events/SelectionChanged')
        notification = Notification(event, None, None)
        notification.SetData(arguments)
        Globals.notificationManager.PostNotification (notification)
        
        
class TreeList(RectangularChild):
    def renderOneBlock(self, parent, parentWindow):
        treeList = wxTreeList(parentWindow, Block.getwxID(self), style = self.Calculate_wxStyle())
        info = wxTreeListColumnInfo()
        for x in range(len(self.columnHeadings)):
            info.SetText(self.columnHeadings[x])
            info.SetWidth(self.columnWidths[x])
            treeList.AddColumnInfo(info)
        self.getParentBlock(parentWindow).addToContainer(parent, treeList, 1, self.Calculate_wxFlag(), self.Calculate_wxBorder())
        """
          We need to send a GetTreeListData event to the tree list to fill out it's root
        item. Unfortunately, it isn't completely wired up because we haven't set the focus
        and assigned the counterpartUUID, which are necessary for the event dispatch to
        work. So we'll go the the extra work in this case to get it wired up before sending
        the event. I couldn't think of a better solution -- DJA
        """
        treeList.SetFocus()
        treeList.counterpartUUID = self.getUUID()
        arguments = {'node':TreeNode (None, treeList),
                     'type':'Normal'}
        event = Globals.repository.find('//parcels/OSAF/framework/blocks/Events/GetTreeListData')
        notification = Notification(event, None, None)
        notification.SetData(arguments)
        Globals.notificationManager.PostNotification (notification)

        return treeList, None, None

    def Calculate_wxStyle (self):
        style = wxTR_DEFAULT_STYLE
        if self.hideRoot:
            style |= wxTR_HIDE_ROOT
        if self.noLines:
            style |= wxTR_NO_LINES
        if self.useButtons:
            style |= wxTR_HAS_BUTTONS
        else:
            style |= wxTR_NO_BUTTONS
        return style


class RepositoryTreeList(TreeList):
    def OnGetTreeListDataEvent (self, notification):
        node = notification.data['node']
        item = node.GetData()
        if item:
            for child in item:
                names = [child.getItemName()]
                names.append (str(child.getItemDisplayName()))
                try:
                    names.append (child.kind.getItemName())
                except AttributeError:
                    names.append ('(kindless)')
                names.append (str(child.getUUID()))
                names.append (str(child.getItemPath()))
                node.AddChildNode (child, names, child.hasChildren())
        else:
            node.AddRootNode (Globals.repository, ['//'], True)

    def OnGoToURI (self, notification):
        wxTreeListWindow = Globals.association[self.getUUID()]
        #wxTreeListWindow.GoToURI (notification.data['URI'])

        
class Sidebar(TreeList):
    def OnGetTreeListDataEvent (self, notification):
        node = notification.data['node']
        item = node.GetData()
        if item:
            for child in item:
                node.AddChildNode (None, [child], false)
        else:
            node.AddRootNode (['Repository Viewer', 'Demo'], ['Views'], true)
    
    def OnSelectionChangedEvent (self, notification):
        node = notification.data['node']
        name = node.treeList.GetItemText(node.nodeId)
        arguments = {'parcelName':name, 'type':'Normal'}
        event = Globals.repository.find('//parcels/OSAF/views/demo/SwitchEmbeddedChild')
        notification = Notification(event, None, None)
        notification.SetData(arguments)
        Globals.notificationManager.PostNotification (notification)

        