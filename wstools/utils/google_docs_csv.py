#! /usr/bin/env python3

import apiclient.discovery
import httplib2
import oauth2client.file
import oauth2client.tools
import re
import requests
import urllib.parse

SCOPES = 'https://www.googleapis.com/auth/drive.readonly'
SPREADSHEET_ID = '1tUdGJIOcIY_QsgaKW1pwLhSABvAPh1Il'

store = oauth2client.file.Storage('credentials.json')
creds = store.get()
if not creds or creds.invalid:
    flow = oauth2client.client.flow_from_clientsecrets(
        'client_secret.json', SCOPES)
    creds = oauth2client.tools.run_flow(flow, store)

service = apiclient.discovery.build(
    'sheets', 'v4', http=creds.authorize(httplib2.Http()))

result = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
urlParts = urllib.parse.urlparse(result['spreadsheetUrl'])
path = re.sub("/edit$", '/export', urlParts.path)
urlParts = urlParts._replace(path=path)
headers = {
    'Authorization': 'Bearer ' + creds.access_token,
}
for sheet in result['sheets']:
    params = {
        'id': SPREADSHEET_ID,
        'format': 'csv',
        'gid': sheet['properties']['sheetId'],
    }
    queryParams = urllib.parse.urlencode(params)
    urlParts = urlParts._replace(query=queryParams)
    url = urllib.parse.urlunparse(urlParts)
    response = requests.get(url, headers=headers)
    filePath = '/tmp/foo-%s.csv' % (+ params['gid'])
    with open(filePath, 'wb') as csvFile:
        csvFile.write(response.content)
