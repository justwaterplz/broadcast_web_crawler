const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('studio', {
  health: () => ipcRenderer.invoke('studio:health'),
  inspect: (payload) => ipcRenderer.invoke('studio:inspect', payload),
  cjenmFiles: (url) => ipcRenderer.invoke('studio:cjenm-files', url),
  importCjenm: (payload) => ipcRenderer.invoke('studio:cjenm-import', payload),
  submit: (payload) => ipcRenderer.invoke('studio:submit', payload),
  job: (id) => ipcRenderer.invoke('studio:job', id),
  collections: () => ipcRenderer.invoke('studio:collections'),
  hide: (path) => ipcRenderer.invoke('studio:hide', path),
  restore: (path) => ipcRenderer.invoke('studio:restore', path),
  inventory: (payload) => ipcRenderer.invoke('studio:inventory', payload),
  inventories: () => ipcRenderer.invoke('studio:inventories'),
  read: (path) => ipcRenderer.invoke('studio:read', path),
  view: (path, index) => ipcRenderer.invoke('studio:view', path, index),
  openFolder: (path) => ipcRenderer.invoke('studio:open-folder', path),
});
