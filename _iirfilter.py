import ctypes
import scipy.signal as signal

filtersdll = ctypes.CDLL("./filters.dll")

filter_func = getattr(filtersdll, '_Z6filterPdiiS_S_S_S_S_S_')
filter_func.restype = ctypes.c_double

class IIRFilter:
    def createCoeffs(self, order, cutoff,filterType,design,rp=1, rs=1,fs=0):
        
        # Defining the acceptable inputs for the design and filterType params
        designs = ['butter','cheby1','cheby2']
        filterTypes1 = ['lowpass','highpass','Lowpass','Highpass','low','high']
        filterTypes2 = ['bandstop','bandpass','Bandstop','Bandpass']
        
        # Error handling: other errors can arise too, but those are dealt with 
        # in the signal package.
        self.isThereAnError = 1 #if there was no error then it will be set to 0
        self.COEFFS = [0] #with no error this will hold the coefficients
        
        if design not in designs:
            print('Gave wrong filter design! Remember: butter, cheby1, cheby2.')
        elif filterType not in filterTypes1 and filterType not in filterTypes2:
            print('Gave wrong filter type! Remember: lowpass, highpass', 
                  ', bandpass, bandstop.')
        elif fs < 0:
            print('The sampling frequency has to be positive!')
        else:
            self.isThereAnError = 0
        
        # If fs was given then the given cutoffs need to be normalised to Nyquist
        if fs and self.isThereAnError == 0:
            for i in range(len(cutoff)):
                cutoff[i] = cutoff[i]/fs*2
        
        if design == 'butter' and self.isThereAnError == 0:
            self.COEFFS = signal.butter(order,cutoff,filterType,output='sos').tolist()
        elif design == 'cheby1' and self.isThereAnError == 0:
            self.COEFFS = signal.cheby1(order,rp,cutoff,filterType,output='sos').tolist()
        elif design == 'cheby2' and self.isThereAnError == 0:
            self.COEFFS = signal.cheby2(order,rs,cutoff,filterType,output='sos').tolist()
        
        return self.COEFFS

    def __init__(self, order, cutoff,filterType,design,rp=1, rs=1,fs=0):
        self.COEFFS = self.createCoeffs(order,cutoff,filterType,design,rp,rs,fs)
        print("#####")
        self.pystages = len(self.COEFFS)
        print(self.pystages)
        
        pyacc_input = [0] * self.pystages
        pyacc_output = [0] * self.pystages
        pybuffer1 = [0] * self.pystages
        pybuffer2 = [0] * self.pystages
        pyFIRCOEFFS = [0] * self.pystages * 3
        pyIIRCOEFFS = [0] * self.pystages * 2

        for i in range(self.pystages):
            pyFIRCOEFFS[i*3+0] = self.COEFFS[i][0]
            pyFIRCOEFFS[i*3+1] = self.COEFFS[i][1]
            pyFIRCOEFFS[i*3+2] = self.COEFFS[i][2]

            pyIIRCOEFFS[i*2+0] = self.COEFFS[i][4+0]
            pyIIRCOEFFS[i*2+1] = self.COEFFS[i][4+1]

            pyacc_input[i] = 0.0
            pyacc_output[i] = 0.0
            pybuffer1[i] = 0.0
            pybuffer2[i] = 0.0
            
        
        self.acc_input = (ctypes.c_double * len(pyacc_input))(*pyacc_input)
        self.acc_output = (ctypes.c_double * len(pyacc_output))(*pyacc_output)
        self.buffer1 = (ctypes.c_double * len(pybuffer1))(*pybuffer1)
        self.buffer2 = (ctypes.c_double * len(pybuffer2))(*pybuffer2)
        self.FIRCOEFFS = (ctypes.c_double * len(pyFIRCOEFFS))(*pyFIRCOEFFS)
        self.IIRCOEFFS = (ctypes.c_double * len(pyIIRCOEFFS))(*pyIIRCOEFFS)
        print(list(self.FIRCOEFFS))
        print(list(self.IIRCOEFFS))
    
    def filter(self,data):
        filter_func(data,len(data),self.pystages,self.acc_input,self.acc_output,self.buffer1,self.buffer2,self.FIRCOEFFS,self.IIRCOEFFS)
        return data