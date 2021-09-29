#!/bin/bash

GROUP=debug_costs
LOC=northcentralus

set -e
set -x

# Hopefully creates unique names
RANDO=$(head /dev/urandom | LC_CTYPE=C tr -dc a-z0-9 | head -c 10 ; echo '')

az group create -l ${LOC} -g ${GROUP}
az eventhubs namespace create -l ${LOC} -g ${GROUP} --name Events-${RANDO} --sku Basic
az eventhubs eventhub create -g ${GROUP} --namespace-name Events-${RANDO} --name samples-workitems --message-retention 1
az storage account create -l ${LOC} -g ${GROUP} --name storage${RANDO} --sku Standard_LRS --kind StorageV2
az functionapp create --resource-group ${GROUP} --name funcApp-${RANDO} --storage-account storage${RANDO} --consumption-plan-location westus --os-type linux --runtime python 

# Create an empty app
func init --worker-runtime python funcAppCost
if [[ -d debugCost ]]
then
  cd debugCost
fi
func new --template "Azure Event Hub trigger" --name emptyFunc

# Connect app to event hub
EH_CONSTRING=$(az eventhubs namespace authorization-rule keys list -g ${GROUP} --namespace-name Events-${RANDO} --name RootManageSharedAccessKey --output json --query "primaryConnectionString" 2>/dev/null | tr -d '"')
az functionapp config appsettings set --resource-group ${GROUP} --name funcApp-${RANDO} --settings "EventHubConnectString=${EH_CONSTRING}"
sed -i 's/"connection": ""/"connection": "EventHubConnectString"/g' emptyFunc/function.json

# publish empty app
sleep 5
func azure functionapp publish funcApp-${RANDO} --build-native-deps --python 

date
echo "Wait about 5 mins, then check eventhub incoming request rate"
