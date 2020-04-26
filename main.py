# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python37_app]
from base64 import urlsafe_b64encode
import datetime
import json
from urllib.parse import urlparse, parse_qs
from secrets import SystemRandom
from operator import itemgetter 
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Flask, request, redirect, jsonify, abort
from google.cloud import datastore
import google.oauth2.credentials
import googleapiclient.discovery
import httplib2
import google_auth_httplib2
import pytz


import gapi
from config import *

def store_endpoint_id(endpoint_id, timestamp):
  client = datastore.Client()
  key = client.key('endpoint_id', endpoint_id)
  entity = datastore.Entity(key)
  entity['endpoint_id'] = endpoint_id 
  entity['timestamp'] = timestamp
  client.put(entity)

def local_time(udt):
  tzone = pytz.timezone(TIMEZONE)
  ldt = udt.astimezone(tzone)
  return ldt.strftime('%-I:%M%p')

def draw_meetings(gmail, meetings):
  for meet in meetings.values():
    output = '<html><body>'
    output += 'Here\'s some details about your recent Google Meet call:<br><br>'
    if meet.get('calendar_event'):
      summary = meet["calendar_event"].get("summary", "<No title>")
      htmlLink = meet["calendar_event"].get("htmlLink", "")
      output += f'Calendar Event: <a href="{htmlLink}">{summary}</a><br>'
    output += f'Meeting code: <a href="https://meet.google.com/{meet["meeting_code"]}">{meet["meeting_code"]}</a><br>'
    output += f'Time: {local_time(meet["start_time"])} - {local_time(meet["end_time"])} {TIMEZONE}<br>'
    output += f'{len(meet["attendees"])} attendees:<br><ul>'
    rcpts = []
    if TO_ORGANIZER:
      rcpts.append(meet['organizer_email'])
    endpoint_ids = []
    for attendee, times in meet['attendees'].items():
      for atime in times:
        if atime.get('identifier_type') == 'email_address':
          if TO_ATTENDEES:
            rcpts.append(attendee)
          attendee = f'<a href="mailto:{attendee}">{atime.get("display_name")}</a>'
          break
      output += f'<li>{attendee}:'
      for atime in sorted(times, key=itemgetter('joined_time')):
        output += f' {local_time(atime["joined_time"])} - {local_time(atime["left_time"])}'
        if SHOW_DEVICE_TYPE and 'device_type' in atime:
          output += f' {atime["device_type"]}'
        if SHOW_IP and 'ip_address' in atime:
          output += f', {atime["ip_address"]}'
        if SHOW_LOCATION and 'location_region' in atime:
          output += f', {atime["location_region"]}'
        if SHOW_LOCATION and 'location_country' in atime:
          output += f', {atime["location_country"]}'
        endpoint_ids.append(atime['endpoint_id'])
      output += '</li>'
    output += '</ul></body></html>'
    if meet.get('calendar_event'):
      subject = SUBJECT_FOR_CALENDAR_MEETINGS.format(
          event_summary=meet['calendar_event'].get('summary', '<no title>'),
          meeting_code=meet['meeting_code'])
    else:
      subject = SUBJECT_FOR_MEETINGS.format(meeting_code=meet['meeting_code'])
    ref_domain = os.environ.get('GAE_APPLICATION', 'unknown-meet-report-instance.appspot.com')
    if ref_domain.find('~') != -1:
      ref_domain = ref_domain.split('~')[1]
      ref_domain += '.appspot.com'
    references = f'<{meet["meeting_code"]}@{ref_domain}>'
    send_email(gmail, rcpts, subject, output, references)
    timestamp = datetime.datetime.utcnow()
    for id in endpoint_ids:
      store_endpoint_id(id, timestamp)

def send_email(gmail, rcpts, subject, body, references=None):
  msg = MIMEMultipart("alternative")
  msg.attach(MIMEText(body, 'html'))
  msg['Subject'] = subject
  if rcpts:
    msg['To'] = ', '.join(rcpts)
  if BCC_ADDRESS:
    msg['Bcc'] = BCC_ADDRESS
  if references:
    msg['References'] = references
  encoded_email = urlsafe_b64encode(msg.as_bytes()).decode()
  api_body = {'raw': encoded_email}
  gmail.users().messages().send(userId='me', body=api_body).execute()  

