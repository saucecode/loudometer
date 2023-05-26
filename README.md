# loudometer.py

loudometer is an audio input monitor that triggers a web request when it detects noise.

Depends on `pip install pyaudio`.

This project was made to send commands to Bitfocus Companion, to switch camera views on a video stream depending on the loudness of the audio input. The input in this instance came from a RODEcaster Pro, presenting to the OS as a single 14-channel audio source. It can be used to trigger HTTP requests to any web address.

`loudometer.py` will let you select an audio stream source, and will monitor the volume levels of each channel in that stream.

# Usage

The first time you run the program it will generate a template config file `config.json` and then exit. Configure the `input_device_name` (if you know it), and enter web URLs to target when a channel *gets hot*. An empty string means do nothing.

The configuration file will be reloaded as the program runs.

To test if PyAudio is working and installed correctly, and to see a list of available input devices, run the `test_pyaudio.py` script.

Further instructions and tips are available in `instructions.txt`.

# License

GPL-3.0. See LICENSE.