import logging
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)
iot = boto3.client('iot')
sdb = boto3.client('sdb')

def lambda_handler(event, context):
    result = {}
    result['results'] = []

    logger.debug('got event{}'.format(event))

    # Get group parameter from path input
    if 'group' in event['pathParameters']:
        group = event['pathParameters']['group']
    else:
        raise Exception('group not defined')

    logger.debug('got group: %s' % group)

    # Loop over things in group
    grouplist = iot.list_things_in_thing_group(
        thingGroupName=group, recursive=True,)
    for thing in grouplist['things']:
        logger.debug("Working on thing: %s" % thing)
        iotdata = boto3.client('iot-data')
        thingdata = iotdata.get_thing_shadow(thingName=thing)
        body = thingdata["payload"]
        thingState = json.loads(body.read())
        # If there is data, then loop over taps in thing
        if 'reported' in thingState['state']:
            for tapdata in thingState['state']['reported']['taps']:
                data = {}
                tapname = tapdata['tap']
                logger.debug("got tapdata: %s" % tapdata)
                logger.info("Updating tap: %s" % tapname)
                data['tap'] = tapname
                data['weight'] = tapdata['weight']
                data['timestamp'] = tapdata['timestamp']
                sdbData = sdb.get_attributes(DomainName = group + ".config",
                                             ItemName = tapname,
                                             ConsistentRead = True);
                if 'Attributes' in sdbData:
                    for element in sdbData['Attributes']:
                        if element['Value']:
                            logger.debug("data[%s] = %s" % (element['Name'], element['Value']))
                            data[element['Name']] = element['Value']

                result['results'].append(data)
    response = {}
    response["statusCode"] = 200
    response["headers"] = {}
    response["headers"]["Access-Control-Allow-Origin"] = "http://beer-status.s3-website-us-west-2.amazonaws.com"
    response["body"] = json.dumps(result)
    response["isBase64Encoded"] = False

    return (response)
