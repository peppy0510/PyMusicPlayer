
## Features

* Music player implemented with python.
* Uses wxPython, numpy, scipy, pybass, un4seen BASS, LoudMax VST.
* Drag and drop following audio files and playlists are supported.
* mp2, mp3, mp4, wav, m4a, ape, flac, aac, ac3, aiff, wma, ogg, m3u
* Displays waveform as a seek bar.
* Displays a real-time log scale mel-frequency spectrum.
* Displays a real-time vectorscope showing a stereo image.
* Analyze and display tempo, key, highlight part of the music.
* The highlights part of the music is displayed on the waveform.
* Only highlights of music can be played continuously.
* Import and analysis done with multi thread or process.
* Ultra fast and accurate global BPM detection.
* ID3Tag edit supported.
* Editable hotkeys supported.
* Automatic gain control with LoudMax VST plug-in.
* When you drag and drop audio files or playlists red bar icon will be displayed on the left side of the playlist which means that the track has not been analyzed. As soon as the player starts to analyze each track the icon will instantly changed to blue color. Wen the analysis of each track is finished the icon will be disappeared.
* Analyzing is done by multi-processing and analyzed music files' information and waveforms are cached with SQLite database.
* If you see exclamation icon on the left side of the playlist which means that the track has been moved or deleted. In this case, you can perform the Check File Consistency on the menu.

## Screenshot

![screenshot](/assets/images/screenshot-001.png)

![screenshot](/assets/images/screenshot-002.png)

![screenshot](/assets/images/screenshot-003.png)

![screenshot](/assets/images/screenshot-004.png)

## Demo on YouTube

[![Demo on YouTube](https://img.youtube.com/vi/GWXntjblLWw/default.jpg)](https://youtu.be/GWXntjblLWw)
[![Highlight Demo on YouTube](https://img.youtube.com/vi/v57Ro8mnaP4/default.jpg)](https://youtu.be/v57Ro8mnaP4)

## How to Install and Run

* Just download and install the latest release.

* Alternatively, if you like to build your own, download or clone a repository then execute makebuild.py. Python 3.x, Python packages in the requirements.pip file, and InnoSetup is required.

  ```bash
  pip install requirements.pip
  choco install innosetup
  python makebuild.py
  ```

* Or just run without build, with following command.

  ```bash
  python ./source/main.pyw  # with terminal
  pythonw ./source/main.pyw  # without terminal
  pymp.exe  # run main.pyw with launcher
  ```
  
* Following argument can be passed while instance is running.

  ```bash
  python ./source/main.pyw [path/to/track.mp3]
  pythonw ./source/main.pyw [path/to/track.mp3]
  pymp.exe [path/to/track.mp3]  # run main.pyw with launcher
  ```

## Supported platforms

* Microsoft Windows 10, Windows 11
* Other versions of Windows have not been tested yet.
* With some modifications, it can also work on macOS.

## TODO

* Remove legacy code.
* Automatic update supports via git release page.
* VST plug-in edit panel. Multiple VST plug-in chain supports.
* Change preference file from python shelve object to JSON.
* Internet radio support such as SouthCast and IceCast. In fact, un4seen BASS library supports internet radio.
* Mac OSX support.
* Adjustable playlist and tracklist splitter supports.

