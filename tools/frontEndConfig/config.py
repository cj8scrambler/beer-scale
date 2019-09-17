import sys
import logging
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity

# Script to configure the scale configuration database from the command
# line.  Used to set details about a given tap associated with a scale.

# !!!! UPDATE STORAGE_ACCT_NAME and STORAGE_ACCT_KEY VALUE!!!!
#
# These values are needed to authenticate with the azure storage table
#
# Storage Account Name is the name of the storage account provisioned on Azure.
# Storage acct key can be found at:  Storage Account -> Access Keys -> key1 -> Key
#
# Or they can be manually fetched with (update your group name):
#   GROUP_NAME={YourAzureGroupName}
#   STORAGE_ACCT_NAME=$(az storage account list -g ${GROUP_NAME} --output json --query "[0].name" 2>/dev/null | tr -d '"')
#   STORAGE_ACCT_KEY=$(az storage account keys list -g ${GROUP_NAME} --account-name ${STORAGE_ACCT_NAME} --output json --query "[0].value" | tr -d '"')
#   echo "STORAGE_ACCT_NAME = ${STORAGE_ACCT_NAME}"
#   echo "STORAGE_ACCT_KEY =  ${STORAGE_ACCT_KEY}"
STORAGE_ACCT_NAME = "updateWithStorageAcctName"
STORAGE_ACCT_KEY = "somekindofsecretkeygetsfilledinhere+besuretogetyourdatafrombackendconfigfyiRHStbzOyxYA=="

# Other constants use default values from provision.sh script
TABLE_NAME_HISTORICAL_DATA = 'ScaleDataTable'
TABLE_NAME_CONFIGURATION = 'ScaleConfigTable'

# Lookup data on table columns
table_data = {
    'PartitionKey': {'description': 'Node', 'type': 'hide'},
    'RowKey': {'description': 'Scale Number', 'type': 'hide'},
    'weight': {'description': 'Last Weight', 'type': 'hide'},
    'etag': {'description': '', 'type': 'drop'},
    'tapname': {'description': 'Tap Name', 'type': 'string'},
    'beername': {'description': 'Beer Name', 'type': 'string'},
    'brewer': {'description': 'Brewer Name', 'type': 'string'},
    'location': {'description': 'Brewery Location', 'type': 'string'},
    'style': {'description': 'Beer Style', 'type': 'string'},
    'abv': {'description': 'Beer ABV', 'type': 'double'},
    'color': {'description': 'Beer Color', 'type': 'string'},
    'ibu': {'description': 'Beer IBU', 'type': 'int'},
    'tarefull': {'description': 'Tare Wieght Full', 'type': 'int'},
    'tareempty': {'description': 'Tare Wieght Empty', 'type': 'int'},
}

def configure_front_end():
    try:
        table_service = TableService(account_name=STORAGE_ACCT_NAME, account_key=STORAGE_ACCT_KEY)
    except:
        print("Error: Could not connect to table service.  Check STORAGE_ACCT_NAME and STORAGE_ACCT_KEY");
        return

    if (not table_service.exists(TABLE_NAME_CONFIGURATION)):
        print("Error: Could not find configuration table: %s" % (TABLE_NAME_CONFIGURATION))
        return

    taps = table_service.query_entities(TABLE_NAME_CONFIGURATION)
    for tap in taps:
        print("")
        print("%s scale-%s" % (tap['PartitionKey'], tap['RowKey']))
        print("---------------------------------")
        for key in tap:
            if key in table_data and table_data[key]['type'] != 'drop' and table_data[key]['type'] != 'hide':
                if key in tap:
                    print("  %s: %s" % (table_data[key]['description'], tap[key]))
                else:
                    print("  %s:" % (table_data[key]['description']))

        answer = input("Update tap info [y/N]? ")
        if not answer:
            answer = 'N'
        if answer.lower() == "y" or answer.lower == "yes":
            newdata = Entity();
            for key in table_data:
                prompt = True;
                if table_data[key]['type'] != 'drop':
                    update = None
                    if table_data[key]['type'] == 'hide':
                        update = tap[key]
                        prompt = False
                    else:
                        if key in tap:
                            existing = tap[key]
                        else:
                            existing = '';

                    if prompt:
                        update = input("  %s: [%s]: " % (table_data[key]['description'], existing))
                        if (not update):
                            update = existing

                    if table_data[key]['type'] == 'hide':
                        newdata[key] = update
                    elif table_data[key]['type'] == 'int':
                        newdata[key] = int(update)
                    elif table_data[key]['type'] == 'double':
                        newdata[key] = float(update)
                    elif table_data[key]['type'] == 'string':
                        newdata[key] = str(update)
                    else:
                        print("Error: uknown data type: %s" % table_data[key]['type'])

            print("Updated record: ")
            print(newdata);
            table_service.update_entity(TABLE_NAME_CONFIGURATION, newdata)

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.ERROR)
    configure_front_end()
