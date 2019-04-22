; http://www.jrsoftware.org/ishelp/index.php

[Setup]
AppName="PyMusicPlayer"
AppVerName="PyMusicPlayer 1.1.0"
DefaultDirName="{pf}\PyMusicPlayer"
DefaultGroupName="PyMusicPlayer"
AppVersion="1.1.0"
AppCopyright="Taehong Kim"
AppPublisher="Taehong Kim"
UninstallDisplayIcon="{app}\PyMusicPlayer.exe"
Compression=lzma2/max
SolidCompression=yes
OutputDir="dist"
OutputBaseFilename="PyMusicPlayer-1.1.0-Setup"
; VersionInfoVersion="1.1.0"
VersionInfoProductVersion="1.1.0"
VersionInfoCompany="Taehong Kim"
VersionInfoCopyright="Taehong Kim"
ArchitecturesInstallIn64BitMode="x64"

[Files]
Source: "dist\PyMusicPlayer\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\PyMusicPlayer"; Filename: "{app}\PyMusicPlayer.exe"
Name: "{commondesktop}\PyMusicPlayer"; Filename: "{app}\PyMusicPlayer.exe"
