'''
    loudometer - loudometer.py
    Copyright (C) 2023  Julian Cahill <cahill.julian@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import wave
import sys

import os, json, time, requests, threading
import logging as log

import pyaudio
import audioop

log.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S', level=log.INFO)



def generate_config():
	with open('config.json', 'w') as f:
		json.dump({
			'http_target': 'http://127.0.0.1:8888/press/bank/1/2',
			'print_volume_every_second': True,
			'volume_trigger_threshold': 1000,
			'minimum_time_between_triggers_in_seconds': 10,
			"active": True
		}, f, indent=4)

def load_config():
	with open('config.json', 'r') as f:
		return json.load(f)
	log.info('Configuration (re)loaded')





if not os.path.exists('config.json'):
	log.info('Generating configuration file... ')
	generate_config()
	log.info('Done. This program will now exit. Start the program again when you have entered your values.')
	sys.exit(0)

config = load_config()

p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')

for i in range(numdevices):
	if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) >= 0:
		print("Input Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0, i).get('name'))

try:
	index = int(input('Enter the device ID number to listen to: '))
except:
	log.info('Failed!')
	sys.exit(1)

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1 if sys.platform == 'darwin' else 2
RATE = 44100

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, input_device_index=index)

log.info('Starting to listen!')

largest = 0
ticker = time.time()
last_request_sent = 0

config_poll = time.time()
config_age = os.stat('config.json').st_mtime

while 1:
	data = stream.read(CHUNK)
	volume = audioop.rms(data,2)
	
	# check for changes in the config file, and load them
	if time.time() > config_poll + 1:
		config_poll = time.time()
		mtime = os.stat('config.json').st_mtime
		if config_age != mtime:
			config_age = mtime
			config = load_config()
			log.info('Reloaded configuration.')
	
	# printing of the recorded volume
	if config['print_volume_every_second']:
		largest = max(volume, largest)
		if time.time() > ticker + 1:
			ticker = time.time()
			log.info(f'Highest Volume in the past second: {largest}')
			largest = 0
	
	if volume > config['volume_trigger_threshold'] and time.time() > last_request_sent + config['minimum_time_between_triggers_in_seconds'] and config['active']:
		target = config['http_target']
		log.info(f'It\'s loud! Sending request to {target}')
		# requests.get(target)
		threading.Thread(target=requests.get, args=(target,)).start()
		last_request_sent = time.time()

print('Done')

stream.close()
p.terminate()