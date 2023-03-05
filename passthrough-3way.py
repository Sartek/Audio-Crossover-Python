import time
import _iirfilter
import numpy as np
import ctypes
import winmm

from enum import Enum

"""
Filter setup and c wrapper in _iirfilter.py

C filter algorithm in filters.cpp as well as filters.h

Works best on my pc with VB audio cable for grabbing audio stream https://vb-audio.com/Cable/index.htm
and asio4all for low latency exclusive access to sound devices https://www.asio4all.org/

some configuration is required

This file is a mess and has only been used on my computer. in need of a partial rewrite
"""

class SpeakerType(Enum):
    TWEETERS = 2
    MIDRANGE = 3
    SUBWOOFER = 4

samplerate = 96000
blocksize = 256

bass_cut = 150
mid_cut_low = 135#125#125
mid_cut_high = 5000#1500
high_cut = 2500

volume = 1#.5
subwoofer_volume = 0.5#75#.5
mid_volume = 0.35#.5#25#.25
tweeters_volume = 0.5#3#25#4#.7

if __name__ == '__main__':
    filters = list()
    input_data = list()
    output_data = list()
    emptyblock = np.zeros((blocksize,1),dtype='float64')
    channels = 5
    
    
    #We could create a thread for each audio channel we need to do processing for but due to how windows handles multiple threads it actually increases latency
    pydata = [0] * blocksize
    for value in range(channels):
        if value == 0:
            f_type = SpeakerType.TWEETERS.value
        elif value == 1:
            f_type = SpeakerType.TWEETERS.value
        elif value == 2:
            f_type = SpeakerType.MIDRANGE.value
        elif value == 3:
            f_type = SpeakerType.MIDRANGE.value
        elif value == 4:
            f_type = SpeakerType.SUBWOOFER.value
        else:
            f_type = 0
            
            
        if f_type == SpeakerType.TWEETERS.value:
            filters.append(_iirfilter.IIRFilter(2,[high_cut],'highpass',design='butter',fs=samplerate))
        elif f_type == SpeakerType.MIDRANGE.value:
            filters.append(_iirfilter.IIRFilter(2,[mid_cut_low,mid_cut_high],'bandpass',design='butter',fs=samplerate))
        elif f_type == SpeakerType.SUBWOOFER.value:
            filters.append(_iirfilter.IIRFilter(2,[bass_cut],'lowpass',design='butter',fs=samplerate))
        input_data.append((ctypes.c_double * len(pydata))(*pydata))
        output_data.append(np.zeros((blocksize,1),dtype='float64'))
        
    pydata = None
        
    #sounddevice stuff
    import sounddevice as sd
    sd.default.samplerate = samplerate
    winmm.begin(0)
    
    wasapi_exclusive = sd.WasapiSettings(exclusive=True)
    print(sd.get_portaudio_version())

    input_device = None
    output_device = None
    input_channels = None
    output_channels = None
    host_api = 2#4
    
    if host_api == 0:       
        input_device_name = 'CABLE Output (VB-Audio Virtual '
        output_device_name = 'Speakers (USB Sound Device     '
    elif host_api == 1:
        input_device_name = 'CABLE Output (VB-Audio Virtual Cable)'
        output_device_name = 'Speakers (USB Sound Device        )'
    elif host_api == 2:
        input_device_name = 'ASIO4ALL v2'
        output_device_name = 'ASIO4ALL v2'
    elif host_api == 3:
        input_device_name = 'CABLE Output (VB-Audio Virtual Cable)'
        output_device_name = 'Speakers (USB Sound Device        )'
    elif host_api == 4:
        input_device_name = 'CABLE Output (VB-Audio Point)'
        output_device_name = 'Speakers (USB Sound Device)'
    #for host_api in range(5):
    for device in sd.query_hostapis(host_api)['devices']:
        print(sd.query_devices(device)['name'])
        if(sd.query_devices(device)['name'] == input_device_name):
            #print(sd.query_devices(device))
            input_device = device
            input_channels = sd.query_devices(device)['max_input_channels']
            input_channels = 2#force to 2 channels
        if(sd.query_devices(device)['name'] == output_device_name):
            #print(sd.query_devices(device))
            output_device = device
            output_channels = sd.query_devices(device)['max_output_channels']
    
    if (input_device == None or output_device == None):
        print('Error: cannot find input or output device')
        raise SystemExit
    
    filter_state = True
    print(input_channels)
    print(output_channels)
    
    def callback(indata, outdata, frames, time, status):
        for value in range(channels):
            #Check if subwoofer channel
            if value == 4:#was 5 bug?
                input_data[value][:] = np.reshape((indata[ : , 0] ), -1) + np.reshape((indata[ : , 1] ), -1)
            else:
                input_data[value][:] = np.reshape((indata[ : , value%2] ), -1)
        
        if filter_state == True:
            for num in range (channels):
                filters[num].filter(input_data[num])
                output_data[num][:] = np.reshape(input_data[num],(-1, 1))
                     
            if output_channels == 2:
                outdata[:] = np.hstack((output_data[0],output_data[1])) * volume
            elif output_channels == 6:
                outdata[:] = np.hstack((output_data[0],output_data[1],output_data[4],output_data[4],output_data[2],output_data[3])) * volume
            elif output_channels == 8:
                outdata[:] = np.hstack((
                    output_data[2] * mid_volume,
                    output_data[3] * mid_volume,
                    output_data[4] * 0 * subwoofer_volume,
                    output_data[4] * 0 * subwoofer_volume,
                    output_data[0] * tweeters_volume,
                    output_data[1] * tweeters_volume,
                    output_data[4] * 1 * subwoofer_volume,
                    output_data[4] * 1 * subwoofer_volume)) * volume
            elif output_channels ==16:
                #print("weird amount of channels")
                outdata[:] = np.hstack((
                    output_data[2] * mid_volume,
                    output_data[3] * mid_volume,
                    output_data[4] * 0 * subwoofer_volume,
                    output_data[4] * 0 * subwoofer_volume,
                    output_data[0] * tweeters_volume,
                    output_data[1] * tweeters_volume,
                    output_data[4] * 1 * subwoofer_volume,
                    output_data[4] * 1 * subwoofer_volume,
                    emptyblock,emptyblock,emptyblock,emptyblock,
                    emptyblock,emptyblock,emptyblock,emptyblock)) * volume
            elif output_channels == 10:
                outdata[:] = np.hstack((output_data[0],output_data[1],output_data[4],output_data[4],emptyblock,emptyblock,output_data[2],output_data[3],output_data[0],output_data[1])) * volume
        else:
            if output_channels == 6:
                outdata[:] = np.hstack((indata,np.zeros((blocksize,4),dtype='float32'))) * volume
            elif output_channels == 8:
                outdata[:] = np.hstack((indata,indata,indata,indata)) * volume
            elif output_channels == 10:
                outdata[:] = np.hstack((indata,indata,indata,indata,indata)) * volume
            else:
                outdata[:] = indata * volume
                
                
    try:
        with sd.Stream(device=(input_device, output_device),latency='low',#latency='low',
                    samplerate=samplerate, blocksize=blocksize,
                    channels=(input_channels,output_channels), callback=callback):
            print('#' * 80)
            print('press Return to toggle')
            print('#' * 80)
            while True:
                input()
                #if True:
                if False:
                    print("Filter = disabled")
                    filter_state = False
                else:
                    print("Filter = enabled")
                    filter_state = True
                input()
                print("Filter = enabled")
                filter_state = True
    except KeyboardInterrupt:
        print('\nInterrupted by user')
    except Exception as e:
        print(type(e).__name__ + ': ' + str(e))
    finally:
        winmm.end(0)