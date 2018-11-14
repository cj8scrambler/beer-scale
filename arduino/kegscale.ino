#include <Arduino.h>
#include <Q2HX711.h>
#include <RunningMedian.h>
#include <EEPROM.h>
#include <SPI.h>
#include <LowPower.h>
#include <limits.h>

#include "Adafruit_BLE.h"
#include "Adafruit_BluefruitLE_SPI.h"

#define DEBUG                          1    // Enable verbose serial logging

#define MAX_SCALES                     2    // Number of HX711 scale devices connected
#define NUM_SAMPLES                    5    // Number of samples to read before taking median
#define TARE_SAMPLES                   12   // Minimum number of samples taken durring tare operation

#define MAX_SCALE_NAME_LEN             10
#define VALID_CONFIG                   0xFEED
#define ALLOWED_VARIANCE               350  // variance which triggers an MQTT report
#define WEIGHT_CHANGE_REPORTS          8    // consectutive samples before going back to slow rate
#define MAX_SAMPLES_SKIPPED            80   // Max samples before MQTT report is forced

// BT SPI SETTINGS
#define VERBOSE_MODE                   false  // If set to 'true' enables debug output
#define BLUEFRUIT_SPI_CS               8
#define BLUEFRUIT_SPI_IRQ              7
#define BLUEFRUIT_SPI_RST              4

typedef struct config {
  uint16_t valid;
  int32_t offset;
  float slope;
  char name[MAX_SCALE_NAME_LEN];
} scaleConfig;

struct config configs[MAX_SCALES];    /* Scale settings saved/retrieved from EEPROM */

RunningMedian samples[MAX_SCALES] = RunningMedian(NUM_SAMPLES);
int32_t last_reported[MAX_SCALES] = {0};

Q2HX711 scales[MAX_SCALES] = {
  Q2HX711(13, 12),
  Q2HX711(11, 10),
//  Q2HX711(9, 6),
//  Q2HX711(A1, A0)  // GPIO 19/18
};

int32_t scaleCharacteristics[MAX_SCALES];  /* BLE weight characteristics */

/* Notes
 *  AT+NVMWRITE/AT+NVMREAD   256 byte Non-voltatile storage; don't know how safe it is
 *  AT+HWMODELED=DISABLE     Save some power
 *  AT+BLEPOWERLEVEL=[-40, -20, -16, -12, -8, -4, 0, 4] Save power
 */
 
/* ...hardware SPI, using SCK/MOSI/MISO hardware SPI pins and then user selected CS/IRQ/RST */
Adafruit_BluefruitLE_SPI ble(BLUEFRUIT_SPI_CS, BLUEFRUIT_SPI_IRQ, BLUEFRUIT_SPI_RST);

// A small helper
void error(const __FlashStringHelper*err) {
  Serial.println(err);
  while (1);
}

int32_t tareCharId;
unsigned int updates = 0;
enum period_t sleep_period;
boolean weight_change = true;
boolean idle_update = false;
bool connected_state = false;

