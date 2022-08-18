# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import copy
import gc
import glob
import math
import mfeats
import mutagen
import os
import re
import stat
import threading
import time
import wx

from macroboxlib import InnerList
from macroboxlib import MakeMusicFileItem
from macroboxlib import SUPPORTED_PLAYLIST_TYPE
from macroboxlib import SUPPORTED_AUDIO_TYPE
from operator import itemgetter
from utilities import Struct


threadListLock = threading.Lock()


class ListBoxListDnD(wx.FileDropTarget):

    def __init__(self, parent):
        wx.FileDropTarget.__init__(self)
        self.parent = parent
        self.dropTimer = 0
        self.onClient = False
        self.itemDrag = False
        self.importing = False
        self.insertItemIdx = None

    def OnEnter(self, x, y, d):
        self.onClient = True
        self.parent.onClient = True
        return d

    def OnLeave(self):
        self.onClient = False
        self.parent.onClient = False

    def OnDragOver(self, x, y, d):
        self.onClient = True
        self.parent.onClient = True
        return d

    def OnDropFiles(self, x, y, inpaths):
        self.onClient = False
        if self.parent.parent.IsFilteredAll():
            return 0
        fileImport = self.importing
        insertItemIdx = self.parent.parent.GetInsertItemIdx(y)
        self.importing = False
        # print(self.importing)
        orderIdx = self.parent.parent.GetColumnKeyToIdx('order')
        isInsertable = self.parent.parent.GetLastSortedColumn()[0] == orderIdx
        if isInsertable and insertItemIdx is None:
            return 0
        if fileImport is False:
            self.DropFromInside(insertItemIdx)
        elif fileImport:
            self.DropFromOutside(inpaths, insertItemIdx)
        return 0

    def DropFromInside(self, insertItemIdx):
        selectedList = self.parent.parent.selectedList
        orderIdx = self.parent.parent.GetColumnKeyToIdx('order')
        if orderIdx != self.parent.parent.GetLastSortedColumn()[0]:
            return
        selectedItems = sorted(self.parent.parent.GetSelectedItems(selectedList))
        offset = insertItemIdx
        selectedItemsData = []
        self.parent.parent.SetListLock(selectedList)

        for i in selectedItems[::-1]:
            if i < insertItemIdx:
                offset = offset - 1
            selectedItemsData.insert(0, self.parent.parent.innerList[selectedList].items.pop(i))

        self.parent.parent.innerList[selectedList].items\
            = self.parent.parent.innerList[selectedList].items[:offset] +\
            selectedItemsData + self.parent.parent.innerList[selectedList].items[offset:]

        for i, v in enumerate(self.parent.parent.innerList[selectedList].items):
            v = list(v)
            v[orderIdx] = i + 1
            self.parent.parent.innerList[selectedList].items[i] = tuple(v)

        self.parent.parent.innerList[selectedList].selectedItems = list(range(offset, offset + len(selectedItems)))
        self.parent.parent.SetListUnLock(selectedList)

    def DropFromOutside(self, inpaths, insertItemIdx=-1,
                        selectedList=None, permit_duplicated=False, filtered=False):
        # if insertItemIdx is -1, append / else insert with insertItemIdx
        if selectedList is None:
            selectedList = self.parent.parent.selectedList
        playlistsIdx = []
        for i, v in enumerate(inpaths):
            file_type = os.path.splitext(v)[1]
            if file_type == '':
                continue
            if file_type[1:].lower() in SUPPORTED_PLAYLIST_TYPE:
                playlistsIdx += [i]
        if playlistsIdx != []:
            for i in playlistsIdx[::-1]:
                m3u_paths = audio.read_m3u(inpaths[i])
                inpaths = inpaths[:i] + m3u_paths + inpaths[i + 1:]

        threadList = threading.Thread(
            target=self.ImportFiles, name='list',
            args=(inpaths, insertItemIdx, selectedList, permit_duplicated, filtered))
        threadList.start()

    def ImportFiles(self, inpaths, insertItemIdx=-1,
                    selectedList=None, permit_duplicated=False, filtered=False):
        # self.parent.parent.parent.SetCursorWAIT()
        jobsegSize = 100
        # If blocking is 0, the thread will return
        # If blocking is 1, the thread will block and wait
        threadListLock.acquire(1)
        if selectedList is None:
            selectedList = self.parent.parent.selectedList
        self.parent.parent.SetListLock(selectedList)

        extended_paths = []
        for path in inpaths:
            if os.path.isfile(path) is False and os.path.isdir(path) is False:
                continue
            stats = os.stat(path)
            if stats[stat.ST_MODE] == 16895:
                extended_paths += self.SearchPatternIncludeSub(path, u'*')
            else:
                extended_paths.append(path)

        pathIdx = self.parent.parent.GetColumnKeyToIdx('path', selectedList)
        orderIdx = self.parent.parent.GetColumnKeyToIdx('order', selectedList)
        sortedColumnIdx = self.parent.parent.GetLastSortedColumn(selectedList)[0]

        isOrdered = sortedColumnIdx == orderIdx
        # If insertItemIdx is -1, inpaths will be appended
        # If insertItemIdx is not -1, inpaths will be inserted
        # print len(extended_paths)

        imported_count = 0
        already_have_count = 0

        if isOrdered and insertItemIdx != -1:
            isInsertable = True
            order = insertItemIdx + 1
        else:
            insertItemIdx = 0
            isInsertable = False
            order = self.parent.parent.GetItemsLength(selectedList) + 1

        for segcnt in range(0, len(extended_paths), jobsegSize):

            innerListSeg = []
            for path in extended_paths[segcnt:segcnt + jobsegSize]:

                if permit_duplicated is False:
                    if list(filter(lambda v: v[pathIdx] == path,
                                   self.parent.parent.innerList[selectedList].items)) != []:
                        already_have_count += 1
                        continue
                columns = self.parent.parent.innerList[selectedList].columns
                item = MakeMusicFileItem(path, order, columns)
                try:
                    item = MakeMusicFileItem(path, order, columns)
                except Exception:
                    item = None
                if item is None:
                    continue
                order += 1
                imported_count += 1

                innerListSeg.append(tuple(item))

            selectedItems = self.parent.parent.GetSelectedItems(selectedList)

            if isInsertable:

                for i, v in enumerate(self.parent.parent.innerList[selectedList].items[insertItemIdx:]):
                    v = list(v)
                    v[orderIdx] = v[orderIdx] + len(innerListSeg)
                    self.parent.parent.innerList[selectedList].items[insertItemIdx + i] = tuple(v)
                self.parent.parent.innerList[selectedList].items\
                    = self.parent.parent.innerList[selectedList]\
                    .items[:insertItemIdx] + innerListSeg + self.parent.parent\
                    .innerList[selectedList].items[insertItemIdx:]

                for i in range(len(selectedItems)):
                    if selectedItems[i] >= insertItemIdx:
                        selectedItems[i] = selectedItems[i] + len(innerListSeg)
                self.parent.parent.innerList[selectedList].selectedItems = selectedItems

            else:

                self.parent.parent.innerList[selectedList].items\
                    = self.parent.parent.innerList[selectedList].items + innerListSeg

            self.parent.parent.SortColumn(sortedColumnIdx, selectedList)
            self.parent.parent.SortColumn(sortedColumnIdx, selectedList)
            insertItemIdx = order - 1
            # imported_count += 1
            self.parent.parent.reInitBuffer = True
        try:
            del extended_paths, stats, innerListSeg
        except Exception:
            pass

        # print(len(self.parent.parent.innerList[0].items))

        threadListLock.release()
        self.dropTimer = 0
        self.itemDrag = False
        self.insertItemIdx = None
        self.parent.parent.reInitBuffer = True
        self.parent.parent.SetListUnLock(selectedList)
        # self.parent.parent.parent.Event.SetCursorARROW()
        self.parent.parent.parent.MFEATS.AutoAnalyzer()
        gc.collect(2)
        # collected = gc.collect(2)
        message = ['Imported %d tracks' % imported_count]
        if already_have_count > 0:
            message += ['%d tracks already in the playlist' % already_have_count]
            self.parent.parent.parent.StatusBox.alarm_color = 'red'
        else:
            self.parent.parent.parent.StatusBox.alarm_color = 'blue'
        message = ' / '.join(message)
        self.parent.parent.parent.StatusBox.alarm_timer = 0
        self.parent.parent.parent.StatusBox.alarm = message

    def SearchPatternIncludeSub(self, filepath, pattern='*'):
        # filepath = unicode(filepath)
        # pattern = unicode(pattern)
        retlist = glob.glob(os.path.join(filepath, pattern))
        findlist = os.listdir(filepath)
        for f in findlist:
            next = os.path.join(filepath, f)
            if os.path.isdir(next):
                retlist += self.SearchPatternIncludeSub(next, pattern)
            # else: retlist += [next]
        return retlist


