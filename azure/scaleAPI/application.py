import os
import logging
import json
import time
import types

from applicationinsights.logging import LoggingHandler
from applicationinsights import TelemetryClient

from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity

from flask import Flask
from flask import request
app = Flask(__name__)

TABLE_NAME_HISTORICAL_DATA = os.environ['HistoricalDataTableName']
TABLE_NAME_CONFIGURATION = os.environ['ConfigurationTableName']

@app.route("/")
def listTaps():
    # Trying to use AppInsights, but this doesn't seem to work (disabling so app.logger works)
    #if 'APPINSIGHTS_INSTRUMENTATIONKEY' in os.environ:
    #    handler = LoggingHandler(os.environ['APPINSIGHTS_INSTRUMENTATIONKEY'])
    #    logging.basicConfig(handlers=[ handler ], format='%(levelname)s: %(message)s', level=logging.DEBUG)

    #    tc = TelemetryClient(os.environ['APPINSIGHTS_INSTRUMENTATIONKEY'])
    #    tc.track_event("GET /")
    #    tc.flush()

    table_service = TableService(connection_string=os.environ['AzureTableConnectionString'])
    taps = table_service.query_entities(TABLE_NAME_CONFIGURATION)
    e = Entity;

    results = []
    for tap in taps:
        app.logger.debug("working on (type %s) %s" % (type(tap), tap))
        # Convert PartitionKey->deviceid and RowKey->scale, drop 'etag' and copy the rest
        tapdata = {}
        tapdata['deviceid'] = tap.pop('PartitionKey')
        tapdata['scale'] = int(tap.pop('RowKey'))
        tap.pop('etag')
        tapdata.update(tap.items())
        app.logger.debug("appending %s" % tapdata)
        results.append(tapdata)

    app.logger.debug("Returning: " % (results))
    return json.dumps(results, default=str)

#/history/<deviceid>/<scale>?seconds=<int>
@app.route("/history/<deviceid>/<scale>")
def historyDevScale(deviceid, scale):
    # Trying to use AppInsights, but this doesn't seem to work (disabling so app.logger works)
    #if 'APPINSIGHTS_INSTRUMENTATIONKEY' in os.environ:
    #    handler = LoggingHandler(os.environ['APPINSIGHTS_INSTRUMENTATIONKEY'])
    #    logging.basicConfig(handlers=[ handler ], format='%(levelname)s: %(message)s', level=logging.DEBUG)

    #    tc = TelemetryClient(os.environ['APPINSIGHTS_INSTRUMENTATIONKEY'])
    #    tc.track_event("GET /history/%s/%d/%d" % (deviceid, scale, seconds))
    #    tc.flush()

    seconds = request.args.get('seconds', default = 3600, type = int)
    timefrom = int(time.time()) - seconds;
    query="timestamp gt %d" % (timefrom)
    app.logger.debug("getting records after %d with query: %s\n" % (timefrom, query));

    table_service = TableService(connection_string=os.environ['AzureTableConnectionString'])
    datapoints = table_service.query_entities(TABLE_NAME_HISTORICAL_DATA, filter=query)

    results = []
    for datapoint in datapoints:
        # Map PartitionKey->deviceid, drop RowKey, Timestamp & etag
        datapoint['deviceid'] = datapoint.pop('PartitionKey')
        datapoint.pop('RowKey')
        datapoint.pop('Timestamp')
        datapoint.pop('etag')
        results.append(datapoint)

    app.logger.debug("Returning %d elemnts: %s" % (len(results), results))
    return json.dumps(results, default=str)
