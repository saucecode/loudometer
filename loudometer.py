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

from collections import defaultdict
from fixedacc import fixedaccumulator

__version__ = 'loudometer/1.0.0'
CONFIG_VERSION = 1000

print(__version__, CONFIG_VERSION)

log.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S', level=log.INFO)

import socket, select

def generate_config():
	with open('config.json', 'w') as f:
		template = {
			'print_volume_every_second': False,
			'accumulator_size': 2,
			"active": True,
			'version': CONFIG_VERSION,
			'udp_commands': True,
			'udp_commands_port': 36591,
			'input_device_name': '',
			'default_trigger': {
				'http_target': 'http://127.0.0.1:8888/press/bank/5/3',
				'channels': [1,2,3,4],
				'silence_level': 5,
				'silence_time_ms': 5000,
				'delay_ms': 500,
				'trigger_hold_time_ms': 1000
			},
			'triggers': [
				{
					'name': 'camera one',
					'http_target': 'http://127.0.0.1:8888/press/bank/1/2',
					'channels': [3],
					'channel_volume_thresholds': [300],
					'delay_ms': 500,
					'priority': 1,
					'trigger_hold_time_ms': 1000
				},
				{
					'name': 'camera two',
					'http_target': 'http://127.0.0.1:8888/press/bank/2/2',
					'channels': [4],
					'channel_volume_thresholds': [400],
					'delay_ms': 500,
					'priority': 1,
					'trigger_hold_time_ms': 1000
				},
				{
					'name': 'wide shot',
					'http_target': 'http://127.0.0.1:8888/press/bank/3/2',
					'channels': [3, 4],
					'channel_volume_thresholds': [300, 400],
					'delay_ms': 200,
					'priority': 5,
					'trigger_hold_time_ms': 2000
				}
			]
		}
		json.dump(template, f, indent=4)

def load_config():
	with open('config.json', 'r') as f:
		return json.load(f)
	log.info('Configuration (re)loaded')





if not os.path.exists('config.json'):
	log.info('Generating configuration file... ')
	generate_config()
	log.info('Done. This program will now exit. Start the program again when you have entered your values.')
	input('Press enter to close...')
	sys.exit(0)

config = load_config()

if (detected_version := config.get('version', 0)) != CONFIG_VERSION:
	log.warning(f'Configuration file may be out of date! Detected version: {detected_version}. Current version: {CONFIG_VERSION}.')
	log.warning('Please backup your config (optional) and delete the config file. It will be regenerated on the next run.')
	input('Press enter to close...')
	sys.exit(0)

p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')
device_data = {}

for i in range(numdevices):
	if (device_info := p.get_device_info_by_host_api_device_index(0, i)).get('maxInputChannels') >= 0:
		device_data[i] = device_info
		print("Device ID ", i, " - ", device_info.get('name'), '(has',device_info.get('maxInputChannels', 'ERROR'),'channels)')


if not config.get('input_device_name'):
	try:
		print('No default device has been set in the config (input_device_name).')
		index = int(input('Enter the device ID number to listen to: '))
		
		assert index < numdevices
		
		reset_config = input(f'Would you like to set "{device_data[index]["name"]}" as the configured default? y/N ').lower() == 'y'
		if reset_config:
			config['input_device_name'] = device_data[index]['name']
			with open('config.json', 'w') as f:
				json.dump(config, f, indent=4)
		
	except:
		log.info('Failed!')
		sys.exit(1)
		
else:
	# search for the device with the name
	candidate_indices = [idx for idx, device_info in device_data.items() if device_info.get('name').startswith(config.get('input_device_name'))]
	
	match len(candidate_indices):
		case 0:
			log.error(f'Could not find a device named {config.get("input_device_name")}! Please update your configuration.')
			input('Press enter to close...')
			sys.exit(0)
		
		case 1:
			log.info(f'{config.get("input_device_name")} was found!')
			index = candidate_indices[0]
			
		case _:
			log.warning(f'Found multiple devices that start with {config.get("input_device_name")}:')
			for idx in candidate_indices:
				log.warning(f' - ({idx}) ' + device_data[idx].get('name'))
			log.warning('Please update your configuration with a more specific name.')
			input('Press enter to close...')
			sys.exit(0)

FORMAT = pyaudio.paInt16
CHANNELS = device_data[index]['maxInputChannels']
CHUNK = 1024
RATE = int(device_data[index]['defaultSampleRate'])

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, input_device_index=index)

log.info(f'Starting to listen on {CHANNELS} channels')

