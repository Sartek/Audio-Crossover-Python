# System imports
import os
import ctypes
from enum import Enum

# External imports
import numpy as np
import psutil

# Local imports
import _iirfilter
import winmm

# Set environment variable before importing sounddevice to enable asio support. Value is not important.
os.environ["SD_ENABLE_ASIO"] = "1"

# Set thread priority to realtime
p = psutil.Process()
p.ionice(psutil.IOPRIO_NORMAL)
p.nice(psutil.REALTIME_PRIORITY_CLASS)

class SpeakerType(Enum):
    TWEETERS = 2
    MIDRANGE = 3
    SUBWOOFER = 4

# The sample rate for audio processing, which determines the number of samples per second.
# This value is also used to configure the filters to ensure they operate correctly.
samplerate = 96000

# Buffer size to pass to filters
blocksize = 512

bass_cutoff = 140
mid_cutoff_low = 100
mid_cutoff_high = 3000
high_cutoff =  2000

master_volume = 1
subwoofer_volume = 1
mid_volume = .8
tweeters_volume = .35


# Make sure to configure ASIO4ALL to use the correct input and output devices via system tray icon
input_device_name = 'ASIO4ALL v2'
output_device_name = 'ASIO4ALL v2'

# The host API type for sounddevice, where 2 corresponds to ASIO (Audio Stream Input/Output) for low-latency audio.
host_api = 2

SUBWOOFER_CHANNEL_INDEX = 4

if __name__ == '__main__':
    filters = list()
    channels = 5
    input_data = [(ctypes.c_double * blocksize)() for _ in range(channels)]
    output_data = [np.zeros((blocksize, 1), dtype='float64') for _ in range(channels)]
    emptyblock = np.zeros((blocksize,1),dtype='float64')
    
    # Create a dictionary to map value to f_type
    f_type_map = {
        0: SpeakerType.TWEETERS.value,
        1: SpeakerType.TWEETERS.value,
        2: SpeakerType.MIDRANGE.value,
        3: SpeakerType.MIDRANGE.value,
        4: SpeakerType.SUBWOOFER.value
    }
    
    # Empty array to initialize the input data
    pydata = [0] * blocksize

    # We could create a thread for each audio channel filter.
    # unfortunately creating a thread for each audio channel increases latency on Windows.
    # Create filters for each channel
    for value in range(channels):
        f_type = f_type_map.get(value, 0)
        if f_type == SpeakerType.TWEETERS.value:
            filters.append(_iirfilter.IIRFilter(2,[high_cutoff],'highpass',design='butter',fs=samplerate))
        elif f_type == SpeakerType.MIDRANGE.value:
            filters.append(_iirfilter.IIRFilter(2,[mid_cutoff_low,mid_cutoff_high],'bandpass',design='butter',fs=samplerate))
        elif f_type == SpeakerType.SUBWOOFER.value:
            filters.append(_iirfilter.IIRFilter(2,[bass_cutoff],'lowpass',design='butter',fs=samplerate))

    # No longer needed
    pydata = None
        
    # Sounddevice setup
    import sounddevice as sd
    sd.default.samplerate = samplerate

    # Set Windows timer resolution to the lowest possible value to reduce latency.
    # Reducing the timer resolution allows the system to handle more timer events per second,
    # which can help in achieving lower latency for real-time audio processing.
    winmm.begin(0)
    
    # Set WASAPI to exclusive mode for lowest possible latency
    wasapi_exclusive = sd.WasapiSettings(exclusive=True)

    print(sd.get_portaudio_version())

    input_device = None
    output_device = None

    device_names = [sd.query_devices(device)['name'] for device in sd.query_hostapis(host_api)['devices']]
    for device_name in device_names:
        print(device_name)
        if device_name == input_device_name:
            input_device = sd.query_hostapis(host_api)['devices'][device_names.index(device_name)]
            input_channels = sd.query_devices(input_device)['max_input_channels']
            input_channels = 2  # force to 2 channels
        if device_name == output_device_name:
            output_device = sd.query_hostapis(host_api)['devices'][device_names.index(device_name)]
            output_channels = sd.query_devices(output_device)['max_output_channels']
    if input_device is None or output_device is None:
        print('Error: cannot find input or output device')
        raise SystemExit
    
    print(input_channels)
    print(output_channels)

    filter_state = True
    
    def audio_callback(indata, outdata, frames, time, status):
        """
        Audio callback function for processing audio data.

        This function processes the input audio data and applies filtering based on the 
        specified filter state. It handles different channels, including summing channels 
        for mono output in the subwoofer channel. The processed data is then copied to 
        the output array, with volume adjustments applied to different channels.
        Note:
        - The function assumes the presence of global variables such as `channels`, 
          `SUBWOOFER_CHANNEL_INDEX`, `input_data`, `filter_state`, `filters`, `output_data`, 
          `output_channels`, `mid_volume`, `tweeters_volume`, `subwoofer_volume`, and 
          `master_volume`.
        - If `filter_state` is True, the input data is filtered and copied to the output 
          data with volume adjustments.
        - If `filter_state` is False, the input data is directly copied to the output data 
          with volume adjustments.
        """
        for value in range(channels):
            # Check if subwoofer channel and if so sum the two channels for mono output
            if value == SUBWOOFER_CHANNEL_INDEX:
                input_data[value][:] = np.reshape((indata[ : , 0] ), -1) + np.reshape((indata[ : , 1] ), -1)
            else:
                input_data[value][:] = np.reshape((indata[ : , value%2] ), -1)

        if filter_state:
            for num in range(channels):
                # Give the filter the input data
                filters[num].filter(input_data[num])
                # Copy the filtered input data to the output data
                output_data[num][:] = np.reshape(input_data[num], (-1, 1))

            if output_channels == 8:
                outdata[:] = np.hstack((
                    output_data[2] * mid_volume,
                    output_data[3] * mid_volume,
                    output_data[4] * 0,  # empty channel
                    output_data[4] * 0,  # empty channel
                    output_data[0] * tweeters_volume,
                    output_data[1] * tweeters_volume,
                    output_data[4] * subwoofer_volume,
                    output_data[4] * subwoofer_volume)) * master_volume
        else:
            if output_channels == 8:
                outdata[:] = np.hstack((indata, indata, indata, indata)) * master_volume
    try:
        with sd.Stream(device=(input_device, output_device),latency='low',
                    samplerate=samplerate, blocksize=blocksize,
                    channels=(input_channels,output_channels), callback=audio_callback):
            print('#' * 80)
            print('press Return to toggle')
            print('#' * 80)
            while True:
                input()
                #if filter_state == True:
                if False:
                    print("Filter = disabled")
                    filter_state = False
                else:
                    print("Filter = enabled")
                    filter_state = True
                input()
    except KeyboardInterrupt:
        print('\nInterrupted by user')
    except Exception as e:
        print(type(e).__name__ + ': ' + str(e))
    finally:
        # Reset the timer resolution
        winmm.end(0)