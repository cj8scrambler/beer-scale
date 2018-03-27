import logging
import boto3
import json
import time

SECS_PER_DAY = 86400

logger = logging.getLogger()
logger.setLevel(logging.INFO)
sdb = boto3.client('sdb')

def timestamp_days_ago(days):
    return (int(time.time() - SECS_PER_DAY * float(days)))

def lambda_handler(event, context):
    data = []
    days = 1;
    nexttoken = ""
    
    logger.debug('got event{}'.format(event))
    
    # Get group parameter from path input
    if 'group' in event['pathParameters']:
        group = event['pathParameters']['group']
    else:
        raise Exception('group not defined')
    logger.debug('got group: %s' % group)
    
    # Get tap parameter from path input
    if 'tap' in event['pathParameters']:
        tap = event['pathParameters']['tap']
    else:
        raise Exception('tap not defined')
    logger.debug('got group: %s' % group)

    # Get days parameter from query string
    if event['queryStringParameters'] is not None:
        if 'days' in event['queryStringParameters']:
            days = event['queryStringParameters']['days']

    query = "select timestamp,weight from '" + group + "' where 'timestamp' >= '"
    query = query + str(timestamp_days_ago(days)) + "' and name = '" + tap + "'" 
    
    logger.info('DZ: query:' + query)

    i = 0
    while True:
        sdbData = sdb.select(SelectExpression=query, NextToken=nexttoken, ConsistentRead=True)
        if 'Items' in sdbData:
            for element in sdbData['Items']:
                #logger.debug(element['Name'])
                point = {}
                for key in element['Attributes']:
                    point[key['Name']] = key['Value']
                    #logger.debug("  %s = %s" % (key['Name'], key['Value']))
                # Covert timestamp from seconds to miliseconds 
                data.append([1000*int(point['timestamp']), float(point['weight'])])
                i = i + 1
        if 'NextToken' in sdbData:
            nexttoken = sdbData['NextToken']
        else:
            break
        
    logger.info('got ' + str(i) + ' datapoints')
    
    response = {}
    response["statusCode"] = 200
    response["headers"] = {}
    response["headers"]["Access-Control-Allow-Origin"] = "http://beer-status.s3-website-us-west-2.amazonaws.com"
    response["body"] = json.dumps(data)
    response["isBase64Encoded"] = False

    return (response)

