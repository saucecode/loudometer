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
import io
import itertools
import logging as log

import pyaudio
import audioop

log.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S', level=log.INFO)



def generate_config():
	with open('config.json', 'w') as f:
		template = {
			'print_volume_every_second': True,
			'volume_trigger_threshold': 1000,
			'minimum_time_between_triggers_in_seconds': 10,
			"active": True
		}
		for i in range(32):
			template[f'http_target_channel{i}'] = ''
		template['http_target_channel0'] = 'http://127.0.0.1:8888/press/bank/1/2'
		json.dump(template, f, indent=4)

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
device_data = {}

for i in range(numdevices):
	if (device_info := p.get_device_info_by_host_api_device_index(0, i)).get('maxInputChannels') >= 0:
		device_data[i] = device_info
		print("Device ID ", i, " - ", device_info.get('name'), '(has',device_info.get('maxInputChannels', 'ERROR'),'channels)')

try:
	index = int(input('Enter the device ID number to listen to: '))
except:
	log.info('Failed!')
	sys.exit(1)

FORMAT = pyaudio.paInt16
CHANNELS = device_data[index]['maxInputChannels']
CHUNK = 1024
RATE = 44100

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, input_device_index=index)

log.info(f'Starting to listen on {CHANNELS} channels')

largest = [0] * CHANNELS
ticker = time.time()
last_request_sent = [0] * CHANNELS

config_poll = time.time()
config_age = os.stat('config.json').st_mtime

while 1:
	raw = stream.read(CHUNK)
	data = io.BytesIO(raw)
	
	assert FORMAT == pyaudio.paInt16
	assert len(raw) == CHUNK * 2 * CHANNELS # 2 because Int16 is 2 bytes
	
	# stream data is interlaced by channel.
	# this will run through the whole chunk and copy the samples to their respective channels
	channels = [io.BytesIO() for _ in range(CHANNELS)]
	channels_selector = itertools.cycle(channels)
	
	while short := data.read(2):
		next(channels_selector).write(short)
	
	# calculates the volume per channel
	volumes = [audioop.rms(data.getvalue(), 2) for data in channels]
	volume = volumes[0]
	
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
		largest = [max(volume, largest[channel]) for channel, volume in enumerate(volumes)]
		if time.time() > ticker + 1:
			ticker = time.time()
			log.info(f'Highest Volume per channel in the past second: {" ".join(str(i) for i in largest)}')
			largest = [0] * CHANNELS
	
	for channel, volume in enumerate(volumes):
		if volume > config['volume_trigger_threshold'] \
		and time.time() > last_request_sent[channel] + config['minimum_time_between_triggers_in_seconds'] \
		and config['active'] \
		and (target := config.get(f'http_target_channel{channel}')):
			
			log.info(f'Channel {channel} is loud! Sending request to {target}')
			# requests.get(target)
			threading.Thread(target=requests.get, args=(target,)).start()
			last_request_sent[channel] = time.time()

print('Done')

stream.close()
p.terminate()