double filter(double* data, int data_size, int stages, double* acc_input, double* acc_output, double* buffer1, double* buffer2, double* FIRCOEFFS, double* IIRCOEFFS)
{
    double input_c = 0;
    for (int i = 0; i < data_size; i++)
    {
        input_c = data[i];
        for (int ii = 0; ii < stages; ii++)
        {
            acc_input[ii] = (input_c + buffer1[ii] * -IIRCOEFFS[ii*2+0] + buffer2[ii] * -IIRCOEFFS[ii*2+1]);
            
            acc_output[ii] = (acc_input[ii] * FIRCOEFFS[ii*3+0] + buffer1[ii] * FIRCOEFFS[ii*3+1] + buffer2[ii] * FIRCOEFFS[ii*3+2]);
            
            buffer2[ii] = buffer1[ii];
            buffer1[ii] = acc_input[ii];
            
            input_c = acc_output[ii];
        }
        
        data[i] = input_c;
    }
    return 1;
}