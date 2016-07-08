from time import sleep
from slackclient import SlackClient
import os
from datetime import datetime
from library import *
from pytz import timezone
import atexit
from tinys3 import Connection

NAME = 'device_bot'

posted = False

usage = """
Welcome to the IIT Mobile Testing Device Library!

You can checkout a device like this. Supplying a username will take it for that person.
`devicetake <device name> [@<username>]`
You can return a device like this. Supplying a username will return it for that person.
`devicereturn <device name> [@<username>]`
You can see a list of all borrowed devices like this. This will also happen once a week automatically
`devices`

Any message with "device" and "help" and I'll show this message!

If you have any comments, complaints, or bug reports, message Jack Reichelt.
"""

TOKEN = os.environ.get('TOKEN', None) # found at https://api.slack.com/web#authentication
S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY', None)
S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY', None)

conn = Connection(S3_ACCESS_KEY, S3_SECRET_KEY, endpoint='s3-ap-southeast-2.amazonaws.com')

saved_subs = conn.get('borrowers.txt', 'iit-devices')

f = open('borrowers.txt', 'wb')
f.write(saved_subs.content)
f.close()

lib = Library()

@atexit.register
def save_library():
  print('Writing devices.')
  lib.write_library()
  conn.upload('borrowers.txt', open('borrowers.txt', 'rb'), 'iit-devices')

sc = SlackClient(TOKEN)
if sc.rtm_connect() == True:
  print('Connected.')

  sc.api_call("im.list")

  while True:
    response = sc.rtm_read()
    for part in response:
      print(part)
      if 'ims' in part:
        channels = part['ims']
      if part['type'] == 'message' and 'text' in part:
        words = part['text'].split()

        # Borrowing a device for another user
        if words[0] == 'devicetake' and words[-1].startswith('<@'):
          user = sc.server.users.find(words[-1][2:-1])
          if user == None:
            sc.api_call("chat.postMessage", channel=part['channel'], text="That user doesn't exist. Try tagging them with @.", username=NAME, icon_emoji=':iphone:')
          else:
            user_id = user.id
            username = user.real_name
            lib.borrow_device(user_id, username, ' '.join(words[1:-1]))
            sc.api_call("chat.postMessage", channel=part['channel'], text="{} has borrowed {}.".format(username, ' '.join(words[1:-1])), username=NAME, icon_emoji=':iphone:')

        # Borrowing a device for themselves
        elif words[0] == 'devicetake':
          user_id = part['user']
          username = sc.api_call("users.info", user=user_id)['user']['profile']['real_name']

          lib.borrow_device(user_id, username, ' '.join(words[1:]))
          sc.api_call("chat.postMessage", channel=part['channel'], text="{} has borrowed {}.".format(username, ' '.join(words[1:])), username=NAME, icon_emoji=':iphone:')

        # Returning a device for another user
        elif words[0] == 'devicereturn' and words[-1].startswith('<@'):
          lib_response = lib.return_device(words[-1][2:-1], ' '.join(words[1:-1]))

          if lib_response == -1:
            sc.api_call("chat.postMessage", channel=part['channel'], text="That user doesn't have any devices borrowed.", username=NAME, icon_emoji=':iphone:')
          elif lib_response == -2:
            sc.api_call("chat.postMessage", channel=part['channel'], text="That user hasn't borrowed that device.", username=NAME, icon_emoji=':iphone:')
          else:
            sc.api_call("chat.postMessage", channel=part['channel'], text="{} has been returned.".format(' '.join(words[1:-1])), username=NAME, icon_emoji=':iphone:')

        # Returning a device for themselves
        elif words[0] == 'devicereturn':
          lib_response = lib.return_device(part['user'], ' '.join(words[1:]))

          if lib_response == -1:
            sc.api_call("chat.postMessage", channel=part['channel'], text="You don't have any devices borrowed.", username=NAME, icon_emoji=':iphone:')
          elif lib_response == -2:
            sc.api_call("chat.postMessage", channel=part['channel'], text="You haven't borrowed that device.", username=NAME, icon_emoji=':iphone:')
          else:
            sc.api_call("chat.postMessage", channel=part['channel'], text="{} has been returned.".format(' '.join(words[1:])), username=NAME, icon_emoji=':iphone:')

        elif len(words) == 1 and words[0] == 'devices':
          if lib.count():
            sc.api_call("chat.postMessage", channel=part['channel'], text=lib.all_borrowed_devices(), username=NAME, icon_emoji=':iphone:')
          else:
            sc.api_call("chat.postMessage", channel=part['channel'], text='There are no borrowed devices.', username=NAME, icon_emoji=':iphone:')

        elif ('device' in words and 'help' in words) or 'devicehelp' in words:
          sc.api_call("chat.postMessage", channel=part['channel'], text=usage, username=NAME, icon_emoji=':iphone:')

        save_library()

    # deviceclub channel is C0QPDRHD2
    if 0 <= datetime.now(timezone('Australia/Sydney')).time().hour < 1 and posted == True: #midnight to 1am
      print('It\'s a new day.')
      posted = False
    if 9 <= datetime.now(timezone('Australia/Sydney')).time().hour < 10 and posted == False and datetime.now(timezone('Australia/Sydney')).weekday() == 3: #3pm to 5pm
      print('It\'s device alert time!')
      posted = True
      sc.api_call("chat.postMessage", channel='C0QPDRHD2', text=lib.all_borrowed_devices(), username=NAME, icon_emoji=':iphone:')

    sleep(1)
else:
  print('Connection Failed, invalid token?')