var AWS = require('aws-sdk');
var iot = new AWS.Iot();

exports.handler = (event, context, callback) => {
//  console.log('DZ: Received event:', event);
  var simpledb = new AWS.SimpleDB();
  var params = {
    Items: []
  };

  var group;
  var thing;
  var taps = [];
  for (var scale in event){
    group = event[scale].group;
    thing = event[scale].thing;
//    console.log('DZ: updated entry:', event[scale]);
    taps.push({"name":  scale, "weight": event[scale].weight});
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
  
  //console.log('DZ: Writing record', JSON.stringify(params));
  
  simpledb.batchPutAttributes(params, function(err, data) {
    if (err) {
      console.log(err);
      context.fail("Internal Error: " + JSON.stringify(err)); // an error occurred
    }
    else {
//        console.log('DZ: Sent DB update', params);
      context.succeed('DB update success: ' + params);
    }
  });
  
  var update = {
    state: {
      reported: {
        taps
        }
    }
  };

  iot.describeEndpoint({}, function(err, endpointData) {
    if (err) console.log(err, err.stack);
    else {
      var iotdata = new AWS.IotData({endpoint: endpointData.endpointAddress});

      iotdata.updateThingShadow(
        {
          payload: JSON.stringify(update),
          thingName: thing.toString()
        }, function(err, data) {
          if (err) {
            context.fail(err);
          } else {
//            console.log(data);
            context.succeed('Shadow update success');
          }
      });
    }
  });
};
