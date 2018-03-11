var AWS = require('aws-sdk');
var iot = new AWS.Iot();

// Could figure this out programaticly, but that takes time.
// Comes from 'aws iot describe-endpoint'
var ENDPOINT = "a3f9rjliro4kji.iot.us-west-2.amazonaws.com"

exports.handler = (event, context, callback) => {
  console.log('DZ: Received event:', event);
  var simpledb = new AWS.SimpleDB();
  var params = {
    Items: []
  };

  var group;
  var thing;
  var taps = [];
  var jobs = [];
  for (var scale in event){
    group = event[scale].group;
    thing = event[scale].thing;
    console.log('DZ: working on  entry:', event[scale]);
    taps.push({"name":  scale, "weight": event[scale].weight, "timestamp": event[scale].timestamp});
    params.Items.push(
     { Attributes: [
        {
          Name: 'timestamp',
          Value: event[scale].timestamp.toString(),
        },
        {
          Name: 'name',
          Value: scale,
        },
        {
          Name: 'weight',
          Value: event[scale].weight.toString(),
        },
      ],
      Name: scale + ":" + event[scale].timestamp.toString(),
     });
  }
  params.DomainName = group;
  
  console.log('DZ: pushing simpledb update job');
  jobs.push(simpledb.batchPutAttributes(params, function(err, data) {
    // For some reason, we hit this twice sometimes
    console.log('DZ:   simbledb callback');
    if (err) {
      console.log("DB Update Error: " + JSON.stringify(err));
    }
    else {
      console.log(thing.toString() + " DB update success: " + JSON.stringify(params));
    }
  }).promise());
  
  var update = {
    state: {
      reported: {
        taps
      }
    }
  };
  console.log('DZ; pushing shadow update job');
  var iotdata = new AWS.IotData({endpoint: ENDPOINT});
  jobs.push(iotdata.updateThingShadow(
    {
      payload: JSON.stringify(update),
      thingName: thing.toString()
    }, function(err, data) {
      console.log('DZ;   shadow update callback');
      if (err) {
        console.log("Shadow Update failure:", err);
      } else {
        console.log(thing.toString() + " shadow update success:" + JSON.stringify(data));
      }
    }).promise());

  Promise.all(jobs).then(function() {
      console.log("All jobs done");
      context.succeed('data update success');
    }, function(err) {
      console.log("Problem somewhere: ", arguments);
      context.fail(err);
    });
};