# stately variables for the main loop
largest = [0] * CHANNELS
ticker = time.time()
next_request_after = 0
last_request_sent_to = ''
volume_accumulators = [fixedaccumulator(int(config['accumulator_size'] * RATE // CHUNK)) for _ in range(CHANNELS)]
volume_current = [0] * CHANNELS
volume_is_silent = [0] * CHANNELS # the last time at which a channel was silent
armed_trigger = {
	'priority': -1,
	'target': None,
	'expires_at': 0,
	'name': None
}

# filter out triggers for non-existent channels
# TODO these lines are repeated elsewhere!!!
log.info(f'Triggers listed in config: {len(config["triggers"])}.')
config['triggers'] = [trigger for trigger in config['triggers'] if all(chan < CHANNELS for chan in trigger['channels'])]
log.info(f'Triggers available with this audio source: {len(config["triggers"])}.')

config_poll = time.time()
config_age = os.stat('config.json').st_mtime

# prepare the UDP socket (if configured)
sock = None

if config.get('udp_commands'):
	log.info(f'Starting UDP socket on port {config.get("udp_commands_port")} [UDP_commands = true]')

	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
	sock.bind(('127.0.0.1', config.get("udp_commands_port")))
	sock.setblocking(False)

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
	
	# accumulates the calculated volumes per channel
	for index, (accumulator, data) in enumerate(zip(volume_accumulators, channels)):
		volume_current[index] = audioop.rms(data.getvalue(), 2)
		accumulator.push(volume_current[index])
	
	# check for changes in the config file, and load them
	if time.time() > config_poll + 1:
		config_poll = time.time()
		mtime = os.stat('config.json').st_mtime
		if config_age != mtime:
			config_age = mtime
			config = load_config()
			log.info('Reloaded configuration.')
			# filter out triggers for non-existent channels
			log.info(f'Triggers listed in config: {len(config["triggers"])}.')
			# TODO repeated code!
			config['triggers'] = [trigger for trigger in config['triggers'] if all(chan < CHANNELS for chan in trigger['channels'])]
			log.info(f'Triggers available with this audio source: {len(config["triggers"])}.')
	
	# printing of the recorded volume
	if config['print_volume_every_second']:
		if time.time() > ticker + 1:
			ticker = time.time()
			log.info(f'Accumulated volume per channel in the past second: {" ".join(str(int(i.average())) for i in volume_accumulators)}')
	
	
	# monitor silence for the default trigger
	current_time = time.time()
	for channel_index in config['default_trigger']['channels']:
		if channel_index < CHANNELS and volume_accumulators[channel_index].average() > config['default_trigger']['silence_level']:
			volume_is_silent[channel_index] = current_time

	# activate the default trigger if silence condition is met
	if all(
		current_time - silent_time > config['default_trigger']['silence_time_ms']/1000 \
		for channel_index, silent_time in enumerate(volume_is_silent) \
		if channel_index in config['default_trigger']['channels']
	) and config['active'] \
	and time.time() > next_request_after and armed_trigger['name'] is None \
	and last_request_sent_to != config['default_trigger']['http_target']:
		armed_trigger['priority'] = -1000
		armed_trigger['name'] = '_default_trigger_'
		armed_trigger['target'] = config['default_trigger']['http_target']
		armed_trigger['expires_at'] = config['default_trigger']['delay_ms']/1000 + current_time
		armed_trigger['trigger_hold_time_ms'] = config['default_trigger']['trigger_hold_time_ms']
		# negative volume, to disable this threshold check at firing-time
		armed_trigger['thresholds'] = {chan: -1 for chan in config['default_trigger']['channels']}

		log.info(f'The default trigger has armed for {config["default_trigger"]["delay_ms"]} ms...')
	
	# trigger monitoring
	for trigger in config['triggers']:
		if all(
			volume_accumulators[channel].average() > threshold and volume_current[channel] > threshold \
			for channel, threshold in zip(trigger['channels'], trigger['channel_volume_thresholds'])
		) and time.time() > next_request_after \
		and config['active']:
		
			if trigger['priority'] > armed_trigger['priority']:
				if armed_trigger['priority'] != -1:
					log.info(f'Trigger {armed_trigger["name"]} disarmed.')
				
				log.info(f'Trigger {trigger["name"]} is loud! Arming for {trigger["delay_ms"]} ms...')
				
				armed_trigger['priority'] = trigger['priority']
				armed_trigger['expires_at'] = time.time() + trigger['delay_ms']/1000
				armed_trigger['target'] = trigger['http_target']
				armed_trigger['name'] = trigger['name']
				armed_trigger['trigger_hold_time_ms'] = trigger['trigger_hold_time_ms']
				armed_trigger['thresholds'] = {chan: threshold for chan, threshold in zip(trigger['channels'], trigger['channel_volume_thresholds'])}
	
	# armed trigger
	if armed_trigger['priority'] != -1:
		if time.time() > armed_trigger['expires_at']:
			if all(
				volume_current[channel] > threshold for channel, threshold \
				in armed_trigger['thresholds'].items()
			):
				if last_request_sent_to != armed_trigger['target']:
					log.info(f'Sending request to {armed_trigger["target"]}')
					
					threading.Thread(target=requests.get, args=(armed_trigger["target"],)).start()
					last_request_sent_to = armed_trigger['target']
					next_request_after = time.time() + armed_trigger['trigger_hold_time_ms']/1000
				
			else:
				log.info(f'Armed trigger {armed_trigger["name"]} expired without firing (instantaneous volume too low)')
				log.info('Instant volume: ' + ' '.join(str(int(i)) for i in volume_current))
			
			# reset trigger to unarmed state
			armed_trigger = {
				'priority': -1,
				'target': None,
				'expires_at': 0,
				'name': None
			}
	
	# UDP commands
	if config.get('udp_commands') and sock and select.select([sock], [], [], 0)[0]:
		command, address = sock.recvfrom(64)
		if command:
			if command == b'DISARM\n':
				log.info(f'Received DISARM command from {address}')
				config['active'] = False
			if command == b'ARM\n':
				log.info(f'Received ARM command from {address}')
				config['active'] = True

print('Done')

stream.close()
p.terminate()