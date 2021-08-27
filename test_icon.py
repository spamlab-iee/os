import os
from win32com.shell import shell, shellcon
import winerror

class IconOverlay:
  
  _reg_clsid_ = '{4FC554DF-F0EE-4A4F-966C-9C49CCF14D59}'
  _reg_progid_ = 'TJG.PythonPackagesOverlayHandler'
  _reg_desc_ = 'Icon Overlay Handler to indicate Python packages'
  _public_methods_ = ['GetOverlayInfo', 'GetPriority', 'IsMemberOf']
  _com_interfaces_ = [shell.IID_IShellIconOverlayIdentifier]
  
  def GetOverlayInfo(self):
    return (r'C:\Program Files\TortoiseHg\icons\status\added.ico', 0, shellcon.ISIOI_ICONFILE)
  
  def GetPriority(self):
    return 50
  
  def IsMemberOf(self, fname, attributes):
    if os.path.exists (os.path.join (fname, "__init__.py")):
        return winerror.S_OK
    return winerror.E_FAIL

if __name__=='__main__':
  import win32api
  import win32con
  import win32com.server.register
  
  win32com.server.register.UseCommandLine (IconOverlay)
  keyname = r'Software\Microsoft\Windows\CurrentVersion\Explorer\ShellIconOverlayIdentifiers\PyPackageOverlay'
  key = win32api.RegCreateKey (win32con.HKEY_LOCAL_MACHINE, keyname)
  win32api.RegSetValue (key, None, win32con.REG_SZ, IconOverlay._reg_clsid_)