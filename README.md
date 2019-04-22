
## Features

* Music player implemented with python.
* Uses wxPython, numpy, scipy, pybass, un4seen BASS, LoudMax VST.
* Drag and drop following audio files and playlists are supported.
* mp2, mp3, mp4, wav, m4a, ape, flac, aac, ac3, aiff, wma, ogg, m3u
* Displays waveform as a seek bar.
* Displays a real-time log scale mel-frequency spectrum.
* Displays a real-time vectorscope showing a stereo image.
* Analyse and display tempo, key, highlight part of the music.
* The highlights part of the music is displayed on the waveform.
* Only highlights of music can be played continuously.
* Import and analysis done with multi thread or process.
* Ultra fast and accurate global BPM detection.
* ID3Tag edit supported.
* Editable hotkeys supported.
* Automatic gain control with LoudMax VST plug-in.
* When you drag and drop audio files or playlists red bar icon will be displayed on the left side of the playlist which means that the track has not been analysed. As soon as the player starts to analyse each track the icon will instantly changed to blue color. Wen the analysis of each track is finished the icon will be disappeared.
* Analysing is done by multi-processing and analysed music files' information and waveforms are cached with SQLite database.
* If you see exclamation icon on the left side of the playlist which means that the track has been moved or deleted. In this case, you can perform the Check File Cosistency on the menu.

## How to install

* Just download and install the latest release.
* Alternatively, if you like to build your own, download or clone a repository then execute makebuild.py. Python 3.x, Python packages in the requirements.pip file, and Inno Setup is required.

## Default hotkeys

* You can edit following hotkeys on the Preference menu.

| `Hotkey`   | `Description`                 |
|:----------:|:------------------------------|
| `Spacebar` | `Play and Pause`              |
| `Q`        | `Toggle Highlight Mode`       |
| `W`        | `Previous Track`              |
| `E`        | `Next Track`                  |
| `R`        | `Toggle Loop Mode`            |
| `E`        | `Toggle Loop Mode`            |
| `1`        | `Decrease Highlight Duration` |
| `2`        | `Increase Highlight Duration` |

## Supported platforms

* Microsoft Windows 10
* Other versions of Windows have not been tested yet.

## MISC

* Variable names `macrobox` or `macroboxplayer` in the source code are legacy name of this project.
* Supported Mac OSX years ago. Some parts handle for OSX. Some parts has not been implemented handling OSX while many updates has been occured.

## TODO

* Remove legacy code.
* Automatic update supports via git release page.
* VST plug-in edit panel. Multiple VST plug-in chain supports.
* Change preference file from python shelve object to JSON.
* Internet radio support such as SouthCast and IceCast. In fact, un4seen BASS library supports internet radio.
* Mac OSX support.
* Adjustable playlist and tracklist splitter supports.
