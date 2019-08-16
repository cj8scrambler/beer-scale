/*
   Arduino based scale application using multiple NAU7802 ADCs
   connected with an I2C Mux.  Data is sent via wifi to an Azure
   backend.  Full details at:
     https://github.com/cj8scrambler/beer-scale

   Based on and including code from:

    Microsoft IOT arduino demo
    https://github.com/Azure/azure-iot-arduino

    Luis Llamas median filter
    https://github.com/luisllamasbinaburo/Arduino-MedianFilter

    NAU7802 Arduino Library
    https://github.com/Sawaiz/nau7802

*/
#include <ArduinoJson.h>

#include "common.h"
#include "scale.h"
#include "iothub.h"
#include "network.h"

//#define DEBUG                          1      // Enable verbose serial logging

NAU7802 adc[NUM_ADC];
Scale *scale[NUM_SCALES];                   // 2 scales per ADC
IotHub iothub;
Network network;

void setup() {
  int weight_change = false;
  int adc_offset, chan;
  uint16_t mv;
  char buffer[MESSAGE_MAX_LEN];

  // Start serial and initialize stdout
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  Serial.println("");

  pinMode(LED_BUILTIN, OUTPUT);
#ifdef DEBUG
  digitalWrite(LED_BUILTIN, LOW); /* turn LED on solid durring setup */
#endif
  pinMode(CONFIG_SW_GPIO, INPUT_PULLUP);
  pinMode(AVDD_EN_GPIO, OUTPUT);
  digitalWrite(AVDD_EN_GPIO, HIGH);

  initConfig();

  if (!digitalRead(CONFIG_SW_GPIO)) {
    Serial.println("Force reconfig due to config switch");
    reconfig();
  }

  /* we're done checking for config mode; disable the pullup to save power */
  pinMode(CONFIG_SW_GPIO, INPUT);

  /* Provision scale devices (may initiate calibration) */
  for(int adc_offset = 0; adc_offset < NUM_ADC; adc_offset++)
  {
    setmux(adc_offset);
    for(int chan = 0; chan < NUM_CHAN_PER_ADC; chan++)
    {
      int scalenum = adc_offset * NUM_CHAN_PER_ADC + chan;
      scale[scalenum] = new Scale(adc[adc_offset], chan, scalenum);

      scale[scalenum]->begin(&g_config->scaledata[scalenum]);

    }
  }
  setmux(-1);

  if (network.connectWifi(g_config->ssid, g_config->pass))
  {
    iothub.init(g_config->connection, g_config->deviceid);
  } else {
    /* If we couldn't connect to Wifi, go to sleep
     * and hope things get better later */
    goto done;
  }

  // 10-bit ADC with 1:10 voltage divider scaled up to mv: /1024 * 10 * 1000
  mv = (uint16_t)((analogRead(A0) * 9.7656) + 0.5);

  /* gather data */
  for (adc_offset = 0; adc_offset < NUM_ADC; adc_offset++)
  {
    setmux(adc_offset);
    for (chan = 0; chan < NUM_CHAN_PER_ADC; chan++)
    {
      int scalenum = adc_offset * NUM_CHAN_PER_ADC + chan;
      if (scale[scalenum]->enabled())
      {
        scale[scalenum]->datapoint();

        DynamicJsonDocument root(MESSAGE_MAX_LEN);
        root["timestamp"] = network.getTime();
        root["deviceid"] = g_config->deviceid;
        root["scale"] = scale[scalenum]->scaleNum();
        root["weight"] = scale[scalenum]->weight();
        root["voltage"] = mv;
#ifdef DEBUG
        Serial.println("Generated message:");
        serializeJsonPretty(root, Serial);
        Serial.println();
#endif
        serializeJson(root, buffer, MESSAGE_MAX_LEN);
        iothub.sendMessage(buffer);
#if 0  /* Log data as CSV */
        Serial.printf("DATA:,%ld,%d,%d,%d,%d\r\n", (time_t) root["timestamp"], scalenum, (int32_t)root["weight"], (bool)scale[scalenum]->recentWeightChange(), (uint16_t)root["voltage"]);
#endif
        Serial.printf("%ld - %ld: reported scale-%d: %.1f Kg %s\r\n",
                      millis(),
                      (time_t) root["timestamp"], scalenum,
                      ((float)root["weight"]) / 1000.0,
                      scale[scalenum]->recentWeightChange()?
                      "(change)":"");
        weight_change |= scale[scalenum]->recentWeightChange();
      }
#ifdef DEBUG
      else Serial.printf("  scale-%d Disabled\r\n", scalenum);
#endif
    }
  }

done:
  setmux(-1);

  if (network.isConnected())
  {
    iothub.doWork();
    delay(5);
  }

#ifndef SIMULATE
  for (adc_offset = 0; adc_offset < NUM_ADC; adc_offset++)
  {
    adc[adc_offset].lowPowerMode();
  }
#endif
  digitalWrite(AVDD_EN_GPIO, LOW);

  /* saves config/state info to EEPROM */
  saveSettings();

  Serial.printf("%ld - Waiting on iothub to finish\r\n", millis());
  /* wait for iot trasmits to finish */

  while (network.isConnected() && iothub.workPending()) {
    iothub.doWork();
    delay(10);
  }
  Serial.println();

  /* deepsleep will cause board to reset to setup() on wakeup */
  int sleeptime = weight_change ? SHORT_SLEEP_TIME_S : LONG_SLEEP_TIME_S;
  Serial.printf("%ld - Sleeping for %d seconds\r\n", millis(), sleeptime);

  digitalWrite(LED_BUILTIN, HIGH);
  ESP.deepSleep(sleeptime * 1000000);
}

void loop() {
}
