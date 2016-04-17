import sys
from Queue import Queue
from ctypes import POINTER, c_ubyte, c_void_p, c_ulong, cast
from requests import get as get_request
from pulseaudio.lib_pulseaudio import *
import json
import requests 

# edit to match your sink
SINK_NAME = 'alsa_output.0.analog-stereo'
METER_RATE = 344
MAX_SAMPLE_VALUE = 127
DISPLAY_SCALE = 2
MAX_SPACES = MAX_SAMPLE_VALUE >> DISPLAY_SCALE

api_url = "http://iris.local/api/set/raw?"

def updateLights(ledArray): 
    serialized = json.dumps(ledArray)
    url = api_url + "leds=" + serialized
    #print url 
    requests.get(url).content 

class PeakMonitor(object):

    def __init__(self, sink_name, rate):
        self.sink_name = sink_name
        self.rate = rate

        # Wrap callback methods in appropriate ctypefunc instances so
        # that the Pulseaudio C API can call them
        self._context_notify_cb = pa_context_notify_cb_t(self.context_notify_cb)
        self._sink_info_cb = pa_sink_info_cb_t(self.sink_info_cb)
        self._stream_read_cb = pa_stream_request_cb_t(self.stream_read_cb)

        # stream_read_cb() puts peak samples into this Queue instance
        self._samples = Queue()

        # Create the mainloop thread and set our context_notify_cb
        # method to be called when there's updates relating to the
        # connection to Pulseaudio
        _mainloop = pa_threaded_mainloop_new()
        _mainloop_api = pa_threaded_mainloop_get_api(_mainloop)
        context = pa_context_new(_mainloop_api, 'peak_demo')
        pa_context_set_state_callback(context, self._context_notify_cb, None)
        pa_context_connect(context, None, 0, None)
        pa_threaded_mainloop_start(_mainloop)

    def __iter__(self):
        while True:
            yield self._samples.get()

    def context_notify_cb(self, context, _):
        state = pa_context_get_state(context)

        if state == PA_CONTEXT_READY:
            print "Pulseaudio connection ready..."
            # Connected to Pulseaudio. Now request that sink_info_cb
            # be called with information about the available sinks.
            o = pa_context_get_sink_info_list(context, self._sink_info_cb, None)
            pa_operation_unref(o)

        elif state == PA_CONTEXT_FAILED :
            print "Connection failed"

        elif state == PA_CONTEXT_TERMINATED:
            print "Connection terminated"

    def sink_info_cb(self, context, sink_info_p, _, __):
        if not sink_info_p:
            return

        sink_info = sink_info_p.contents
        print '-'* 60
        print 'index:', sink_info.index
        print 'name:', sink_info.name
        print 'description:', sink_info.description

        if sink_info.name == self.sink_name:
            # Found the sink we want to monitor for peak levels.
            # Tell PA to call stream_read_cb with peak samples.
            print
            print 'setting up peak recording using', sink_info.monitor_source_name
            print
            samplespec = pa_sample_spec()
            samplespec.channels = 1
            samplespec.format = PA_SAMPLE_U8
            samplespec.rate = self.rate

            pa_stream = pa_stream_new(context, "peak detect demo", samplespec, None)
            pa_stream_set_read_callback(pa_stream,
                                        self._stream_read_cb,
                                        sink_info.index)
            pa_stream_connect_record(pa_stream,
                                     sink_info.monitor_source_name,
                                     None,
                                     PA_STREAM_NOFLAGS)

    def stream_read_cb(self, stream, length, index_incr):
        data = c_void_p()
        pa_stream_peek(stream, data, c_ulong(length))
        data = cast(data, POINTER(c_ubyte))
        self.spectrum = []
        string = ""
        for i in xrange(length):
            # When PA_SAMPLE_U8 is used, samples values range from 128
            # to 255 because the underlying audio data is signed but
            # it doesn't make sense to return signed peaks.
            self._samples.put(data[i] - 128)
        pa_stream_drop(stream)

def main():
    audioData = open("audio.txt", "w+")
    monitor = PeakMonitor(SINK_NAME, METER_RATE)
    running = [0] 
    n = 0; 
    numLights = 90 
    sampleRate = 1 
    red = 0xFF003300
    blue = 0xFF0000FF
    green = 0xFFFF0000
    off = 0xFF000000
    arr = [[0 for x in range(25)] for x in range(6)] 
    sum = [0] * sampleRate; 
    min = [0] * sampleRate;
    max = [0] * sampleRate; 
    for sample in monitor:
        sample = sample >> DISPLAY_SCALE
        bar = '>' * sample
        spaces = ' ' * (MAX_SPACES - sample)
        #print ' %3d %s%s\r' % (sample, bar, spaces),
        sys.stdout.flush()
        #spectrum = [0] * 6
        for i in range(sampleRate):
            try:
                #spectrum[i] = (monitor._samples.get(0))
                sum[i] -= arr[n%25][i] 
                arr[n%25][i] = (monitor._samples.get(0))
                sum[i] += arr[n%25][i]
                #pure debug lol print(sum[i], arr[n%25][i])
                #if arr[n%25][i] > max[i]:
                #    max[i] = arr[n%25][i]
                #if arr[n%25][i] < min[i]: 
                #    min[i] = arr[n%25][i] 
            except:
                pass  
        light = 0;  
        lightMax = 200;                            
        if n%25 == 0: 
            #for i in range(sampleRate): 
             #   print(sum[i]/25 , '\t' , max[i] , '\t' , min[i])
            light = abs(sum[0]/25) 
            if abs(sum[0]/25) > lightMax: 
                light = lightMax
            print(light, sum[0]/25, '\n')
            lightLength = (numLights * light) / lightMax
            deadLight = numLights - lightLength
            ledBuffer = [0] * (numLights * 2)
            for j in range(deadLight):
                ledBuffer[j] = red
                ledBuffer[(numLights * 2) - 1 - j] = red 
            for j in range(deadLight, deadLight + lightLength): 
                ledBuffer[j] = blue 
                ledBuffer[(numLights * 2) - 1 - j] = blue
        if n%10 == 0:
            updateLights(ledBuffer)
        n += 1 
	   #for i in spectrum:
	   #     print i 
	   #print('\n') 
#        rgb = int((float(sum(spectrum))/400.0)  * 100)
#        rgb = ('#%02x%02x%02x' % (0,0,rgb))[1:]
        
#        print rgb
#        get_request('http://192.168.1.13:8081/' + rgb)



if __name__ == '__main__':
    main()
