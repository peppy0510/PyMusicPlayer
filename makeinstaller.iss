; http://www.jrsoftware.org/ishelp/index.php

[Setup]
AppName="PyMusicPlayer"
AppVerName="PyMusicPlayer 1.0.51"
DefaultDirName="{pf}\PyMusicPlayer"
DefaultGroupName="PyMusicPlayer"
AppVersion="1.0.51"
AppCopyright="Taehong Kim"
AppPublisher="Taehong Kim"
UninstallDisplayIcon="{app}\PyMusicPlayer.exe"
Compression=lzma2/max
SolidCompression=yes
OutputDir="dist"
OutputBaseFilename="PyMusicPlayer-1.0.51-Setup"
; VersionInfoVersion="1.0.51"
VersionInfoProductVersion="1.0.51"
VersionInfoCompany="Taehong Kim"
VersionInfoCopyright="Taehong Kim"
ArchitecturesInstallIn64BitMode="x64"

[Files]
Source: "dist\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\PyMusicPlayer"; Filename: "{app}\PyMusicPlayer.exe"
Name: "{commondesktop}\PyMusicPlayer"; Filename: "{app}\PyMusicPlayer.exe"
