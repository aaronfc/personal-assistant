import httplib2
import os
import time
import random
import json
import sys
import datetime
import iso8601
import pytz
import subprocess

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

'''
 Memory class
'''
class Memory:
	def __init__(self, filename):
		self.filename = filename
	def __all(self):
		data = {}
		with open(self.filename) as f:
			data = json.load(f)
		return data
		
	def set(self, key, value):
		data = self.__all()
		data[key] = value
		with open(self.filename, 'w') as f:
			json.dump(data, f)
	def get(self, key, default=None):
		data = self.__all()
		if key in data:
			return data[key]
		return None
	def __getitem__(self, key):
		return self.get(key)
	def __setitem__(self, key, value):
		self.set(key, value)

'''
 Google credentials management
'''
try:
	import argparse
	flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
	flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/gmail-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Gmail API Python Quickstart'


def get_credentials():
	"""Gets valid user credentials from storage.

	If nothing has been stored, or if the stored credentials are invalid,
	the OAuth2 flow is completed to obtain the new credentials.

	Returns:
		Credentials, the obtained credential.
	"""
	home_dir = "/home/aaron"
	credential_dir = os.path.join(home_dir, '.credentials')
	if not os.path.exists(credential_dir):
		os.makedirs(credential_dir)
	credential_path = os.path.join(credential_dir,
								   'gmail-python-quickstart.json')

	store = Storage(credential_path)
	credentials = store.get()
	if not credentials or credentials.invalid:
		flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
		flow.user_agent = APPLICATION_NAME
		if flags:
			credentials = tools.run_flow(flow, store, flags)
		else: # Needed only for compatibility with Python 2.6
			credentials = tools.run(flow, store)
		eprint('Storing credentials to ' + credential_path)
	return credentials

'''
 Text to speech
'''
def say(text, lang='es'):
	import os
	options = '-a 30 -s 220 -p20 -a 200'
	is_headset_on = os.popen('(pacmd list-sinks | grep -q -B 1 bluez_sink.04_52_C7_08_88_E9) && echo "YES" || echo "NO"').read().strip() == "YES"
	if is_headset_on:
		eprint("Loudly saying: {}".format(text))
		os.system('espeak {} -a 10 -v{}+f3 "{}" --stdout | aplay'.format(options, lang, text))
	else:
		print("Personal Assistant: {}".format(text))

'''
Stderr print function
'''
def eprint(*args, **kwargs):
	print(*args, file=sys.stderr, **kwargs)

'''
 Main loop
'''
def main(long_memory, short_memory):
	"""Shows basic usage of the Gmail API.

	Creates a Gmail API service object and outputs a list of label names
	of the user's Gmail account.
	"""
	credentials = get_credentials()
	http = credentials.authorize(httplib2.Http())
	gmail_service = discovery.build('gmail', 'v1', http=http)
	calendar_service = discovery.build('calendar', 'v3', http=http)

	while True:
		try:
			# Handle idle status
			idle_time = int(os.popen("xprintidle").read())
			eprint ("IDLE_TIME={}".format(idle_time))
			is_user_just_back = False
			if idle_time > 300000:
				short_memory['is_user_idle'] = True
			elif short_memory['is_user_idle']:
				short_memory['is_user_idle'] = False
				is_user_just_back = True
			
			# Get emails
			results = gmail_service.users().messages().list(userId='me', q='is:unread in:inbox').execute()
			messages = results.get('messages', [])
			
			
			# Handling emails
			messages_amount = len(messages)
			unread_emails = set()
			for message in messages:
				uid = '{}_{}'.format(message['id'], message['threadId'])
				unread_emails.add(uid)
			eprint ('Unread emails: {}'.format(messages_amount))

			# First-run
			# if short_memory['is_first_run']:
			# 	# Open todo-tuenti
			# 	os.system("wmctrl -a TODO || gnome-terminal -e 'bash -c \"todo-tuenti\"'")

			# First-run or just_back
			if short_memory['is_first_run'] or is_user_just_back:
				# Emails
				if messages_amount == 1:
					say("Tienes un imeil sin leer")
				elif messages_amount > 1:
					say("Tienes {} imeils sin leer".format(messages_amount))
				short_memory['is_first_run'] = False
				short_memory['seen_emails'] = short_memory['seen_emails'].union(unread_emails)
			# TODO Tell out the emails not read


			# Retrieving next calendar event
			now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
			eprint('Getting upcoming events')
			eventsResult = calendar_service.events().list(
					calendarId='primary', timeMin=now, maxResults=2, singleEvents=True,
					orderBy='startTime').execute()
			events = eventsResult.get('items', [])

			if not events:
				eprint('No upcoming events found.')

			for event in events:
				event_id = event['id']
				start = event['start'].get('dateTime', event['start'].get('date'))
				eprint(start, event['summary'], event['status'])
				dt = iso8601.parse_date(start)
				time_difference = dt - datetime.datetime.now(pytz.UTC)

				if time_difference.total_seconds() < 0 or time_difference.total_seconds() > 86400/2:
					continue # Skip already started events or tomorrow's
				if event_id not in short_memory['seen_events'] or is_user_just_back:
					short_memory['seen_events'].add(event_id)
					say("Próximo evento a las {}:{}. Resumen:".format(dt.hour, dt.minute))  
					say("{}".format(event['summary']), 'en') # Summary is usually in english
				elif time_difference.total_seconds() <= 300:
					if event_id not in short_memory['handled_events']:
						short_memory['handled_events'].add(event_id)
						say("Ey! Evento a las {}:{}. Resumen:".format(dt.hour, dt.minute))  
						say("{}".format(event['summary']), 'en') # Summary is usually in english
						if 'hangoutLink' in event:
							link = event['hangoutLink']
							os.system("export DISPLAY=:0; firefox -P tuenti --new-window {}".format(link))


			# Sleeping
			time_to_sleep = 60 # One minute
			eprint ('Sleeping {} seconds'.format(time_to_sleep))
			time.sleep(time_to_sleep)
		except Exception as e:
			eprint (e)
			eprint ("Exception when trying to get messages.")


#	results = service.users().labels().list(userId='me').execute()
#	labels = results.get('labels', [])
#
#	if not labels:
#		print('No labels found.')
#	else:
#	  print('Labels:')
#	  for label in labels:
#		print(label['name'])


def initialize_memories():
	# Long term memory is persisted on JSON file
	long_memory = Memory('memory.json')
	long_memory['born_time'] = long_memory.get('born_time', time.time())

	# Short term memory is a simple dictionary
	short_memory = {}
	short_memory['is_first_run'] = True
	short_memory['is_user_idle'] = False
	short_memory['start_time'] = time.time()
	short_memory['seen_emails'] = set()
	short_memory['seen_events'] = set()
	short_memory['handled_events'] = set()

	return long_memory, short_memory
	


if __name__ == '__main__':
	long_memory, short_memory = initialize_memories()
	main(long_memory, short_memory)