def fetch_all_endpoint_ids():
  endpoint_ids = []
  client = datastore.Client()
  query = client.query(kind='endpoint_id')
  query_iter = query.fetch()
  for entity in query_iter:
    endpoint_ids.append(entity.get('endpoint_id'))
  return list(set(endpoint_ids))

str_params = ['device_type', 'display_name', 'endpoint_id',
              'identifier_type', 'ip_address', 'location_country',
              'location_region',]
bool_params = ['is_external', ]

def parse_report(report, cal, ignore_endpoint_ids=[]):
  '''Takes a Meet Activity Report and parses into something we can chew'''
  meetings = {}
  now = datetime.datetime.utcnow()
  defer_if_event_after = now - datetime.timedelta(minutes=DEFER_IF_EVENT_SOONER_THAN_MINUTES)
  for meeting in report:
    left_time = meeting['id']['time'][:-1]
    left_time = datetime.datetime.fromisoformat(left_time)
    for event in meeting.get('events', []):
      left_event = {'left_time': left_time}
      is_meet = True
      conference_id = identifier = meeting_code = calendar_event_id = organizer_email = None
      for param in event.get('parameters', []):
        name = param.get('name', 'NOTSET')
        if name == 'product_type' and param.get('value').lower() != 'meet':
          is_meet = False
          break
        elif name == 'conference_id':
          conference_id = param.get('value')
        elif name == 'meeting_code':
          meeting_code = param.get('value')
          meeting_code = meeting_code.lower()
          if len(meeting_code) == 10:
            meeting_code = f'{meeting_code[:3]}-{meeting_code[3:7]}-{meeting_code[7:]}'
        elif name == 'calendar_event_id':
          calendar_event_id = param.get('value')
        elif name == 'organizer_email':
          organizer_email = param.get('value')
        elif name == 'identifier':
          identifier = param.get('value')
        elif name in str_params:
          left_event[name] = param.get('value')
        elif name in bool_params:
          left_event[name] = bool(param.get('boolValue'))
        elif name == 'duration_seconds':
          left_event[name] = int(param.get('intValue'))
          left_event['joined_time'] = left_event['left_time'] - datetime.timedelta(seconds=left_event[name])
      if not is_meet:
        print(f'skipping non meet meeting {conference_id}')
        continue
      if not conference_id:
        print(f'skipping end_call with no conference_id: {event}')
        continue
      if left_event.get('endpoint_id') in ignore_endpoint_ids:
        print(f'skipping ignored endpoint {left_event["endpoint_id"]}')
        continue
      if not identifier: # anonymous web user
        identifier = left_event.get('display_name', 'No Name Set')
      if conference_id in meetings:
        if meeting_code and not meetings[conference_id]['meeting_code']:
          meetings[conference_id]['meeting_code'] = meeting_code
        if calendar_event_id and not meetings[conference_id]['calendar_event_id']:
          meetings[conference_id]['calendar_event_id'] = calendar_event_id
        if organizer_email and not meetings[conference_id]['organizer_email']:
          meetings[conference_id]['organizer_email'] = organizer_email
        if identifier in meetings[conference_id]['attendees']:
          meetings[conference_id]['attendees'][identifier].append(left_event)
        else:
          meetings[conference_id]['attendees'][identifier] = [left_event, ]
        if left_event['left_time'] > meetings[conference_id]['end_time']:
          meetings[conference_id]['end_time'] = left_event['left_time']
        if left_event['joined_time'] < meetings[conference_id]['start_time']:
          meetings[conference_id]['start_time'] = left_event['joined_time']
      else:
        meetings[conference_id] = {'meeting_code': meeting_code,
                                   'calendar_event_id': calendar_event_id,
                                   'organizer_email': organizer_email,
                                   'start_time': left_event.get('joined_time', now),
                                   'end_time': left_event.get('left_time', now),
                                   'attendees': {identifier: [left_event]}}
  organized_meetings = {}
  print(f'len meetings = {len(meetings)}')
  for meeting, val in meetings.items():
    if val['end_time'] > defer_if_event_after:
      print('deferring meeting with recent end call events')
      continue
    val['duration'] = (val['end_time'] - val['start_time']).total_seconds()
    if val['duration'] < MINIMUM_MEETING_DURATION_SECONDS:
      print(f'skipping short meeting of {val["duration"]} seconds')
      continue
    if len(val['attendees']) < MINIMUM_MEETING_ATTENDEES:
      print(f'skipping meeting with only {len(val["attendees"])}')
      continue 
    if not val['organizer_email']:
      print('skipping meeting with no organizer')
      continue
    if 'calendar_event_id' in val:
      val['calendar_event'] = get_event(val['organizer_email'], val['calendar_event_id'], cal)
    organized_meetings[meeting] = val
  print(f'len organized_meetings = {len(organized_meetings)}')
  return organized_meetings

