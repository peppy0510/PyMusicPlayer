; http://www.jrsoftware.org/ishelp/index.php

[Setup]
AppName="PyMusicPlayer"
AppVerName="PyMusicPlayer 1.3.1000"
DefaultDirName="{autopf}\PyMusicPlayer"
DefaultGroupName="PyMusicPlayer"
AppVersion="1.3.1000"
AppCopyright="Taehong Kim"
AppPublisher="Taehong Kim"
UninstallDisplayIcon="{app}\PyMusicPlayer.exe"
Compression=lzma2/max
SolidCompression=yes
OutputDir=".dist"
OutputBaseFilename="PyMusicPlayer-1.3.1000-Setup"
; VersionInfoVersion="1.3.1000"
VersionInfoProductVersion="1.3.1000"
VersionInfoCompany="Taehong Kim"
VersionInfoCopyright="Taehong Kim"
ArchitecturesInstallIn64BitMode="x64compatible"

[Files]
Source: ".dist\PyMusicPlayer\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\PyMusicPlayer"; Filename: "{app}\PyMusicPlayer.exe"
Name: "{commondesktop}\PyMusicPlayer"; Filename: "{app}\PyMusicPlayer.exe"