class ListControl():

    def __init__(self, parent):
        pass

    def LeftDoubleClick(self, event):
        item = self.GetSelectedItem()
        if item is None:
            return
        self.parent.PlayBox.OnStop()
        item = self.innerList[self.selectedList].items[item]
        self.parent.PlayBox.cue.path = item[self.GetColumnKeyToIdx('path')]
        self.parent.PlayBox.cue.order = item[self.GetColumnKeyToIdx('order')]
        self.parent.PlayBox.cue.listId = self.innerList[self.selectedList].Id
        self.parent.PlayBox.OnPlay()

    def SearchItemIdxByKey(self, key, query, selectedList=None, selectedTab=None):
        if selectedList is None:
            selectedList = self.selectedList
        keyIdx = self.parent.ListBox[0].GetColumnKeyToIdx(key, selectedList)
        return [i for i, v in enumerate(
                self.parent.ListBox[0].innerList[selectedList].items)
                if v[keyIdx] == query]

    def SetListLock(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].lock = True
        self.parent.SetCursor(wx.Cursor(wx.CURSOR_WAIT))

    def SetListUnLock(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].lock = False
        self.parent.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

    def SetListUnLockAll(self):
        for listIdx in range(len(self.innerList)):
            self.innerList[listIdx].lock = False
        self.parent.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

    def IsListLocked(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].lock

    def IsAnyListLocked(self):
        for listIdx in range(len(self.innerList)):
            if self.innerList[listIdx].lock is True:
                return True
        return False

    def GetTotalItemsNumber(self):
        total_number = 0
        for listIdx in range(len(self.innerList)):
            if self.IsFiltered(listIdx) is False:
                total_number += len(self.innerList[listIdx].items)
            else:
                total_number += len(self.innerList[listIdx].filterCache)
        return total_number

    def CheckItemsConsistencyAll(self):
        self.SetListLock()
        self.consistency_check_counter = 0
        self.consistency_check_stop = False
        self.consistency_check_error_counter = 0
        self.consistency_check_error_items = list()
        for listIdx in range(len(self.innerList)):
            isFiltered = self.IsFiltered(listIdx)
            columns = self.innerList[listIdx].columns
            # mdxIdx = self.GetColumnKeyToIdx('mdx', listIdx)
            pathIdx = self.GetColumnKeyToIdx('path', listIdx)
            orderIdx = self.GetColumnKeyToIdx('order', listIdx)
            statusIdx = self.GetColumnKeyToIdx('status', listIdx)
            for itemIdx in range(len(self.innerList[listIdx].items)):
                path = self.innerList[listIdx].items[itemIdx][pathIdx]
                order = self.innerList[listIdx].items[itemIdx][orderIdx]
                item = MakeMusicFileItem(path, order, columns)
                if item is None:
                    item = list(self.innerList[listIdx].items[itemIdx])
                    item[statusIdx] = 'error'
                    if isFiltered is False:
                        self.consistency_check_error_counter += 1
                        self.consistency_check_error_items += [path]
                self.innerList[listIdx].items[itemIdx] = tuple(item)
                if isFiltered is False:
                    self.consistency_check_counter += 1
                if self.consistency_check_stop:
                    self.SetListUnLock()
                    return
            if isFiltered is False:
                continue
            for cacheItemIdx in range(len(self.innerList[listIdx].filterCache)):
                path = self.innerList[listIdx].filterCache[cacheItemIdx][pathIdx]
                order = self.innerList[listIdx].filterCache[cacheItemIdx][orderIdx]
                item = MakeMusicFileItem(path, order, columns)
                if item is None:
                    item = list(self.innerList[listIdx].filterCache[cacheItemIdx])
                    item[statusIdx] = 'error'
                    self.consistency_check_error_counter += 1
                    self.consistency_check_error_items += [path]
                self.innerList[listIdx].filterCache[cacheItemIdx] = tuple(item)
                self.consistency_check_counter += 1
        self.SetListUnLock()

    def CheckItemsConsistency(self, itemsIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.SetListLock()
        columns = self.innerList[selectedList].columns
        # mdxIdx = self.GetColumnKeyToIdx('mdx', selectedList)
        pathIdx = self.GetColumnKeyToIdx('path', selectedList)
        orderIdx = self.GetColumnKeyToIdx('order', selectedList)
        statusIdx = self.GetColumnKeyToIdx('status', selectedList)
        for itemIdx in itemsIdx:
            path = self.innerList[selectedList].items[itemIdx][pathIdx]
            order = self.innerList[selectedList].items[itemIdx][orderIdx]
            item = MakeMusicFileItem(path, order, columns)
            if item is None:
                item = list(self.innerList[selectedList].items[itemIdx])
                item[statusIdx] = 'error'
            self.innerList[selectedList].items[itemIdx] = tuple(item)
        self.SetListUnLock()

    def CheckItemConsistencyByPathAll(self, path):
        for listIdx in range(len(self.innerList)):
            self.CheckItemConsistencyByPath(path, listIdx)

    def CheckItemConsistencyByPath(self, path, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.SetListLock()
        columns = self.innerList[selectedList].columns
        # mdxIdx = self.GetColumnKeyToIdx('mdx', selectedList)
        pathIdx = self.GetColumnKeyToIdx('path', selectedList)
        orderIdx = self.GetColumnKeyToIdx('order', selectedList)
        statusIdx = self.GetColumnKeyToIdx('status', selectedList)
        itemIdx = [i for i in range(len(self.innerList[selectedList].items))
                   if self.innerList[selectedList].items[i][pathIdx] == path]
        if itemIdx == []:
            self.SetListUnLock()
            return
        itemIdx = itemIdx[0]
        mdx = audio.makemdx(path)
        item = list(self.innerList[selectedList].items[itemIdx])
        order = self.innerList[selectedList].items[itemIdx][orderIdx]
        if mdx is None:
            item[statusIdx] = 'error'
        else:
            item = MakeMusicFileItem(path, order, columns)
        self.innerList[selectedList].items[itemIdx] = tuple(item)
        self.SetListUnLock()

    def CheckAnalyzingStatus(self):
        for listIdx in range(len(self.innerList)):
            columns = self.innerList[listIdx].columns
            # mdxIdx = self.GetColumnKeyToIdx('mdx', listIdx)
            pathIdx = self.GetColumnKeyToIdx('path', listIdx)
            orderIdx = self.GetColumnKeyToIdx('order', listIdx)
            statusIdx = self.GetColumnKeyToIdx('status', listIdx)
            for itemIdx in range(len(self.innerList[listIdx].items)):
                if self.innerList[listIdx].items[itemIdx][statusIdx] in ('', 'analyzing'):
                    path = self.innerList[listIdx].items[itemIdx][pathIdx]
                    resp = mfeats.getby_key_value('mdx', audio.makemdx(path))
                    if resp is not None:
                        order = self.innerList[listIdx].items[itemIdx][orderIdx]
                        item = MakeMusicFileItem(path, order, columns)
                        self.innerList[listIdx].items[itemIdx] = tuple(item)

    def SetListItemsValueWhereColumnKey(self, where, columnKeyValue):
        for listIdx in range(len(self.innerList)):
            self.SetItemsValueWhereColumnKey(where, columnKeyValue, listIdx)

    def SetItemsValueWhereColumnKey(self, where, columnKeyValue, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        columnIdx = self.GetColumnKeyToIdx(columnKeyValue[0], selectedList)
        for itemIdx in self.GetItemsIdxByColumnKeyValue(
                where[0], where[1], selectedList):
            item = list(self.innerList[selectedList].items[itemIdx])
            item[columnIdx] = columnKeyValue[1]
            self.innerList[selectedList].items[itemIdx] = tuple(item)

        self.SetCacheValueWhereColumnKey(where, columnKeyValue, selectedList)

    def SetCacheValueWhereColumnKey(self, where, columnKeyValue, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        columnIdx = self.GetColumnKeyToIdx(columnKeyValue[0], selectedList)
        for cacheIdx in self.GetCacheIdxByColumnKeyValue(
                where[0], where[1], selectedList):
            item = list(self.innerList[selectedList].filterCache[cacheIdx])
            item[columnIdx] = columnKeyValue[1]
            self.innerList[selectedList].filterCache[cacheIdx] = tuple(item)

    def GetListItemsIdxByColumnKeyValue(self, columnKey, value):
        listItemsIdx = []
        for listIdx in range(len(self.innerList)):
            itemsIdx = self.GetItemsIdxByColumnKeyValue(columnKey, value, listIdx)
            for itemIdx in itemsIdx:
                listItemsIdx += [(listIdx, itemIdx)]
        return listItemsIdx

    def GetListCacheIdxByColumnKeyValue(self, columnKey, value):
        listCacheIdx = []
        for listIdx in range(len(self.innerList)):
            cacheIdx = self.GetCacheIdxByColumnKeyValue(columnKey, value, listIdx)
            for itemIdx in cacheIdx:
                listCacheIdx += [(listIdx, itemIdx)]
        return listCacheIdx

    def GetItemsIdxByColumnKeyValue(self, columnKey, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        columnIdx = self.GetColumnKeyToIdx(columnKey, selectedList)
        return [i for i, v in enumerate(
                self.innerList[selectedList].items) if v[columnIdx] == value]

    def GetCacheIdxByColumnKeyValue(self, columnKey, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered(selectedList) is False:
            return []
        columnIdx = self.GetColumnKeyToIdx(columnKey, selectedList)
        return [i for i, v in enumerate(
                self.innerList[selectedList].filterCache) if v[columnIdx] == value]

    def RenameFileByItemIdx(self, itemIdx, newPath, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        oldPath = self.GetItemValueByColumnKey(itemIdx, 'path', selectedList)
        if newPath == oldPath:
            return False
        try:
            os.rename(oldPath, newPath)
        except Exception:
            return False

        newMDX = audio.makemdx(newPath)
        newFilename = newPath.split(os.path.sep)[-1]
        newFilename = os.path.splitext(newFilename)[0]
        key_values = [('path', newPath), ('mdx', newMDX)]
        oldMDX = self.GetItemValueByColumnKey(itemIdx, 'mdx', selectedList)
        mfeats.update_many_key_values(('mdx', oldMDX), key_values)
        self.SetListItemsValueWhereColumnKey(('mdx', oldMDX), ('mdx', newMDX))
        self.SetListItemsValueWhereColumnKey(('mdx', newMDX), ('path', newPath))
        self.SetListItemsValueWhereColumnKey(('mdx', newMDX), ('filename', newFilename))
        self.parent.MFEATS.ResetItemValue(oldPath, newPath)
        return True

    def IsID3TAGColumnByColumnIdx(self, columnIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.innerList[selectedList].columns[columnIdx].id3 is not None:
            return True
        return False

    def RenameID3TAGByColumnItemIdx(
            self, columnIdx, itemIdx, newValue, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        columnKey = self.GetColumnIdxToKey(columnIdx, selectedList)
        path = self.GetItemValueByColumnKey(itemIdx, 'path', selectedList)
        oldValue = self.GetItemValueByColumnKey(itemIdx, columnKey, selectedList)
        id3Key = self.innerList[selectedList].columns[columnIdx].id3
        if newValue == oldValue:
            return False
        try:
            mutagen_mp3 = mutagen.mp3.MP3(path)
            attr = getattr(mutagen.id3, id3Key)
            mutagen_mp3[id3Key] = attr(encoding=3, text=[newValue])
            mutagen_mp3.save()
        except Exception:
            return False
        self.SetListItemsValueWhereColumnKey(
            ('path', path), (columnKey, newValue))
        if columnKey in ('tempo', 'key'):
            key_values = [(columnKey, newValue)]
            mdx = self.GetItemValueByColumnKey(itemIdx, 'mdx', selectedList)
            mfeats.update_many_key_values(('mdx', mdx), key_values)
        return True

    # Filter Control

    def FilterItems(self, key, query, ignore_case=True, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.InitSelectedItems(selectedList)
        keyIdx = self.GetColumnKeyToIdx(key, selectedList)
        self.innerList[selectedList].filterQuery = query
        if ignore_case:
            query = query.lower()
        query = query.split(' ')
        query = [v for v in query if v != '']
        queryLength = len(query)
        self.innerList[selectedList].items\
            = filter(lambda v: len([x for x in query
                                    if x in v[keyIdx].lower()]) == queryLength,
                     self.innerList[selectedList].filterCache)

    def FilterItemsExtended(self, query, ignore_case=True, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if ':' in query:
            query = query.split(':')
            key = query[0]
            query = query[1]
        else:
            key = 'file'
        self.FilterItems(key, query, ignore_case, selectedList)

    def GetFilterQuery(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].filterQuery

    def SetFilterQuery(self, query, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].filterQuery = query

    def IsFiltered(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.innerList[selectedList].filterCache is None:
            return False
        return True

    def SetFilterOnAll(self):
        for listIdx in range(len(self.innerList)):
            self.SetFilterOn(listIdx)

    def IsFilteredAll(self):
        for listIdx in range(len(self.innerList)):
            if self.IsFiltered(listIdx) is False:
                return False
        return True

    def FilterItemsAll(self, key, query, ignore_case=True):
        for listIdx in range(len(self.innerList)):
            self.FilterItems(key, query,
                             ignore_case=ignore_case, selectedList=listIdx)

    def SetFilterOffAll(self):
        for listIdx in range(len(self.innerList)):
            self.SetFilterOff(listIdx)
        self.parent.ListSearch.reInitBuffer = True

    def SetFilterOn(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered(selectedList):
            return
        self.innerList[selectedList].filterCache\
            = self.innerList[selectedList].items
        self.InitSelectedItems(selectedList)

    def SetFilterOff(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered(selectedList) is False:
            return
        self.innerList[selectedList].items\
            = self.innerList[selectedList].filterCache
        self.innerList[selectedList].filterCache = None
        self.innerList[selectedList].filterQuery = None
        self.InitSelectedItems(selectedList)
        self.RefreshSortedColumn()

    def RefreshSortedColumn(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        idx = self.GetLastSortedColumn(selectedList)[0]
        self.SortColumn(idx, selectedList)
        self.SortColumn(idx, selectedList)

    def MirrorItemToFilterCache(self, itemIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered(selectedList) is False:
            return
        cacheIdx = self.ItemIdxToCacheIdx(itemIdx, selectedList)
        if cacheIdx is None:
            return
        self.innerList[selectedList].filterCache[cacheIdx]\
            = self.innerList[selectedList].items[itemIdx]

    def MirrorItemFromFilterCache(self, cacheIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered(selectedList) is False:
            return
        itemIdx = self.CacheIdxToItemIdx(cacheIdx, selectedList)
        if itemIdx is None:
            return
        self.innerList[selectedList].items[itemIdx]\
            = self.innerList[selectedList].filterCache[cacheIdx]

    def GetItemCacheValueByColumnIdx(self, itemIdx, columnIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].filterCache[itemIdx][columnIdx]

    def GetItemCacheValueByColumnKey(self, itemIdx, columnKey, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        columnIdx = self.GetColumnKeyToIdx(columnKey)
        return self.innerList[selectedList].filterCache[itemIdx][columnIdx]

    def GetItemValueByColumnIdx(self, itemIdx, columnIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].items[itemIdx][columnIdx]

    def GetItemValueByColumnKey(self, itemIdx, columnKey, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        columnIdx = self.GetColumnKeyToIdx(columnKey, selectedList)
        return self.innerList[selectedList].items[itemIdx][columnIdx]

    def PropagateItemValue(
            self, itemIdx, columnKey, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if columnKey == 'path':
            someKey = 'mdx'
        else:
            someKey = 'path'
        self.PropagateItemValueBySomeKey(
            itemIdx, columnKey, value, selectedList, someKey)

    def PropagateItemValueBySomeKey(
            self, itemIdx, columnKey, value, selectedList=None, someKey='path'):
        if selectedList is None:
            selectedList = self.selectedList
        some = self.GetItemValueByColumnKey(itemIdx, someKey, selectedList)
        value = self.GetItemValueByColumnKey(itemIdx, columnKey, selectedList)
        for listIdx in range(len(self.innerList)):
            someIdx = self.GetColumnKeyToIdx(someKey, listIdx)
            columnIdx = self.GetColumnKeyToIdx(columnKey, listIdx)
            if self.IsFiltered(listIdx):
                cacheId = [cacheId for cacheId, item in enumerate(
                    self.innerList[listIdx].filterCache) if item[someIdx] == some]
                if cacheId == []:
                    continue
                self.SetCacheValueByColumnIdxLocal(cacheId[0], columnIdx, value, listIdx)
            else:
                itemId = [itemId for itemId, item in enumerate(
                    self.innerList[listIdx].items) if item[someIdx] == some]
                if itemId == []:
                    continue
                self.SetItemValueByColumnIdxLocal(itemId[0], columnIdx, value, listIdx)

    def CacheIdxToItemIdx(self, cacheIdx, selectedList):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered() is False:
            return None
        orderIdx = self.GetColumnKeyToIdx('order', selectedList)
        order = self.innerList[selectedList].filterCache[cacheIdx][orderIdx]
        itemIdx = [i for i, v in enumerate(
            self.innerList[selectedList].items) if v[orderIdx] == order]
        if itemIdx == []:
            return None
        return itemIdx[0]

    def ItemIdxToCacheIdx(self, itemIdx, selectedList):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered() is False:
            return None
        orderIdx = self.GetColumnKeyToIdx('order', selectedList)
        order = self.innerList[selectedList].items[itemIdx][orderIdx]
        cacheIdx = [i for i, v in enumerate(
            self.innerList[selectedList].filterCache) if v[orderIdx] == order]
        if cacheIdx == []:
            return None
        return cacheIdx[0]

    def SetItemValueByColumnIdx(
            self, itemIdx, columnIdx, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.SetItemValueByColumnIdxLocal(
            itemIdx, columnIdx, value, selectedList)
        columnKey = self.GetColumnIdxToKey(columnIdx, selectedList)
        cacheIdx = self.ItemIdxToCacheIdx(itemIdx, selectedList)
        if cacheIdx is not None:
            self.SetCacheValueByColumnIdxLocal(
                cacheIdx, columnKey, value, selectedList)
        self.PropagateItemValue(itemIdx, columnKey, value, selectedList)

    def SetItemValueByColumnKey(
            self, itemIdx, columnKey, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.SetItemValueByColumnKeyLocal(
            itemIdx, columnKey, value, selectedList)
        cacheIdx = self.ItemIdxToCacheIdx(itemIdx, selectedList)
        if cacheIdx is not None:
            self.SetCacheValueByColumnKeyLocal(
                cacheIdx, columnKey, value, selectedList)
        self.PropagateItemValue(itemIdx, columnKey, value, selectedList)

    def SetItemValueByColumnIdxLocal(
            self, itemIdx, columnIdx, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        item = list(self.innerList[selectedList].items[itemIdx])
        item[columnIdx] = value
        self.innerList[selectedList].items[itemIdx] = tuple(item)
        self.MirrorItemToFilterCache(itemIdx, selectedList)

    def SetItemValueByColumnKeyLocal(
            self, itemIdx, columnKey, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        item = list(self.innerList[selectedList].items[itemIdx])
        item[self.GetColumnKeyToIdx(columnKey, selectedList)] = value
        self.innerList[selectedList].items[itemIdx] = tuple(item)
        self.MirrorItemToFilterCache(itemIdx, selectedList)

    def SetCacheValueByColumnIdxLocal(
            self, cacheIdx, columnIdx, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered(selectedList) is False:
            return
        item = list(self.innerList[selectedList].filterCache[cacheIdx])
        item[columnIdx] = value
        self.innerList[selectedList].filterCache[cacheIdx] = tuple(item)
        self.MirrorItemFromFilterCache(cacheIdx, selectedList)

    def SetCacheValueByColumnKeyLocal(
            self, cacheIdx, columnKey, value, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.IsFiltered(selectedList) is False:
            return
        item = list(self.innerList[selectedList].filterCache[cacheIdx])
        item[self.GetColumnKeyToIdx(columnKey, selectedList)] = value
        self.innerList[selectedList].filterCache[cacheIdx] = tuple(item)
        self.MirrorItemFromFilterCache(cacheIdx, selectedList)

    def SetShownColumnShuffle(self, fromIdx, toIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        lastSortedColumn = self.GetLastSortedColumn()
        if fromIdx < toIdx:
            toIdx = toIdx - 1
        shownColumnsIdx = self.GetShownColumnsIdx()
        toIdx = shownColumnsIdx[toIdx]
        fromIdx = shownColumnsIdx[fromIdx]
        if lastSortedColumn[0] is not None:
            lsckey = self.GetColumns()[lastSortedColumn[0]].key
        self.innerList[selectedList].columns.insert(
            toIdx, self.innerList[selectedList].columns.pop(fromIdx))
        if lastSortedColumn[0] is not None:
            self.innerList[selectedList].lastSortedColumn[0]\
                = self.GetColumnKeyToIdx(lsckey)
        for i, v in enumerate(self.innerList[selectedList].items):
            v = list(v)
            v.insert(toIdx, v.pop(fromIdx))
            self.innerList[selectedList].items[i] = v
        if self.IsFiltered():
            for i, v in enumerate(self.innerList[selectedList].filterCache):
                v = list(v)
                v.insert(toIdx, v.pop(fromIdx))
                self.innerList[selectedList].filterCache[i] = v

    def GetSelectedListIdx(self):
        return self.selectedList

    def SetSelectedList(self, idx):
        self.selectedList = idx
        # self.parent.PlayBox.FocusPlayingItem()
        self.DirectDraw()

    def AddInnerList(self, title=None):
        if hasattr(self, 'innerList') is False:
            self.innerList = []
            filtered = False
        else:
            filtered = self.IsFilteredAll()
        if hasattr(self, 'selectedList') is False:
            self.selectedList = 0
        self.innerList.append(InnerList())
        self.selectedList = len(self.innerList) - 1
        timeId = '%0.12f' % (time.time())
        self.innerList[self.selectedList].Id = timeId
        self.innerList[self.selectedList].lock = False
        if filtered:
            query = self.innerList[0].filterQuery
            self.innerList[self.selectedList].filterQuery = query
            self.SetFilterOn(self.selectedList)
        if title is None:
            title = self.GetBestListTitle()
            self.SetListTitle(title)
        else:
            self.SetListTitle(title)
        if hasattr(self, 'line_space'):
            self.SetRowsHeightAll(self.line_space)
        self.reInitBuffer = True

    def GetBestListTitle(self, prefix='Untitled-'):
        existingTitles = [self.innerList[i].title.lower() for i in range(len(self.innerList))]
        lowerPrefix = prefix.lower()
        for cnt in range(1, 1000):
            title = '%s%02d' % (lowerPrefix, cnt)
            if title in existingTitles:
                continue
            return '%s%02d' % (prefix, cnt)

    def DeleteInnerList(self, idx):
        if len(self.innerList) == 1:
            return
        self.innerList.pop(idx)
        tabLength = len(self.innerList)
        if tabLength == 0:
            idx = None
        elif idx >= tabLength - 1:
            idx = tabLength - 1
        self.selectedList = idx
        self.reInitBuffer = True

    def SetListTitle(self, title, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if len(title) == 0:
            return
        if len(title) > 256:
            return
        # if len(title) > 64:
        #     return
        title = self.LimitFileName(title)
        self.innerList[selectedList].title = title

    def GetListTitle(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].title

    def LimitFileName(self, name):
        strip = re.findall(r'(\s+)$', name)
        if strip != []:
            name = name[:-len(strip[0])]
        strip = re.findall(r'^(\s+)', name)
        if strip != []:
            name = name[len(strip[0]):]
        return name

    # Header Control

    def GetColumns(self):
        return self.innerList[self.selectedList].columns

    def GetColumnRectIdx(self, x):
        self.column_splitter_size = 5
        margin = self.column_splitter_size
        vpx = self.GetVirtualPositionX()
        for i, column in enumerate(self.GetShownColumns()):
            if x >= vpx + margin and x <= vpx + column.width - margin:
                return i
            vpx += column.width
        return None

    def GetShownColumnsWidth(self):
        width = 0
        for column in self.GetShownColumns():
            width += column.width
        return width

    def GetBestColumnWidth(self, idx, width):
        self.innerList[self.selectedList]
        if width < self.innerList[self.selectedList].columns[idx].min_width:
            width = self.innerList[self.selectedList].columns[idx].min_width
        elif width > self.innerList[self.selectedList].columns[idx].max_width:
            width = self.innerList[self.selectedList].columns[idx].max_width
        return width

    def SetColumnWidthAll(self, idx, width):
        for selectedList in range(len(self.innerList)):
            self.innerList[selectedList].columns[idx].width = width
        self.reInitBuffer = True

    def SetColumnWidth(self, idx, width, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].columns[idx].width = width
        self.reInitBuffer = True

    def SetBestColumnWidth(self, idx, width):
        width = self.GetBestColumnWidth(idx, width)
        self.SetColumnWidth(idx, width)

    def SetColumn(self, key, **kwrd):  # SetColumn('order', width=100)
        if type(key) != int:
            for kw in kwrd.keys():
                exec(
                    'self.innerList[self.selectedList].columns[%s].%s=%s'
                    % (self.GetColumnKeyToIdx(key), kw, kwrd[kw]))
        else:
            for kw in kwrd.keys():
                exec(
                    'self.innerList[self.selectedList].columns[%s].%s=%s'
                    % (key, kw, kwrd[kw]))

    def GetColumn(self, key, selectedList):  # GetColumn('order')
        if selectedList is None:
            selectedList = self.selectedList
        return filter(lambda v: v.key == key,
                      self.innerList[selectedList].columns)[0]

    def GetColumnIdxToKey(self, idx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].columns[idx].key

    def GetColumnKeyToIdx(self, key, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return [i for i, v in enumerate(self.innerList[selectedList].columns) if v.key == key][0]

    def GetShownColumns(self):
        return list(filter(lambda v: v.show is True, self.innerList[self.selectedList].columns))

    def GetShownColumnsIdx(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return [i for i, v in enumerate(self.innerList[selectedList].columns) if v.show is True]

    def GetInsertColumnIdx(self, x):
        headerIdx = self.GetHeaderIdx(x)
        if headerIdx is None:
            return None
        if headerIdx[1] == 0 or headerIdx[1] == 1:
            return headerIdx[0] + headerIdx[1]
        if headerIdx[1] == 2:
            return headerIdx[0] + 1
        return None

    def GetColumnSplitterIdx(self, x):
        if self.Header.onClient is False:
            return None
        headerIdx = self.GetHeaderIdx(x)
        if headerIdx is None:
            return None
        if headerIdx[1] != 2:
            return None
        return headerIdx[0]

    def GetHeaderIdx(self, x):
        self.column_splitter_size = 5
        if self.Header.onClient is False:
            return None
        width = self.GetSize().width
        vpx = self.GetVirtualPositionX()
        columns = list()
        for i, column in enumerate(self.GetShownColumns()):
            columns.append(Struct(x=vpx, width=column.width))
            vpx += column.width
        for i, column in enumerate(columns):
            if x > column.x + column.width - self.column_splitter_size\
                    and x < column.x + column.width + self.column_splitter_size:
                return [i, 2]
            elif x >= column.x + column.width / 2 and x <= column.x + column.width:
                return [i, 1]
            elif x >= column.x and x <= column.x + column.width / 2:
                return [i, 0]
        if x >= column.x and x < width:
            return [i + 1, 0]
        return None

    def GetGlobalColumnIdx(self, x):
        width = self.GetSize().width
        vpx = self.GetVirtualPositionX()
        columns = list()
        for i, column in enumerate(self.GetShownColumns()):
            columns.append(Struct(x=vpx, width=column.width))
            vpx += column.width
        for i, column in enumerate(columns):
            if x > column.x + column.width\
                    and x < column.x + column.width:
                return i
            elif x >= column.x + column.width / 2 and x <= column.x + column.width:
                return i
            elif x >= column.x and x <= column.x + column.width / 2:
                return i
        if x >= column.x and x < width:
            return i + 1
        return None

    def CloneColumnsDefinitionToAll(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        columns = copy.deepcopy(self.innerList[selectedList].columns)
        for listIdx in range(len(self.innerList)):
            if listIdx == selectedList:
                continue
            columnsIdx = [self.GetColumnKeyToIdx(v.key, listIdx) for v in columns]
            # need to debug columns and columnsIdx
            # print [v.key for v in columns]
            # print columnsIdx
            for itemIdx in range(len(self.innerList[listIdx].items)):
                newItem = [self.innerList[listIdx].items[itemIdx][columnIdx]
                           for columnIdx in columnsIdx]
                self.innerList[listIdx].items[itemIdx] = tuple(newItem)
            if self.IsFiltered(listIdx):
                for cacheIdx in range(len(self.innerList[listIdx].filterCache)):
                    newItem = [self.innerList[listIdx].filterCache
                               [cacheIdx][columnIdx] for columnIdx in columnsIdx]
                    self.innerList[listIdx].filterCache[cacheIdx] = tuple(newItem)
            self.innerList[listIdx].columns = columns

    # Virtual Position Control

    def GetVirtualPositionX(self):
        return self.innerList[self.selectedList].rects.offset.x

    def GetVirtualPositionY(self):
        return self.innerList[self.selectedList].rects.offset.y

    def GetVirtualPositionXW(self):
        vpxw = self.GetVirtualPositionX()
        for column in self.GetShownColumns():
            vpxw += column.width
        return vpxw

    # def GetVirtualPositionYH(self):
    #     row_size = self.GetRowsHeight()
    #     height = self.rects.list.height
    #     length = self.GetItemsLength()
    #     vpy = self.GetVirtualPositionY()
    #     return offset_y + length * row_size

    def GetVirtualPosition(self):
        x = self.GetVirtualPositionX()
        y = self.GetVirtualPositionY()
        return wx.Point(round(x), round(y))

    def SetVirtualPositionX(self, x):
        x = self.LimitVirtualPositionX(x)
        self.innerList[self.selectedList].rects.offset.x = round(x)
        self.reInitBuffer = True

    def SetVirtualPositionY(self, y, bounce=False):
        y = self.LimitVirtualPositionY(y, bounce=bounce)
        # if bounce:
        #   if y == 0: y = 1
        #   vpy_limit = self.GetVirtualPositionYLimit()
        #   if y == vpy_limit: y = y-5
        #   print y
        self.innerList[self.selectedList].rects.offset.y = round(y)
        self.reInitBuffer = True

    def SetBestVirtualPositionX(self):
        vpx = self.GetVirtualPositionX()
        self.SetVirtualPositionX(vpx)

    def SetBestVirtualPositionY(self):
        vpy = self.GetVirtualPositionY()
        self.SetVirtualPositionY(vpy)

    def SetBestVirtualPosition(self):
        vpx = self.GetVirtualPositionX()
        vpy = self.GetVirtualPositionY()
        self.SetVirtualPositionX(vpx)
        self.SetVirtualPositionY(vpy)

    def LimitVirtualPositionX(self, x):
        if x > 0:
            return 0
        try:
            list_width = self.List.GetSize().width
        except Exception:
            list_width = 0
        cols_width = self.GetShownColumnsWidth()
        if cols_width < list_width:
            return 0
        if cols_width + x < list_width:
            return -cols_width + list_width
        return x

    def LimitVirtualPositionY(self, vpy, bounce=False):
        if vpy > 0:
            return 0
        vpy_limit = self.GetVirtualPositionYLimit()
        if vpy < vpy_limit:
            if bounce:
                # return vpy_limit-1
                return vpy_limit
            return vpy_limit
        return vpy

    def GetVirtualPositionXLimit(self):
        length = self.GetShownColumnsWidth()
        if hasattr(self, 'List'):
            width = self.List.GetClientSize().height
        else:
            width = 0
        if length < width:
            return 0
        return -length + width
        # length = self.rectHeader.columns[-1].x+self.rectHeader.columns[-1].w
        # if length < self.rectList.w: return 0
        # return -length+self.rectList.w

    def GetVirtualPositionYLimit(self):
        row_size = self.GetRowsHeight()
        if hasattr(self, 'List'):
            height = self.List.GetClientSize().height
        else:
            height = 0
        length = self.GetItemsLength()
        # print self.rects.list.height
        if length * row_size < height:
            return 0
        return -length * row_size + height

    # List Control

    def InitInnerList(self):
        self.innerList = list()

    def InitSelectedItems(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].selectedItems = list()

    def PosY2Item(self, posY):
        return int((posY - self.GetVirtualPositionY() - 1) / self.GetRowsHeight())

    def GetInsertItemIdx(self, y):
        if self.List.onClient is False:
            return None
        row_size = self.GetRowsHeight()
        vpy = self.GetVirtualPositionY()
        itemsLength = self.GetItemsLength()
        itemIdx = int((y - vpy + row_size * 0.5) / row_size)
        if itemIdx > itemsLength:
            itemIdx = itemsLength
        return itemIdx

    def GetShownItemsIdx(self):
        vpy = self.innerList[self.selectedList].rects.offset.y
        vpy = self.LimitVirtualPositionY(vpy, bounce=True)
        self.innerList[self.selectedList].rects.offset.y = vpy
        row_size = self.GetRowsHeight()
        vpy = self.GetVirtualPositionY()
        innerListLength = self.GetItemsLength()
        if hasattr(self, 'List'):
            height = self.List.GetSize().height
        else:
            height = 0
        # height = self.rects.list.height
        maxline = self.GetMaxLine()
        maxlinefloat = self.GetMaxLineFloat()
        if height >= innerListLength * row_size:
            vpy = 0
        firstShownItem = int(abs(vpy) / row_size)
        lastShownItem = int((abs(vpy) + maxlinefloat * row_size) / row_size)
        if lastShownItem > innerListLength:
            lastShownItem = innerListLength
        if height >= innerListLength * row_size:
            maxLine = innerListLength
        else:
            maxLine = maxline
        shownItems = list(range(firstShownItem, firstShownItem + maxLine))
        if shownItems == []:
            return []
        if innerListLength > shownItems[-1] + 1:
            shownItems = list(range(firstShownItem, lastShownItem + 1))
        return shownItems

    def GetRowsHeight(self):
        return self.innerList[self.selectedList].rects.row.height

    def SetRowsHeight(self, height, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].rects.row.height = height

    def SetRowsHeightAll(self, height):
        for selectedList in range(len(self.innerList)):
            self.innerList[selectedList].rects.row.height = height

    def GetItemsLength(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return len(self.innerList[selectedList].items)

    def GetSelectedItemsKeyValue(self, key, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if self.GetItemsLength(selectedList) == 0:
            return
        if self.GetSelectedItemsLength(selectedList) == 0:
            return
        items = list()
        idx = self.GetColumnKeyToIdx(key, selectedList)
        for item in self.GetSelectedItems(selectedList):
            # if item > itemsLength: break
            items.append(self.innerList[selectedList].items[item][idx])
        return items

    def IsNeededSliderH(self):
        if hasattr(self, 'List') is False:
            return False
        if self.GetShownColumnsWidth() > self.List.GetSize().width:
            return True
        return False

    def IsNeededSliderV(self):
        if self.GetItemsLength() > self.GetMaxLineFloat():
            return True
        return False

    def GetMaxLine(self):
        return int(math.ceil(self.GetMaxLineFloat()))

    def GetMaxLineFloat(self):
        try:
            height = self.List.GetSize().height
        except Exception:
            height = 0
        return 1.0 * height / self.GetRowsHeight()

    def IsSelectedItem(self, item):
        if item in self.GetSelectedItems():
            return True
        return False

    def IsHighlightedItem(self, item):
        if item in self.innerList[self.selectedList].selectedItems:
            return True
        return False

    def RefreshOrder(self):
        cid = self.GetColumnKeyToIdx('order')
        self.innerList[self.selectedList].items\
            = sorted(self.innerList[self.selectedList].items, key=itemgetter(cid))
        for i, v in enumerate(self.innerList[self.selectedList].items):
            v = list(v)
            v[cid] = i + 1
            self.innerList[self.selectedList].items[i] = tuple(v)
        if self.innerList[self.selectedList]\
                .lastSortedColumn[1] == 1:
            reverse = False
        elif self.innerList[self.selectedList]\
                .lastSortedColumn[1] == -1:
            reverse = True
        self.innerList[self.selectedList].items\
            = sorted(self.innerList[self.selectedList].items,
                     key=itemgetter(self.innerList[self.selectedList]
                                    .lastSortedColumn[0]), reverse=reverse)

    def GetLastSortedColumn(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].lastSortedColumn

    def SetLastSortedColumn(self, idx_direction, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[self.selectedList].lastSortedColumn = idx_direction

    def RemoveItemAll(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.UnSelectItemAll(selectedList)
        self.innerList[self.selectedList].items = list()

    def RemoveSelectedItems(self):
        itemsLength = self.GetItemsLength()
        selectedItemsLength = self.GetSelectedItemsLength()
        if itemsLength == 0:
            return
        if selectedItemsLength == 0:
            return
        if selectedItemsLength == itemsLength:
            self.RemoveItemAll()
            return
        for i in sorted(self.innerList[
                self.selectedList].selectedItems, reverse=True):
            self.innerList[self.selectedList].items.pop(i)
        self.RefreshOrder()
        self.InitSelectedItems()
        if selectedItemsLength == 1:
            nearestItem = self.GetNearestItem(self.GetFocusedItem())
            if nearestItem != -1:
                self.SelectAndFocusItem(nearestItem)
        self.reInitBuffer = True

    def RemoveItemsByPath(self, paths):
        for path in paths:
            for listIdx in range(len(self.innerList)):
                itemIdx = self.GetItemsIdxByColumnKeyValue('path', path, listIdx)
                if itemIdx != []:
                    for i in itemIdx:
                        self.innerList[listIdx].items.pop(i)
                itemIdx = self.GetCacheIdxByColumnKeyValue('path', path, listIdx)
                if itemIdx != []:
                    for i in itemIdx:
                        self.innerList[listIdx].filterCache.pop(i)
        self.RefreshOrder()
        self.InitSelectedItems()
        self.reInitBuffer = True

    def SelectItems(self, items):
        if type(items) != list:
            items = [items]
        select = [i for i in items
                  if i not in self.innerList[self.selectedList].selectedItems]
        unselect = [i for i in items
                    if i in self.innerList[self.selectedList].selectedItems]
        self.UnSelectItems(unselect)
        self.innerList[self.selectedList].selectedItems\
            = self.innerList[self.selectedList].selectedItems + select

    def GetNearestItem(self, focus, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if focus < 0:
            return 0
        elif focus >= self.GetItemsLength(selectedList):
            return self.GetItemsLength(selectedList) - 1
        return focus

    def GetFocusedItem(self, selectedList=None):
        # return self.focus.item
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].focus.item

    def GetShiftedItem(self, selectedList=None):
        # return self.focus.shift
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].focus.shift

    def IsItemInViewRange(self, item):
        if self.ItemDirectionInViewRange(item) == 0:
            return True
        return False

    def ItemDirectionInViewRange(self, item):
        row_size = self.GetRowsHeight()
        height = self.List.GetSize().height
        y = self.GetVirtualPositionY() + item * row_size
        if y < 0:
            return -1
        if y > height - row_size:
            return 1
        return 0

    def GetSelectedItem(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if len(self.innerList[selectedList].selectedItems) == 0:
            return None
        return self.innerList[selectedList].selectedItems[-1]

    def GetSelectedItemsLength(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return len(self.innerList[selectedList].selectedItems)

    def GetSelectedItems(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].selectedItems

    def SelectItemAll(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].selectedItems\
            = range(0, self.GetItemsLength(selectedList))
        self.reInitBuffer = True

    def UnSelectItemAll(self, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].selectedItems = []
        self.reInitBuffer = True

    # UI Action Control

    def ScrollH(self, scroll_size):
        vpx = self.GetVirtualPositionX()
        x = vpx + scroll_size * 5
        self.SetVirtualPositionX(x)

    def ScrollV(self, scroll_size):
        vpy = self.GetVirtualPositionY()
        y = vpy + scroll_size * self.GetRowsHeight()
        self.SetVirtualPositionY(y, bounce=True)

    def SlideVKnob(self, event):
        if event.LeftIsDrag is False:
            return
        rect = self.rectSliderV
        initPosY = event.drag.Y - rect.slidable.y
        if event.drag.rectIdx == 301 and self.pending.SliderDrag is False:
            self.dragSlidePosY = self.firstItemPosY
            self.pending.SliderDrag = True
        length = len(self.innerList) * self.row_size
        if length != 0:
            shownRatio = 1.0 * self.rectList.h / length
        else:
            shownRatio = 1.0
        if shownRatio > 1.0:
            shownRatio = 1.0
        slidable = rect.slidable.h - rect.knob.h
        if slidable == 0:
            return
        diff = event.Y - initPosY - rect.slidable.y
        diffRatio = 1.0 * diff * (length - self.rectList.h) / slidable
        self.firstItemPosY = self.LimitFirstItemPosY(self.dragSlidePosY - diffRatio)
        self.reInitBuffer = True

    def SlideVSlidable(self, event):
        rect = self.rectSliderV
        slidable = rect.slidable.h - rect.knob.h
        if slidable != 0:
            posCYRatio = 1.0 * (event.Y - rect.slidable.y - rect.knob.h * 0.5) / slidable
        else:
            posCYRatio = 1.0
        firstItemPosYLimit = self.GetFirstItemPosYLimit()
        self.firstItemPosY = self.LimitFirstItemPosY(
            int(posCYRatio * firstItemPosYLimit))
        self.reInitBuffer = True

    def SelectAndFocusItem(self, item, shift=None, align=None):
        if item < 0:
            item = 0
        if item >= self.GetItemsLength():
            item = self.GetItemsLength() - 1
        self.innerList[self.selectedList].selectedItems = [item]
        self.FocusItem(item, shift=shift, align=align)

    def ControlSelectItem(self, item):
        if item in self.GetSelectedItems():
            self.innerList[self.selectedList].selectedItems.remove(item)
        else:
            self.innerList[self.selectedList].selectedItems.append(item)
        self.FocusItem(item)

    def ShiftSelectItems(self, item):
        if item < 0:
            item = 0
        itemsLength = self.GetItemsLength()
        if item >= itemsLength:
            item = itemsLength - 1
        shift = self.GetShiftedItem()
        if shift is None:
            self.SelectAndFocusItem(item, shift=item)
            return
        if shift < item:
            items = range(shift, item + 1)
        elif shift > item:
            items = range(shift, item - 1, -1)
        else:
            items = [item]
        self.innerList[self.selectedList].selectedItems = items
        self.FocusItem(item, shift=shift, align=None)

    def ScrollSelectItem(self, scroll_size, shifted=False):
        if scroll_size is None:
            return
        if isinstance(scroll_size, float) and scroll_size == 0.0:
            item = 0
        elif isinstance(scroll_size, float) and scroll_size == 1.0:
            item = self.GetItemsLength() - 1
        else:
            # self.GetSelectedItems()
            focusedItem = self.GetFocusedItem()
            if focusedItem is None:
                return
            item = self.GetNearestItem(focusedItem + scroll_size)
        if shifted is False:
            self.SelectAndFocusItem(item, shift=None, align=None)
            return
        self.ShiftSelectItems(item)

    def FocusItem(self, item, shift=None, align=None, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].focus.item = item
        row_size = self.GetRowsHeight()
        if shift is None:
            self.innerList[selectedList].focus.shift = item
        else:
            self.innerList[selectedList].focus.shift = shift
        if align is None and self.IsItemInViewRange(item):
            self.reInitBuffer = True
            return
        if align is None:
            align = self.ItemDirectionInViewRange(item)
        height = self.List.GetClientSize().height
        offsetY = (height - row_size) * 0.5 * (align + 1)
        newPosY = -item * row_size + offsetY
        if newPosY > 0:
            newPosY = 0
        self.SetVirtualPositionY(newPosY, bounce=True)
        self.reInitBuffer = True

    def UnSelectItems(self, items, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        for item in [i for i in items if i in self.innerList[selectedList].selectedItems]:
            self.innerList[self.selectedList].remove(item)

    def SortColumn(self, idx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        orderIdx = self.GetColumnKeyToIdx('order', selectedList)
        statusIdx = self.GetColumnKeyToIdx('status', selectedList)
        lastSortedColumn = self.GetLastSortedColumn(selectedList)
        if idx == statusIdx:
            return
        if lastSortedColumn == [orderIdx, 1] and idx == orderIdx:
            return
        # shownColumnsIdx = self.GetShownColumnsIdx(selectedList)
        if lastSortedColumn[0] != idx:
            direction = 1
        else:
            direction = -lastSortedColumn[1]
        selectedItemsOrder = [self.innerList[selectedList].items[i][orderIdx]
                              for i in self.GetSelectedItems(selectedList)]
        if direction == 1:
            self.SetLastSortedColumn([idx, direction], selectedList)
            self.innerList[selectedList].items\
                = sorted(self.innerList[selectedList].items, key=itemgetter(idx))
        elif direction == -1:
            self.SetLastSortedColumn([idx, direction], selectedList)
            self.innerList[selectedList].items\
                = sorted(self.innerList[selectedList].items, key=itemgetter(idx), reverse=True)
        self.innerList[selectedList].selectedItems\
            = [i for i in range(self.GetItemsLength(selectedList))
               if self.innerList[selectedList].items[i][orderIdx] in selectedItemsOrder]
        self.reInitBuffer = True

    def IsEdiditableColumnByColumnIdx(self, columnIdx, selectedList=None):
        if columnIdx is None:
            return False
        if selectedList is None:
            selectedList = self.selectedList
        shownColumnsIdx = self.GetShownColumnsIdx(selectedList)
        if columnIdx >= len(shownColumnsIdx):
            return False
        columnIdx = shownColumnsIdx[columnIdx]
        return self.innerList[selectedList].columns[columnIdx].editable

    def ConvertToUpTempo(self, itemsIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.SetListLock(selectedList)
        tempoIdx = self.GetColumnKeyToIdx('tempo', selectedList)
        for itemIdx in itemsIdx:
            item = list(self.innerList[selectedList].items[itemIdx])
            try:
                tempo = float(item[tempoIdx])
            except Exception:
                continue
            if tempo <= 95:
                tempo = tempo * 2.0
            item[tempoIdx] = '%05.1f' % (tempo)
            self.innerList[selectedList].items[itemIdx] = tuple(item)
        self.SetListUnLock(selectedList)
        self.List.reInitBuffer = True

    def ConvertToDownTempo(self, itemsIdx, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.SetListLock(selectedList)
        self.parent.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        # self.parent.CursorEventCatcher.SetCursorWAIT()
        tempoIdx = self.GetColumnKeyToIdx('tempo', selectedList)
        for itemIdx in itemsIdx:
            oldValue = self.innerList[selectedList].items[itemIdx][tempoIdx]
            try:
                tempo = float(oldValue)
            except Exception:
                continue
            if tempo >= 120:
                tempo = tempo * 0.5
            newValue = '%05.1f' % (tempo)
            if newValue == oldValue:
                continue
            self.RenameID3TAGByColumnItemIdx(
                tempoIdx, itemIdx, newValue, selectedList)
        self.parent.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        # self.parent.CursorEventCatcher.SetCursorARROW()
        self.SetListUnLock(selectedList)
        # self.List.reInitBuffer = True
        self.List.reInitBuffer = True

    def ConvertKeyFormat(self, itemsIdx, key_type, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.SetListLock(selectedList)
        self.parent.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
        # self.parent.CursorEventCatcher.SetCursorWAIT()
        keyIdx = self.GetColumnKeyToIdx('key', selectedList)
        for itemIdx in itemsIdx:
            oldValue = self.innerList[selectedList].items[itemIdx][keyIdx]
            newValue = mfeats.convert_chord_type(oldValue, key_type)
            if newValue == oldValue:
                continue
            self.RenameID3TAGByColumnItemIdx(
                keyIdx, itemIdx, newValue, selectedList)
        self.parent.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        # self.parent.CursorEventCatcher.SetCursorARROW()
        self.SetListUnLock(selectedList)
        self.List.reInitBuffer = True


# http://www.blog.pythonlibrary.org/2011/02/10/
# wxpython-showing-2-filetypes-in-wx-filedialog/

class FileOpenDialog(wx.FileDialog):

    def __init__(self, parent):
        self.parent = parent
        message = 'Import Tracks'
        defaultDir = os.path.expanduser(u'~')
        defaultDir = os.path.dirname(defaultDir)
        wildcard = [u'*.%s' % (v) for v in SUPPORTED_PLAYLIST_TYPE]
        wildcard += [u'*.%s' % (v) for v in SUPPORTED_AUDIO_TYPE]
        wildcard = u';'.join(wildcard)
        wx.FileDialog.__init__(self, parent,
                               defaultDir=defaultDir, message=message, wildcard=wildcard,
                               style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_CHANGE_DIR)


class FileSaveDialog(wx.FileDialog):

    def __init__(self, parent):
        self.parent = parent
        message = 'Export Tracklist'
        defaultDir = os.path.expanduser(u'~')
        defaultDir = os.path.dirname(defaultDir)
        wildcard = [u'*.%s' % (v) for v in SUPPORTED_PLAYLIST_TYPE]
        wildcard = u';'.join(wildcard)
        wx.FileDialog.__init__(self, parent,
                               defaultDir=defaultDir, message=message, wildcard=wildcard,
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR)
        filename = self.parent.parent.ListBox.GetListTitle()
        self.SetFilename(filename)
