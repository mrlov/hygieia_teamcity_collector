#!/usr/bin/env python3

import os
import sys
import logging
import json
import requests
import datetime
import pyteamcity
import http.server
import validators

from urllib.parse import urlparse

config = {}
tc = None
logger = None

def initializeLogger():
  logger = logging.getLogger('teamcity_connector')
  logger.setLevel(logging.INFO)
  ch = logging.StreamHandler()
  ch.setLevel(logging.INFO)
  formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
  ch.setFormatter(formatter)
  logger.addHandler(ch)
  return logger

class TCWebHookHandler(http.server.BaseHTTPRequestHandler):
  def do_POST(self):
    contentLen = int(self.headers['Content-Length'])
    postBody=self.rfile.read(contentLen)
    postBody = postBody.decode("utf-8")
    postBody=json.loads(postBody)
    buildId=postBody['build']['buildId']
    result=processBuild(buildId)
    self.send_response(result['status_code'])
    self.end_headers()
    self.wfile.write(result['text'].encode("utf-8"))
    return

def getTeamcityConnection(user,password,url):
  url_parsed = urlparse(url)
  tc = pyteamcity.TeamCity(user,password,url_parsed.hostname,url_parsed.port)
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
    logger.debug("buildId: %s" % buildId)
    logger.debug("build: %s" % build)
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
  if 'finishDate' in build:
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
        if sourceChangeSet['scmAuthor'] == '' and build['triggered']['type'] == "vcs":
          sourceChangeSet['scmAuthor'] = "started by VCS trigger"
        elif sourceChangeSet['scmAuthor'] == '' and build['triggered']['type'] == "user":
          sourceChangeSet['scmAuthor'] = build['triggered']['user']['username']
        else:
          logger.error("can not get \"triggered by\" value for buildId %s" % buildId)
        sourceChangeSet['scmCommitTimestamp'] = dateTimeToTimestamp(change['date'])
        sourceChangeSet['numberOfChanges'] = 1
        data['sourceChangeSet'].append(sourceChangeSet)
  
  dataJson=json.dumps(data)
  
  logger.debug("dataJson: %s" % dataJson)

  headers = {'Accept': 'application/json','Content-type':'application/json'}
  url=config['HYGIEIA_API_URL'] + "/build"
  request=requests.post(url, data = dataJson, headers = headers)
  logger.debug("request: %s" % request)
  logger.debug("build ID: %s" % build['id'])
  result={}
  result['status_code']=request.status_code
  result['text']=request.text
  logger.debug("result: %s" % result)
  return result

def checkEnvironmentVariables(config):
  result = True
  config["HOST"] = "0.0.0.0"
  config['PORT'] = 80
  if "HYGIEIA_API_URL" in os.environ and validators.url(os.getenv("HYGIEIA_API_URL")):
    config['HYGIEIA_API_URL'] = os.getenv("HYGIEIA_API_URL")
  else:
    logger.error("HYGIEIA_API_URL environmanet variable is not set")
    result = False

  if "TEAMCITY_URL" in os.environ and validators.url(os.getenv("TEAMCITY_URL")):
    config['TEAMCITY_URL'] = os.getenv("TEAMCITY_URL")
  else:
    logger.error("TEAMCITY_URL environmanet variable is not set")
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
    tc = getTeamcityConnection(config['TEAMCITY_USER'], config['TEAMCITY_PASSWORD'], config['TEAMCITY_URL'])
    if tc != False:
      httpd = http.server.HTTPServer((config['HOST'], config['PORT']), TCWebHookHandler)
      try:
          httpd.serve_forever()
      except KeyboardInterrupt:
          pass
      httpd.server_close()

