# PlayAudioGui
Simple Python GUI to play (multi-channel) audio files and switch between them on the fly.

Quickstart
---

Clone this repository and install dependencies with

```
conda create -n demo Python=3 tk numpy portaudio
conda activate demo
pip install soundfile sounddevice
```

Then adapt the list of audio files in the script -- that's it!

If you prefer, you can pass the audio files directly:
```
python play_audio_gui.py -f myaudio.wav -f emptyButton
```
Or multiple files, even wildcards:
```
python play_audio_gui.py -F *.wav
```
Or pass a directory and it will load all sound files contained in the specified folder:

```
python play_audio_gui.py -d ./Path/To/SoundFiles/
```