void setup(void)
{
  int32_t scaleServiceId;
  int32_t scaleFeatureCharId;
  int i;
  
  delay(2000);

  boolean success;

  Serial.begin(115200);
  Serial.println(F("Keg Scale"));
  Serial.println(F("---------"));

  randomSeed(micros());
  /* Read in scale configurations */
  EEPROM.get(0, configs);
  for (i = 0; i < MAX_SCALES; i++)
  {
    if (configs[i].valid == VALID_CONFIG)
    {
      Serial.println("");
      Serial.print(millis());
      Serial.print(F(" Scale #"));
      Serial.print(i);
      Serial.print(F(": "));
      Serial.println(configs[i].name);
      Serial.println(F("--------------------"));
      Serial.print(F("  Slope: "));
      Serial.println(configs[i].slope);
      Serial.print(F("  Offset: "));
      Serial.print(configs[i].offset);
      Serial.print(F("  Valid: 0x"));
      Serial.println(configs[i].valid,HEX);
    }
  }

  /* Initialize the BT module */
  Serial.print(F("Initializing BLE module: "));
  if ( !ble.begin(VERBOSE_MODE) )
  {
    error(F("Error: couldn't find Bluefruit."));
  }
  Serial.println( F("OK!") );

  /* Perform a factory reset to make sure everything is in a known state */
  Serial.print(F("BLE factory reset: "));
  if (! ble.factoryReset() ){
       error(F("Couldn't factory reset"));
  }
  Serial.println( F("OK!") );

  /* Disable command echo from Bluefruit */
  ble.echo(false);

  /* Change the device name to make it easier to find */
  Serial.println(F("Setting device name to 'kegscale'"));
  if (! ble.sendCommandCheckOK(F("AT+GAPDEVNAME=kegscale")) ) {
    error(F("Could not set device name?"));
  }

  /* Add the WeightScale Service definition */
  /* Service ID should be 1 */
  Serial.println(F("Adding the Weight Scale Service definition #1 (UUID = 0x181D): "));
  success = ble.sendCommandWithIntReply( F("AT+GATTADDSERVICE=UUID=0x181D"), &scaleServiceId);
  if (! success) {
    error(F("Could not add Weight service"));
  }

  /* Add the Weight Scale Feature characteristics */
  /* Chars ID for Weight Scale Feature should be 1 */
  // Serial.println(F("Adding the Weight Scale Feature characteristic #1 (UUID = 0x2A9E): "));
  /* 
   * PROPERTIES 0x02: Read-only
   * VALUE 0x38: disable: timestamp, multiple user, BMI, height; resolution = 0.005 kg
   */
  success = ble.sendCommandWithIntReply( F("AT+GATTADDCHAR=UUID=0x2A9E, PROPERTIES=0x02, MIN_LEN=4, MAX_LEN=4, VALUE=38-00-00-00"), &scaleFeatureCharId);
    if (! success) {
    error(F("Could not add Scale Feature characteristic"));
  }

  for (i = 0; i < MAX_SCALES; i++)
  {
      /* Add the Weight Measurement characteristic */
      //Serial.println(F("Adding a Weight Measurement characteristic (UUID = 0x2A9D): "));
      /* 
       * PROPERTIES 0x20: Indicate
       * VALUE 0: 0x00: SI units; Disable timestamp, userID, BMI & height
       * VALUE 1-2: weight in kg / 0.005 resolution
       * 
       */
      success = ble.sendCommandWithIntReply( F("AT+GATTADDCHAR=UUID=0x2A9D, PROPERTIES=0x20, MIN_LEN=3, MAX_LEN=3, VALUE=00-14-74"), &(scaleCharacteristics[i]));
      if (! success) {
        error(F("Could not add Weight Measurement characteristic"));
      }
  }
  
  /* Add the custom Tare characteristic */
  /* Chars ID for Measurement should be 3 */
  Serial.println(F("Adding the Tare characteristic: (custom UUID-128)"));
  /* 
   * PROPERTIES 0x0A: Read/Write
   * VALUE 0: 0x00: not tared;  0x01: tared
   * 
   */
  success = ble.sendCommandWithIntReply( F("AT+GATTADDCHAR=UUID128=D8-D4-2A-BE-D2-F3-4A-E7-B1-69-21-E5-56-3F-1C-7B, PROPERTIES=0x0A, MIN_LEN=2, MAX_LEN=2, VALUE=0x00"), &tareCharId);
    if (! success) {
    error(F("Could not add Tare characteristic"));
  }
  
  /* Reset the device for the new service setting changes to take effect */
  //Serial.print(F("Performing a SW reset (service changes require a reset): "));
  ble.reset();

  //Serial.println();
}

