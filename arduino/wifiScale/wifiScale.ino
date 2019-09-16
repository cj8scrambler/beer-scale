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
#include <Wire.h>

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
  uint32_t start = millis();
  bool run_scale_cal = false;

  // Start serial and initialize stdout
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  Serial.println("");
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH); /* turn off LED */

  pinMode(CONFIG_SW_GPIO, INPUT_PULLUP);
  pinMode(AVDD_EN_GPIO, OUTPUT);
  digitalWrite(AVDD_EN_GPIO, HIGH);

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

#ifdef DEBUG
  Serial.printf("%ld - Begin readings\r\n", start);
#endif

  // Read battery voltage
  // 10-bit ADC with 1:10 voltage divider scaled up to mv: /1024 * 10 * 1000
  mv = (uint16_t)((analogRead(A0) * 9.7656) + 0.5);

  run_scale_cal = initConfig();

  if (!digitalRead(CONFIG_SW_GPIO)) {
    Serial.println("Force reconfig due to config switch");
    run_scale_cal |= reconfig();
  }

  /* we're done checking for config mode; disable the pullup to save power */
  pinMode(CONFIG_SW_GPIO, INPUT);

  /* If scale calibration is needed, do that then sleep to reset setup sequence */
  if (run_scale_cal)
  {
    for(int adc_offset = 0; adc_offset < NUM_ADC; adc_offset++)
    {
      setmux(adc_offset);
      for(int chan = 0; chan < NUM_CHAN_PER_ADC; chan++)
      {
        int scalenum = adc_offset * NUM_CHAN_PER_ADC + chan;
        if (g_config->scaledata[scalenum].slope == 0.0)
        {
          scale[scalenum] = new Scale(&(adc[adc_offset]), chan, scalenum);
          scale[scalenum]->begin(&g_config->scaledata[scalenum]);
          scale[scalenum]->calibrate(g_config->refweight);
        }
      }
    }

    /* save new settings to EEPROM */
    saveSettings();

    setmux(-1);

    Serial.println("Scale calibrations complete.  Reseting....");
    /* This will never return; actually goes back to begining of setup() */
    ESP.deepSleep(1000);
  }

  /* Provision scale devices for real
   * Loop order (chan then ADC) is important to minimize recalibrations delays
   */
  for(int chan = 0; chan < NUM_CHAN_PER_ADC; chan++)
  {
    /* Provision, initialize and begin calibration on each */
    for(int adc_offset = 0; adc_offset < NUM_ADC; adc_offset++)
    {
      int scalenum = adc_offset * NUM_CHAN_PER_ADC + chan;
      setmux(adc_offset);
      scale[scalenum] = new Scale(&(adc[adc_offset]), chan, scalenum);
      scale[scalenum]->begin(&g_config->scaledata[scalenum]);
    }

    /* Check network while ADC calibration is happening */
    if (!network.isConnected())
    {
      if (!network.connectWifi(g_config->ssid, g_config->pass) ||
          !iothub.init(g_config->connection, g_config->deviceid))
      {
        /* If we can't connect then go to sleep
         * and hope things get better later */
        goto done;
      }
    }

    /* Get the datapoint from each ADC when it's ready */
    for(int adc_offset = 0; adc_offset < NUM_ADC; adc_offset++)
    {
      int scalenum = adc_offset * NUM_CHAN_PER_ADC + chan;
      if (scale[scalenum]->enabled())
      {
        setmux(adc_offset);
        if (scale[scalenum]->waitForReady(1000))
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

          Serial.printf("%ld - %ld: reported scale-%d: %.1f Kg %s\r\n",
                        millis(),
                        (time_t) root["timestamp"], scalenum,
                        ((float)root["weight"]) / 1000.0,
                        scale[scalenum]->recentWeightChange()?
                        "(change)":"");
          weight_change |= scale[scalenum]->recentWeightChange();
        }
        else
        {
          Serial.printf("%ld Error waiting for scale-%d to become ready\r\n", millis(), scalenum);
        }
      }
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
    if (adc[adc_offset].isConnected())
      adc[adc_offset].powerDown();
  }
#endif
  digitalWrite(AVDD_EN_GPIO, LOW);

  /* saves config/state info to EEPROM */
  saveSettings();

  Serial.printf("%ld - Waiting on iothub to finish\r\n", millis());
  while (network.isConnected() && iothub.workPending()) {
    iothub.doWork();
    delay(10);
  }
  Serial.println();

  /* deepsleep will cause board to reset to setup() on wakeup */
  int sleeptime = weight_change ? SHORT_SLEEP_TIME_S : LONG_SLEEP_TIME_S;
  Serial.printf("Uptime %0.2fS; Sleeping for %d seconds\r\n", (millis() - start) / 1000.0, sleeptime);

  digitalWrite(LED_BUILTIN, HIGH);
  ESP.deepSleep(sleeptime * 1000000);
}

void loop() {
}
