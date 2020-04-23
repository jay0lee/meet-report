import json
import sys

import google.auth
import googleapiclient

def call(service, function, soft_errors=False, throw_reasons=[], **kwargs):
  retries = 10
  parameters = kwargs.copy()
  for n in range(1, retries+1):
    try:
      if function:
        method = getattr(service, function)(**parameters)
      else:
        method = service
      return method.execute()
    except googleapiclient.errors.MediaUploadSizeError as e:
      sys.stderr.write('\nERROR: %s' % (e))
      if soft_errors:
        sys.stderr.write(' - Giving up.\n')
        return
      else:
        sys.exit(int(http_status))
    except googleapiclient.errors.HttpError as e:
      try:
        error = json.loads(e.content.decode('utf-8'))
        reason = error['error']['errors'][0]['reason']
        http_status = error['error']['code']
        message = error['error']['errors'][0]['message']
      except (KeyError, json.decoder.JSONDecodeError):
        http_status = int(e.resp['status'])
        reason = e.content
        message = e.content
      if reason in throw_reasons:
        raise
      if n != retries and (http_status >= 500 or
       reason in ['rateLimitExceeded', 'userRateLimitExceeded', 'backendError']):
        wait_on_fail = (2 ** n) if (2 ** n) < 60 else 60
        randomness = float(random.randint(1,1000)) / 1000
        wait_on_fail += randomness
        if n > 3:
          sys.stderr.write('\nTemp error %s. Backing off %s seconds...'
            % (reason, int(wait_on_fail)))
        time.sleep(wait_on_fail)
        if n > 3:
          sys.stderr.write('attempt %s/%s\n' % (n+1, retries))
        continue
      sys.stderr.write('\n%s: %s - %s\n' % (http_status, message, reason))
      if soft_errors:
        sys.stderr.write(' - Giving up.\n')
        return
      else:
        sys.exit(int(http_status))
    except google.auth.exceptions.RefreshError as e:
      sys.stderr.write('Error: Authentication Token Error - %s' % e)
      sys.exit(403)

def call_pages(service, function, items='items',
 nextPageToken='nextPageToken', page_message=None, message_attribute=None,
 **kwargs):
  pageToken = None
  all_pages = list()
  total_items = 0
  while True:
    this_page = call(service, function,
      pageToken=pageToken, **kwargs)
    if not this_page:
      this_page = {items: []}
    try:
      page_items = len(this_page[items])
    except KeyError:
      page_items = 0
    total_items += page_items
    if page_message:
      show_message = page_message
      try:
        show_message = show_message.replace('%%num_items%%', str(page_items))
      except (IndexError, KeyError):
        show_message = show_message.replace('%%num_items%%', '0')
      try:
        show_message = show_message.replace('%%total_items%%',
          str(total_items))
      except (IndexError, KeyError):
        show_message = show_message.replace('%%total_items%%', '0')
      if message_attribute:
        try:
          show_message = show_message.replace('%%first_item%%',
            str(this_page[items][0][message_attribute]))
          show_message = show_message.replace('%%last_item%%',
            str(this_page[items][-1][message_attribute]))
        except (IndexError, KeyError):
          show_message = show_message.replace('%%first_item%%', '')
          show_message = show_message.replace('%%last_item%%', '')
      rewrite_line(show_message)
    try:
      all_pages += this_page[items]
      pageToken = this_page[nextPageToken]
      if pageToken == '':
        return all_pages
    except (IndexError, KeyError):
      if page_message:
        sys.stderr.write('\n')
      return all_pages