def get_event(calendarId, eventId, cal):
  fields = 'summary,htmlLink'
  try:
    results = cal.events().get(calendarId=calendarId, eventId=eventId, fields=fields).execute()
    if not results.get('summary'):
      results.pop('summary', None)
    return results
  except:
    pass

app = Flask(__name__)

@app.route('/send-reports', methods=['GET'])
def send_reports():
  if request.headers.get('X-Appengine-Cron') != 'true':
    abort(404)
  already_parsed_endpoint_ids = fetch_all_endpoint_ids()
  print(already_parsed_endpoint_ids)
  with open('oauth2.txt') as f:
    cdata = json.load(f)
  httpc = httplib2.Http()
  req = google_auth_httplib2.Request(httpc)
  creds = google.oauth2.credentials.Credentials.from_authorized_user_file('oauth2.txt')
  creds.token = cdata.get('token', cdata.get('auth_token', ''))
  creds._id_token = cdata.get('id_token_jwt', cdata.get('id_token', None))
  token_expiry = cdata.get('token_expiry', '1970-01-01T00:00:01Z')
  creds.expiry = datetime.datetime.strptime(token_expiry, '%Y-%m-%dT%H:%M:%SZ')
  creds.refresh(req)
  httpc = google_auth_httplib2.AuthorizedHttp(creds, httpc)
  rep = googleapiclient.discovery.build('admin', 'reports_v1', http=httpc, cache_discovery=False)
  gmail = googleapiclient.discovery.build('gmail', 'v1', http=httpc, cache_discovery=False)
  cal = googleapiclient.discovery.build('calendar', 'v3', http=httpc, cache_discovery=False)
  now = datetime.datetime.utcnow()
  two_days_ago = now - datetime.timedelta(days=2)
  two_days_ago = two_days_ago.isoformat(timespec='seconds') + 'Z'
  min_age = now - datetime.timedelta(minutes=MINIMUM_AGE_MINUTES)
  min_age = min_age.isoformat(timespec='seconds') + 'Z'
  print(f'Start time: {two_days_ago}  End time: {min_age}')
  response = gapi.call_pages(rep.activities(), 'list', applicationName='meet',
                             userKey='all', eventName='call_ended',
                             startTime=two_days_ago, endTime=min_age)
  meetings = parse_report(response, cal, ignore_endpoint_ids=already_parsed_endpoint_ids)
  draw_meetings(gmail, meetings)
  return 'all done!'

@app.route('/cleanup', methods=['GET'])
def cleanup():
  if request.headers.get('X-Appengine-Cron') != 'true':
    abort(404)
  client = datastore.Client()
  q = client.query(kind='endpoint_id')
  three_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days = 3)
  q.add_filter('timestamp', '<', three_days_ago)
  q.keys_only()
  keys = [key.key for key in list(q.fetch())]
  max_chunk_size = 500
  chunked_keys = [keys[i * max_chunk_size:(i + 1) * max_chunk_size] for i in range((len(keys) + max_chunk_size - 1) // max_chunk_size )]
  for key_chunk in chunked_keys:
    client.delete_multi(key_chunk)
  return 'Deleted %s codes' % len(keys)

 
if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='0.0.0.0', port=8080, debug=True)
# [END gae_python37_app]
