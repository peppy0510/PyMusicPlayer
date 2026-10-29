; http://www.jrsoftware.org/ishelp/index.php

[Setup]
AppName="PyMusicPlayer"
AppVerName="PyMusicPlayer 1.2.2"
DefaultDirName="{autopf}\PyMusicPlayer"
DefaultGroupName="PyMusicPlayer"
AppVersion="1.2.2"
AppCopyright="Taehong Kim"
AppPublisher="Taehong Kim"
UninstallDisplayIcon="{app}\PyMusicPlayer.exe"
Compression=lzma2/max
SolidCompression=yes
OutputDir=".dist"
OutputBaseFilename="PyMusicPlayer-1.2.2-Setup"
; VersionInfoVersion="1.2.2"
VersionInfoProductVersion="1.2.2"
VersionInfoCompany="Taehong Kim"
VersionInfoCopyright="Taehong Kim"
ArchitecturesInstallIn64BitMode="x64compatible"

[Files]
Source: ".dist\PyMusicPlayer\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\PyMusicPlayer"; Filename: "{app}\PyMusicPlayer.exe"
Name: "{commondesktop}\PyMusicPlayer"; Filename: "{app}\PyMusicPlayer.exe"
