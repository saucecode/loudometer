'''
    loudometer - test_pyaudio.py
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

import pyaudio

p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')

for i in range(numdevices):
	if (device_info := p.get_device_info_by_host_api_device_index(0, i)).get('maxInputChannels') >= 0:
		print("Device ID ", i, " - ", device_info.get('name'), '(has',device_info.get('maxInputChannels', 'ERROR'),'channels)')

input('Press enter to close...')