void loop(void)
{
  int i, scale;
  int32_t new_connected;
  float kg;
  int32_t grams, median;
  int weight;
  char buffer[16];
  int32_t tare_cmd;

#ifdef DEBUG
  /* Check for connection status */
  ble.sendCommandWithIntReply(F("AT+GAPGETCONN"), &new_connected);
  if (new_connected != connected_state)
  {
    connected_state = new_connected;
    if (connected_state)
    {
      Serial.println(F("CONNECTED"));
    }
    else
    {
      Serial.println(F("DISCONNECTED"));
    }
  }
#endif
    
  /* Check for an incoming command */
  sprintf(buffer, "AT+GATTCHAR=%d", tareCharId);
  ble.atcommandIntReply(buffer, &tare_cmd);
  if (tare_cmd != 0)
  {
    uint16_t scale = ((tare_cmd & 0xFFFF0000) >> 16);
    uint16_t tare_weight = (tare_cmd & 0xFFFF);

    /* scale is specified as 1 based, but we use 0 based here */
    scale = scale - 1;
    /* tare_weight is weight in grams */

    if (scale < MAX_SCALES)
    {
      if (tare_weight == 0)
      {
        Serial.print(F("Disable scale # "));
        Serial.println(scale + 1);
        configs[scale].valid = 0;
      }
      else
      {
        Serial.print(F("Got tare request on scale # "));
        Serial.print(scale + 1);
        Serial.print(F(" at "));
        Serial.print(tare_weight / 1000.0);
        Serial.println(F("kg"));
        tareScale(scale, tare_weight);
      }
      EEPROM.put(0, configs);
    }

    /* clear Tare request */
    ble.print( F("AT+GATTCHAR=") );
    ble.print( tareCharId );
    ble.print( F(",") );
    ble.println(0);

  }
  else
  {
    if (++updates >= MAX_SAMPLES_SKIPPED)
    {
      updates = 0;
      idle_update = true;
#ifdef DEBUG
      Serial.print(millis());
      Serial.print(F(" Scale # "));
      Serial.print(scale + 1);
      Serial.println(F(" Idle too long generate 1 report"));
#endif
    }
    
    for (scale = 0; scale < MAX_SCALES; scale++)
    {
      if (configs[scale].valid == VALID_CONFIG)
      {
        int32_t datapoint = scales[scale].read();
        samples[scale].add(datapoint);
        median = samples[scale].getMedian();
#ifdef DEBUG
        Serial.print(millis());
        Serial.print(F(" Scale #"));
        Serial.print(scale + 1);
        Serial.print(F(" Reading #"));
        Serial.print(updates);
        Serial.print(F(": "));
        Serial.print(datapoint);
        Serial.print(F(" Median: "));
        Serial.print(median);
        Serial.print(F(" LastReported: "));
        Serial.print(last_reported[scale]);
        Serial.print(F(" delta: "));
        Serial.print(abs(median - last_reported[scale]));
        Serial.print(F("/"));
        Serial.println(ALLOWED_VARIANCE);
#endif
        if (abs(median - last_reported[scale]) > ALLOWED_VARIANCE)
        {
#ifdef DEBUG
          Serial.print(millis());
          Serial.print(F(" Scale #"));
          Serial.print(scale + 1);
          Serial.println(F(" Weight changed state"));
#endif
          updates = 0;
          weight_change = true;
          sleep_period = SLEEP_4S;
        }
        
        if (weight_change || idle_update)
        {
          last_reported[scale] = median;
          grams = (median - configs[scale].offset) / (float)configs[scale].slope;
          weight = grams / 5.0;

          Serial.print(millis());
          Serial.print(F(" Reporting: Scale #"));
          Serial.print(scale + 1);
          Serial.print(F(" median: "));
          Serial.print(median);
          Serial.print(F(" grams: "));
          Serial.print(grams);
          Serial.print(F(" kg: "));
          Serial.print(grams / 1000.0);
          Serial.print(F(" weight counts: "));
          Serial.println(weight);

          /* Command is sent when \n (\r) or println is called */
          /* AT+GATTCHAR=CharacteristicID,value */
          ble.print( F("AT+GATTCHAR=") );
          ble.print( scaleCharacteristics[scale] );
          ble.print( F(",00-") );
          sprintf(buffer, "%02x", weight & 0xff);
          ble.print(buffer);
          ble.print( F("-") );
          sprintf(buffer, "%02x", weight >> 8);
          ble.println(buffer);

          /* Check if command executed OK */
          if ( !ble.waitForOK() )
          {
            Serial.println(F("Failed to get response!"));
          }
          delay(2000); /* seems to need a delay between reports */
        }
#ifdef DEBUG
        else
        {
          Serial.print(millis());
          Serial.print(F("Scale #"));
          Serial.print(scale +1);
          Serial.print(F(" abs("));
          Serial.print(median);
          Serial.print(F(" - "));
          Serial.print(last_reported[scale]);
          Serial.print(F(") !> "));
          Serial.println(ALLOWED_VARIANCE);
        }
#endif
      }
    }
    idle_update = false;
    if (updates >= WEIGHT_CHANGE_REPORTS)
    {
#ifdef DEBUG
      Serial.println(F(" Idle state"));
#endif
      weight_change = false;
      sleep_period = SLEEP_4S;
    }
    Serial.println(F("."));
  }

#ifdef DEBUG
  delay(200); /* needed to get serial prints complete before going to sleep */
#endif
  LowPower.idle(sleep_period, ADC_OFF, TIMER4_OFF, TIMER3_OFF, TIMER1_OFF, 
                TIMER0_OFF, SPI_OFF, USART1_OFF, TWI_OFF, USB_OFF);
}

void tareScale(int scale, int reference)
{
  int i;
  RunningMedian tare_samples = RunningMedian(TARE_SAMPLES);
  int32_t before, after;

  Serial.print(F("Tare Scale #"));
  Serial.print(scale + 1);

  /******** Get an empty baseline *************/
  for (i = 0; i < 4*TARE_SAMPLES; i++ )
  {
      tare_samples.add(scales[scale].read());
      delay(400);
      Serial.print(F("."));
  }
  before = tare_samples.getMedian();
  Serial.println(F(""));
  Serial.print(F("  Before: "));
  Serial.println(before);
  

  /******** Get a reference reading *************/
  Serial.print(F("  Add "));
  Serial.print(reference);
  Serial.println(F(" gram weight now."));
  delay(5000);
  Serial.print(F(" Reading"));
  for (i = 0; i < 4*TARE_SAMPLES; i++ )
  {
      tare_samples.add(scales[scale].read());
      delay(400);
      Serial.print(F("."));
  }
  after = tare_samples.getMedian();
  Serial.println(F(""));
  Serial.print(F("  After: "));
  Serial.println(after);

  /******** Save calculated config ************/
  configs[scale].slope = (after - before) / (float) reference;
  configs[scale].offset = before;
  configs[scale].valid = VALID_CONFIG;

  Serial.print(F("  Slope: "));
  Serial.println(configs[scale].slope);
  Serial.print(F("  Offset: "));
  Serial.println(configs[scale].offset);
  
  snprintf(configs[scale].name, MAX_SCALE_NAME_LEN, "Scale#%d", scale+1);
}
