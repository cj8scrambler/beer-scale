var AWS = require('aws-sdk');
var iot = new AWS.Iot();

// Could figure this out programaticly, but that takes time.
// Comes from 'aws iot describe-endpoint'
var ENDPOINT = "a3f9rjliro4kji.iot.us-west-2.amazonaws.com"

exports.handler = (event, context, callback) => {
  var results = { 'results': [] };
  //console.log('DZ: Received event:', event);
  
  const group = event.pathParameters.group;
  if (group == undefined) {
    context.fail("Invalid path: missing group");
  }
  
  var params = {
    thingGroupName: group,
    maxResults: 32,
    recursive: true
  };
  
  iot.listThingsInThingGroup(params, function(err, groupData) {
    if (err) context.fail(err);
    else {
      //console.log('DZ: Received group list::', groupData);
      groupData.things.forEach(function(item, index, array) {
        console.log('DZ: on thing:', item)
        var iotdata = new AWS.IotData({endpoint: ENDPOINT})
        iotdata.getThingShadow({thingName: item}, function(err, shadowData) {
          var shadowPromise = new Promise(function(resolve, reject) {
            if (err) {
              reject(err);
            } else {
              console.log('DZ:', item, "has:", shadowData)
              var jsonPayload = JSON.parse(shadowData.payload);
              if (jsonPayload.state.reported != undefined) {
                for (var i in jsonPayload.state.reported.taps) {
                  console.log('DZ: thing:', item, '  tap:', i, ' weight:', jsonPayload.state.reported.taps[i]);
                  var entry = {};
                  entry['tap'] = jsonPayload.state.reported.taps[i].tap;
                  entry['timestamp'] = jsonPayload.state.reported.taps[i].timestamp;
                  entry['weight'] = jsonPayload.state.reported.taps[i].weight;
                  console.log("DZ: entry is:", entry)
                  results['results'].push(entry);
                }
                resolve("Stuff worked!");
              }
              reject(Error("No data found"));
            }
          });
          shadowPromise.then(function(result) {
            console.log("DZ; promise result handler");
            var response = {
              "statusCode": 200,
              "headers": {
                "Access-Control-Allow-Origin": "http://beer-status.s3-website-us-west-2.amazonaws.com"
              },
              "body": JSON.stringify(results),
              "isBase64Encoded": false
            };
            context.succeed(response);
          }, function(err) {
            console.log("DZ; promise err handler");
          });
        });
      });
    }
  });
};
