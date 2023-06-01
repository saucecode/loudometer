'''
    fixedacc.py
    Copyright (c) 2023 Julian Cahill <cahill.julian@gmail.com>

	Permission is hereby granted, free of charge, to any person obtaining a copy
	of this software and associated documentation files (the "Software"), to deal
	in the Software without restriction, including without limitation the rights
	to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
	copies of the Software, and to permit persons to whom the Software is
	furnished to do so, subject to the following conditions:

	The above copyright notice and this permission notice shall be included in all
	copies or substantial portions of the Software.

	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
	OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
	SOFTWARE.
'''

import collections

__version__ = '1.0.0'

class fixedaccumulator(object):
	def __init__(self, limit : int, default:int=0):
		self.value_sum = default * limit
		self.history = collections.deque([default]*limit, limit)
	
	def push(self, value):
		self.value_sum -= self.history.pop()
		self.history.appendleft(value)
		self.value_sum += value
	
	def average(self):
		return self.value_sum / self.history.maxlen

if __name__ == "__main__":
	print('Testing fixedaccumulator')
	
	a = fixedaccumulator(10)
	
	for i in range(10):
		a.push(i)
	assert a.average() == 4.5
	
	for i in range(10):
		a.push(0)
	
	assert a.average() == 0.0
	
	print('Tests pass!')