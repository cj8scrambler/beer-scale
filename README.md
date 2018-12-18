# Keg Scale
This is a project to monitor the amount of beer left in my keggerator by weighing them and providing a web interface to view the data.

### Architecture
![arch](docs/arch.png)

##### Scales
Custom scales were created which fit in the keggerator.  In my case they are 9" x 9.75".  The scales are made from a 1/2" thick sheet of HDPP plastic [cutting boards](https://www.amazon.com/gp/product/B01LXE0MBM/ref=oh_aui_search_detailpage?ie=UTF8&psc=1).  [50kg load cells](https://www.amazon.com/gp/product/B071ZYYJHJ/ref=oh_aui_search_detailpage?ie=UTF8&psc=1) are placed in each corner.  The load cells are held in place using a custom [3D printed clip](hw/).

##### Scale Wiring
Sparkfun has a great [tutorial](https://learn.sparkfun.com/tutorials/load-cell-amplifier-hx711-breakout-hookup-guide?_ga=2.146147319.292295071.1545164052-27740493.1545164052) on wiring and using load cells.  I used their [Load Cell Combinator](https://www.sparkfun.com/products/13878) and [HX711 board](https://www.sparkfun.com/products/13879?_ga=2.192286441.292295071.1545164052-27740493.1545164052) to wire up the scale. 

##### Reading Data
I spent a lot of time trying to get a Raspberry Pi to reliably read the data from the HX711, but it wouldn't work.  I tried multiple python drivers, user space C code and kernel drivers.  They all worked most of the time, but had intermittant problems which led to unreliable data.

I ended up using an [Adafruit Feature 32u4 Bluefruit LE](https://www.adafruit.com/product/2829) to read the HX711 data.  This was much more reliable and draws less power so it could run off a battery from inside the keggerator.  The Arduino implements a BLE Weight Scale allowing any BLE app to read the data.

##### Sending Data
The Arduino is great at reading the data, but it's not able to send the data directly to the cloud due to a lack of wifi and SSL capabilities.  So I have a Raspberry Pi running a python script to read the BLE data from any available Arduinos, then send the data up to the Amazon IOT interface.

##### Storing Data
All of the backend data is kept in Amazon cloud services.  Data comes in through the Amazon IOT interface.  From there a Lamda function is triggered which stores the data in a SimpleDB.

##### Accessing Data
An HTML/javascript frontend is stored in S3.  It uses the Amazon API to call a Lambda function which retrieves data from the SimpleDB for rendering.

### Organization
The scales are organized so they can scale for a single keggerator up to a large multi-keggerator setup.  Here is how they are mapped in each layer:

##### Scales -> HX711
Each scale needs to wire to a single HX711 IC to read the data.  The 4 sensors are wired in a Wheatsonte bridge configuration.  This can be done manually, or by using a Sparkfun [Load Combinator](https://www.sparkfun.com/products/13878) board.

##### HX711 -> Arduino
1-4 HX711 interfaces can be connected to a single Arduino.  All the scales should be inside the same keggerator to minimize noise on the lines.  Boards are connected as:

| Scale # | Clock | Data |
|:-------:|:-----:|:----:|
|    1    |   13  |  12  |
|    2    |   11  |  10  |
|    3    |   9   |   6  |
|    4    |   A1  |  A0  |

The arduino needs to have a unique BLE name configured in [kegscale.ino](raspberrypi/scaleconfig.json).

##### Arduino -> Raspberry Pi
There is no hard limit on the number of Arduinos that a Rasbperry Pi can read from.  The [scaleconfig.json](raspberrypi/scaleconfig.json) file configures the expected BLE name for each Arduino and the name of each scale (i.e. tap) connected to that Arduino.  Tap names should be unique across your *group*.

[scaleconfig.json](raspberrypi/scaleconfig.json) also configures the AWS *thingname*.  If you have multiple Raspberry Pis (i.e. one in the basement bar and one in the garage), each should have a unique *thingname*.

##### Raspberry Pi -> Cloud
The AWS IOT can have multiple *things* under one *group*.  If you have multiple Raspberry Pis reporting, they should all be in the same group.  If you only have a single Raspberry Pi, then you still need a group with 1 *thing*.  The *group* name is used for all web front end calls and represents all of the taps in your system regardless of which keggerators/arduinos/raspberries they are connected to.
