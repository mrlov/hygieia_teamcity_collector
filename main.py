#!/usr/bin/env python3

import os
import sys
import logging
import json
import requests
import datetime
import pyteamcity
import http.server

config = {}
tc = None
logger = None

def initializeLogger():
  logger = logging.getLogger('teamcity_connector')
  logger.setLevel(logging.DEBUG)
  ch = logging.StreamHandler()
  ch.setLevel(logging.DEBUG)
  formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
  ch.setFormatter(formatter)
  logger.addHandler(ch)
  return logger

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

def getTeamcityConnection(user,password,host):
  tc = pyteamcity.TeamCity(user,password,host)
  try:
    tc.get_server_info()
  except Exception as e:
    logger.error("can not connect to TeamCity: %s" % e)
    result = False
  else:
    result = tc
  return result

def dateTimeToTimestamp(s):
  s=datetime.datetime.strptime(s, "%Y%m%dT%H%M%S%z").timestamp()*1000
  s="%.0f" % s
  return s

def processBuild(buildId):
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
  
  data['buildStatus'] = build['status']
  data['buildUrl'] = build['webUrl']
  buildStatisticProperties = buildStatistic['property']
  for buildStatisticProperty in  buildStatisticProperties:
    if 'BuildDurationNetTime' == buildStatisticProperty['name']:
      data['duration'] = int(buildStatisticProperty['value'])
  data['startTime'] = dateTimeToTimestamp(build['startDate'])
  data['endTime'] = dateTimeToTimestamp(build['finishDate'])
  # FIXME: what is instanceUrl ? set to N/A
  data['instanceUrl']  = "N/A"

  try:
    data['jobName'] = build['buildType']['projectName']
  except Exception as e:
    logger.warn("can not get project name from build type, set to N/A")
    data['jobName'] = "N/A"

  # FIXME: what is jobURL? set to webUrl
  data['jobUrl'] = build['webUrl']
  try:
    data['log'] = changes['comment']
  except Exception as e:
    data['log'] = ""
  data['niceName'] = build['buildType']['id']
  data['number'] = build['id']
  if build['triggered']['type'] == "user":
    data['startedBy'] = build['triggered']['user']['username']
  elif build['triggered']['type'] == "vcs":
    data['startedBy'] = "started by VCS trigger"
  
  data['sourceChangeSet'] = []
  sourceChangeSet = {}

  if changesEmpty == False:
    for changeIterator in build['lastChanges']['change']:
      try:
        change=tc.get_change_by_change_id(changeIterator['id']) 
      except Exception as e:
        logger.error("can not get change with id %s" % changeIterator['id'])
      else:
        sourceChangeSet['scmRevisionNumber'] = change['version']
        sourceChangeSet['scmCommitLog'] = change['comment']
        try:
          sourceChangeSet['scmAuthor'] = change['user']['name']
        except Exception as e:
          sourceChangeSet['scmAuthor'] = ''
          logger.info("user.name is not found for change %s, set to username" % changeIterator['id'])
        else:
          sourceChangeSet['scmAuthor'] = change['username']
        if sourceChangeSet['scmAuthor'] == '' && build['triggered']['type'] == "vcs":
          sourceChangeSet['scmAuthor'] = "started by VCS trigger"
        else:
          logger.error("can not get \"triggered by\" value for buildId %s" % buildId)
        sourceChangeSet['scmCommitTimestamp'] = dateTimeToTimestamp(change['date'])
        sourceChangeSet['numberOfChanges'] = 1
        data['sourceChangeSet'].append(sourceChangeSet)
  
  dataJson=json.dumps(data)
  
  headers = {'Accept': 'application/json','Content-type':'application/json'}
  url=config['HYGIEIA_API_URL'] + "/build"
  request=requests.post(url, data = dataJson, headers = headers)
  logger.info("new build ID: %s" % build['id'])
  result={}
  result['status_code']=request.status_code
  result['text']=request.text
  return result

def checkEnvironmentVariables(config):
  result = True
  config["HOST"] = "0.0.0.0"
  config['PORT'] = 80
  if "HYGIEIA_API_URL" in os.environ:
    config['HYGIEIA_API_URL'] = os.getenv("HYGIEIA_API_URL")
  else:
    logger.error("HYGIEIA_API_URL environmanet variable is not set")
    result = False

  if "TEAMCITY_HOST" in os.environ:
    config['TEAMCITY_HOST'] = os.getenv("TEAMCITY_HOST")
  else:
    logger.error("TEAMCITY_HOST environmanet variable is not set")
    result=False

  if "TEAMCITY_USER" in os.environ:
    config['TEAMCITY_USER'] = os.getenv("TEAMCITY_USER")
  else:
    logger.info("TEAMCITY_USER environment variable is not set, trying with empty")
    config['TEAMCITY_USER'] = ""

  if "TEAMCITY_PASSWORD" in os.environ:
    config['TEAMCITY_PASSWORD'] = os.getenv("TEAMCITY_PASSWORD")
  else:
    logger.info("TEAMCITY_PASSWORD environment variable is not set, trying with empty")
    config['TEAMCITY_PASSWORD'] = ""
  return result

if __name__ == '__main__':
  logger = initializeLogger()
  if checkEnvironmentVariables(config) == True:
    tc = getTeamcityConnection(config['TEAMCITY_USER'], config['TEAMCITY_PASSWORD'], config['TEAMCITY_HOST'])
    if tc != False:
      httpd = http.server.HTTPServer((config['HOST'], config['PORT']), TCWebHookHandler)
      try:
          httpd.serve_forever()
      except KeyboardInterrupt:
          pass
      httpd.server_close()

