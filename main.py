#!/usr/bin/env python

import os
import sys
import logging
import json
import requests
import datetime
import pyteamcity
import http.server

config={}

class TCWebHookHandler(http.server.BaseHTTPRequestHandler):
  def do_POST(s):
    contentLen = int(s.headers['Content-Length'])
    postBody=s.rfile.read(contentLen)
    postBody = postBody.decode("utf-8")
    postBody=json.loads(postBody)
    buildId=postBody['build']['buildId']
    result=processBuild(buildId)
    s.send_response(result['status_code'])
    s.end_headers()
    s.wfile.write(result['text'].encode("utf-8"))
    return

# TODO: move into initializer
logger = logging.getLogger('teamcity_connector')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

def dateTimeToTimestamp(s):
  s=datetime.datetime.strptime(s, "%Y%m%dT%H%M%S%z").timestamp()*1000
  s="%.0f" % s
  return s

def processBuild(buildId):
  tc = pyteamcity.TeamCity(config['TEAMCITY_USER'], config['TEAMCITY_PASSWORD'], config['TEAMCITY_HOST'])
  try:
    build = tc.get_build_by_build_id(buildId)
  except Exception as e:
    logger.error("can not get build: %s" % e)
  
  try:
    buildStatistic = tc.get_build_statistics_by_build_id(buildId)
  except Exception as e:
    logger.error("can not get build statistic: %s" % e)
  
  try:
    changes = tc.get_changes_by_build_id(buildId)
  except Exception:
    logger.info("changes are empty for build id: %s" % buildId)
    changesEmpty = True
  else:
    changesEmpty = False
  
  data={}
  
  data['buildStatus']=build['status']
  data['buildUrl']=build['webUrl']
  buildStatisticProperties = buildStatistic['property']
  for buildStatisticProperty in  buildStatisticProperties:
    if 'BuildDuration' == buildStatisticProperty['name']:
      data['duration']=int(buildStatisticProperty['value'])
  data['startTime']=dateTimeToTimestamp(build['startDate'])
  data['endTime']=dateTimeToTimestamp(build['finishDate'])
  # FIXME: what is instanceUrl ? set to N/A
  data['instanceUrl']="N/A"
  data['jobName']=build['buildType']['projectName']
  # FIXME: what is jobURL? set to webUrl
  data['jobUrl']=build['webUrl']
  try:
    data['log']=changes['comment']
  except Exception as e:
    data['log']=""
  data['niceName']=build['buildType']['id']
  data['number']=build['id']
  if build['triggered']['type'] == "user":
    data['startedBy']=build['triggered']['user']['username']
  elif build['triggered']['type'] == "vcs":
    data['startedBy']="started by VCS trigger"
  
  data['sourceChangeSet']=[]
  sourceChangeSet={}

  if changesEmpty == False:
    for changeIterator in build['lastChanges']['change']:
      try:
        change=tc.get_change_by_change_id(changeIterator['id']) 
      except Exception as e:
        logger.error("can not get change with id %s" % changeIterator['id'])
      else:
        sourceChangeSet['scmRevisionNumber']=change['version']
        sourceChangeSet['scmCommitLog']=change['comment']
        try:
          sourceChangeSet['scmAuthor']=change['user']['name']
        except Exception as e:
          logger.info("user.name is not found for change %s" % changeIterator['id'])
        else:
          sourceChangeSet['scmAuthor']=change['username']

        sourceChangeSet['scmCommitTimestamp']=dateTimeToTimestamp(change['date'])
        sourceChangeSet['numberOfChanges']=1
        data['sourceChangeSet'].append(sourceChangeSet)
  
  dataJson=json.dumps(data)
  
  headers = {'Accept': 'application/json','Content-type':'application/json'}
  url=config['HYGIEIA_API_URL'] + "/build"
  request=requests.post(url, data=dataJson, headers=headers)
  result={}
  result['status_code']=request.status_code
  result['text']=request.text
  return result

def checkEnvironmentVariables(config):
  config["HOST"]="0.0.0.0"
  config['PORT']=80
  config['HYGIEIA_API_URL']=os.getenv("HYGIEIA_API_URL")
  config['TEAMCITY_HOST']=os.getenv("TEAMCITY_HOST")
  config['TEAMCITY_USER']=os.getenv("TEAMCITY_USER")
  config['TEAMCITY_PASSWORD']=os.getenv("TEAMCITY_PASSWORD")

if __name__ == '__main__':
  checkEnvironmentVariables(config)
  httpd = http.server.HTTPServer((config['HOST'], config['PORT']), TCWebHookHandler)
  try:
      httpd.serve_forever()
  except KeyboardInterrupt:
      pass
  httpd.server_close()
