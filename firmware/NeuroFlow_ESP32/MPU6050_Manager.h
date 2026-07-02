#ifndef MPU6050_MANAGER_H
#define MPU6050_MANAGER_H

#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include "SystemConfig.h"
#include "SignalFilter.h"

enum ActivityLevel { ACTIVITY_DIAM, ACTIVITY_JALAN, ACTIVITY_LARI };

class MPU6050_Manager {
private:
    Adafruit_MPU6050 mpu;
    MovingAverageFilter magBuffer;
    float baseGravityMag;
    ActivityLevel currentActivity;
    
public:
    MPU6050_Manager();
    
    bool begin(TwoWire* wire);
    void calibrate();
    void prepareForDeepSleep();
    
    float getAccelMagnitude();
    void update(float magnitude);
    
    float getTremorIntensity() const;
    ActivityLevel getActivityLevel() const;
    const char* getActivityLabel() const;
};

#endif // MPU6050_MANAGER_H
