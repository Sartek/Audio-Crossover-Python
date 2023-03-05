gcc -c -Wall -Werror -fpic filters.cpp
gcc -shared -o filters.dll filters.o
gcc -L./ -Wall -o test main.cpp -lfilters -lstdc++