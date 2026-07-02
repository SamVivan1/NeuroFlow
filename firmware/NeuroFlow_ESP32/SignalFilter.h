#ifndef SIGNAL_FILTER_H
#define SIGNAL_FILTER_H

#include <Arduino.h>

class MovingAverageFilter {
private:
    float* buffer;
    int size;
    int index;
    int count;
    float sum;

public:
    MovingAverageFilter(int windowSize);
    ~MovingAverageFilter();
    void reset();
    float process(float newValue);
    float getAverage() const;
    float getVariance() const;
    float getStandardDeviation() const;
    bool isFull() const;
};

// Basic Low Pass Filter (Alpha Filter)
class LowPassFilter {
private:
    float alpha;
    float lastOutput;
    bool initialized;

public:
    LowPassFilter(float alphaValue);
    void reset();
    float process(float newValue);
};

#endif // SIGNAL_FILTER_H
