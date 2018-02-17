# -*- coding: utf-8 -*-

from __future__ import print_function
from builtins import input

import sys
import signal
import os
import pickle
#import time
import datetime
import readline
import logging
from colored import fore, back, style
import click

from langdetect import detect_langs
from langdetect import DetectorFactory
DetectorFactory.seed = 0

from rasa_nlu.model import Metadata, Interpreter
from rasa_nlu.config import RasaNLUConfig

import configparser
#import re
#from string import Template
import util as u # some local utility functions

class Core:
    """Core is the main class for MLB"""

    def pickle_user_dict(self):
        """Pickles the user dictionary to pickle file so that subsequent runs still keep the same user metrics (if available)"""
        try:
            pickle_out = open(self.pickle_file,'wb')
            pickle.dump(self.user_dict, pickle_out)
            pickle_out.close()
        except Exception as e:
            self.logger.warn('Problem pickling user dictionary')
        return

    def unpickle_user_dict(self):
        """Unpickles (loads) the user dictionary from pickle file so that subsequent runs still keep the same user metrics (if available)"""
        if os.path.exists(self.pickle_file):
            try:
                pickle_in = open(self.pickle_file,'rb')
                self.user_dict = pickle.load(pickle_in)
            except Exception as e:
                self.logger.warn('Problem unpickling user dictionary')
                self.user_dict = {}
        else:
            self.logger.info('No pickle file found (' + self.pickle_file + ') so setting user_dict to empty.')
            self.user_dict = {}
        return


    def before_quit(self):
        """Does any required closinng of resources prior to the programme quiting
        and then reports end of script execution"""
        self.pickle_user_dict()
        try:
            self.logger.warn('Ending script execution now\n')
        except (AttributeError, NameError) as e:
            print('Ending script execution now\n(logger was not found.)\n')
        sys.exit()


    def handle_ctrl_c(self, signal, frame):
        # TODO: test the behaviour on Windows
        #       close down anything that should be closed before exiting
        self.before_quit()
        sys.exit(130)  # 130 is standard exit code for <ctrl> C


    def highlight(self, text, entities, sty_start = u.STY_DESC_INV, sty_end = u.STY_DESC):
        start = 0
        output = ''
        for span in entities:
            output = output + text[start:(int(span['start']))] + sty_start + text[(int(span['start'])):(int(span['end']))] + sty_end
            start = int(span['end'])
        output = output + text[start:] + style.RESET
        return output


    def get_user(self, user_id=None):
        if user_id not in self.user_dict:
            new_user = {}
            new_user['msg_output'] = ''

            new_user['lang_selected'] = 'en'

            new_user['last_interaction_time'] = None
            new_user['this_interaction_time'] = None

            new_user['input_counter'] = 0
            new_user['session_counter'] = 0
            new_user['total_sessions'] = 0
            new_user['current_buttons'] = []

            self.user_dict[user_id] = new_user
            #self.logger.debug('get_user is returning new user ' + str(user_id))
            return new_user
        #self.logger.debug('get_user is returning existing user ' + str(user_id))
        return self.user_dict[user_id]


    def get_user_language(self):
        """Returns the current user's language"""
        return self.langs_handled[self.user['lang_selected']]


    def update_user_dict(self, user_id=None, user=None):
        self.user_dict[user_id] = user


    def interaction_controls(self, user_input):
        """Handling for various UI interactions usually executed as part of the main loop

        Return: False if no interaction, otherwise returns True (except when quitting)"""

        # Only want these enabled when running locally (ie screen)
        if self.CHANNEL_IN == 'screen':
            ui_lower = user_input.lower()
            if ui_lower == ':q':
                print(
                    '\t\t' + u.STY_RESP + '  Okay.  Goodbye!  ' + u.STY_USER +
                    '\n')
                self.before_quit()
            elif ui_lower == ':l':
                self.show_language = not self.show_language
                self.print_settings('Show_language: ' + {True: 'on', False: 'off'}[self.show_language])
                return True
            elif ui_lower == ':u':
                self.user_stats = not self.user_stats
                self.print_settings('User stats: ' + str(self.user_stats))
                return True
            elif ui_lower == ':s':
                self.show_parse = not self.show_parse
                self.print_settings(
                    'Show_parse: ' + {True: 'on', False: 'off'}[self.show_parse])
                return True
            elif ui_lower == ':h':
                self.show_highlight = not self.show_highlight
                self.print_settings(
                    'Show_highlight: ' + {True: 'on', False: 'off'}[self.show_highlight])
                return True
            elif ui_lower == ':c':
                u.clear_screen()
                return True
            elif ui_lower == ':d':
                self.logger.setLevel(logging.DEBUG)
                self.logger.info('Logging level set to DEBUG')
                return True
            elif ui_lower == ':i':
                self.logger.setLevel(logging.INFO)
                self.logger.info('Logging level set to INFO')
                return True
            elif ui_lower == ':w':
                self.logger.setLevel(logging.WARNING)
                self.logger.warn('Logging level set to WARN')
                return True
            elif user_input in (':1', ':2', ':3'):
                self.button_selection(self.user_input, self.show_parse)
                return True
        return False


    def print_settings(self, text, out=sys.stdout, invisible=False):
        """A screen-only output function for printing settings changes that do not
        go to remote users. Typically to give a more human friendly and detailed
        level than might be sent to the logs.

        Invisible: suppresses subsequent output (ie NUMPY forced errors
        NB: use sparingly as hides errors too!"""
        
        if invisible:
            print(u.STY_DESC + text + u.STY_INVISIBLE)
        else:
            print(u.STY_DESC + text + u.STY_USER)


    def update_user_stats(self):
        """Updates the user stats, such as interaction counts etc"""
        self.user['last_interaction_time'] = self.user['this_interaction_time']
        self.user['this_interaction_time'] = datetime.datetime.now()
        self.user['input_counter'] += 1
        if self.user['last_interaction_time'] is not None:
            if (self.user['last_interaction_time'] + datetime.timedelta(minutes=self.SESSION_TIME_LIMIT)) < datetime.datetime.now():
                self.user['session_counter'] = 0
                self.user['total_sessions'] += 1
        self.user['session_counter'] += 1


    def print_user_stats(self, display=False):
        """Outputs current user stats, such as interaction counts etc"""

        if display:
            print(('\n\t{l1} Input counter: {d1}{input_counter}\t{l1} Session counter: {d1}{session_counter}\t{l1} Total sessions: {d1}{total_sessions}' + \
                '\t{l1} Last interaction time: {d1}{last_interaction_time}\n' + \
#                '\t{l1} This interaction time: {d1}{this_interaction_time}\n{e}').format(**self.user, d1=u.STY_STAT_DATA,l1=u.STY_STAT_LABEL,e=u.STY_USER))
                '\t{l1} This interaction time: {d1}{this_interaction_time}\n{e}').format(**self.user, d1=u.STY_STAT_DATA,l1=u.STY_STAT_LABEL,e=u.STY_USER))


    def pick(self, pick_list):
        if type(pick_list) == list:
            if len(pick_list) > 0:
                return pick_list[self.user['session_counter'] % len(pick_list)]
            else:
                return ''
        else:
            return ''


    def button_selection(self, button_choice=None, show_parse=False):
        """Displays then returns the user selection as if they had typed it in 
        rather than selected it via a button"""

        prompt_text = '>'
        if button_choice is not None:
            button_choice = button_choice.replace(':','')
            self.logger.debug('User selected a button (' + button_choice + ')')
            int_button_choice = int(button_choice) - 1
            if (int_button_choice in range(len(self.user['current_buttons']))):
                chosen_input = self.user['current_buttons'][int_button_choice]
            else:
                chosen_input = ''
                self.print_settings('Invalid choice')
            chosen_input = chosen_input + '\n'
            self.say_text(prompt_text + chosen_input)
            self.check_input(chosen_input, show_parse)
            return chosen_input
        else:
            return ''

    def say_text(self, text, buttons=None, out=sys.stdout):
        """Handles 'saying' the output, with different approaches depending on the
        active channel (or channels) for output"""

        # Useful for unit tests
        sys.stdout = out
        BUTTON_LIMIT = 3

        # do this same manner for both output routes
        self.user['current_buttons'] = []
        if ((isinstance(buttons, list)) and (len(buttons) > 0)):
            if len(buttons) > BUTTON_LIMIT:
                self.logger.warn('No more than ' + str(BUTTON_LIMIT) +' buttons can be displayed (content may be missing)')
            # just allow first N buttons
            self.user['current_buttons'] = buttons[:BUTTON_LIMIT]
            self.logger.debug('User button choices: ' + str(self.user['current_buttons']))

        if self.CHANNELS_OUT['screen']:
            if (len(text) > 0) and (text[0] == '>'):
                print('\n\t\t' + u.STY_CURSOR + ' > ' + u.STY_USER + text[1:] + style.RESET)
            else:
                print('\n\t' + u.STY_RECIPIENT + '  User: ' + str(self.user_id) + '  ' + u.STY_USER + '\t' + u.STY_RESP + '  ' + text,
                    end='  ' + u.STY_USER + '\n\n')
            if ((isinstance(buttons, list)) and (len(buttons) > 0)):
                # just allow first N buttons
                print('\t\t',end='')
                for idx, button in zip(range(BUTTON_LIMIT), buttons):
                    print('\t[' + str(idx + 1) + '] ' + button, end='')
                print('\n')


    def handle_history(self, resp):
        """Handles History"""
        self.say_text('Handling History (in {language})'.format(language=self.get_user_language()))


    def handle_physics(self, resp):
        """Handles Physics"""
        self.say_text('Handling Physics (in {language})'.format(language=self.get_user_language()))


    def handle_biology(self, resp):
        """Handles Biology"""
        self.say_text('Handling Biology (in {language})'.format(language=self.get_user_language()))


    def handle_computing(self, resp):
        """Handles Computing"""
        self.say_text('Handling Computing (in {language})'.format(language=self.get_user_language()))


    def handle_low_confident(self):
        """Simple output indicating low confidence with the user input parsing"""
        low_confidence_list = [
        'Sorry, I am confused - it may be me, rather than you! :-(\nMaybe try stating your question in different words? (or even try another question?)',
        'Sorry, I\'m still learning and I don\'t think I understood you. :-(\nHow about repeating your question in different words? (or maybe try another question?)'
        ]
        self.say_text(self.pick(low_confidence_list))


    def handle_suitable_answer(self):
        """Simple output indicating cannot find suitable answer for user input"""
        suitable_answer_list = [
            'Sorry, I\'m having trouble coming up with a suitable answer.\nMaybe try stating your question in different words? (or even try another question?)',
            'I\'m not sure I follow your meaning.\nCould you try stating your question in different words? (or even try another question?)',
                    ]
        self.say_text(self.pick(suitable_answer_list))


    def handle_empty_input(self):
        """Simple output for empty input"""
        empty_response_list = ['I\'m unsure what to say to that! :/', 'I didn\'t quite catch that! :/', 'Excuse me? :/']
        self.logger.debug('Skipping empty input')
        self.say_text(self.pick(empty_response_list))


    def __init__(self, channels_out, channel_in = 'screen', loglvl = '', config_override = ''):
        """Initialises the core functionality and sets up various variables."""

        # TODO: add checks to confirm all necessary files are present and readable
        # (and writable if applicable)

        signal.signal(signal.SIGINT, self.handle_ctrl_c)

        self.logger = u.setup_custom_logger('root')

        if loglvl.lower().strip() == 'debug':
            self.logger.setLevel(logging.DEBUG)
            self.logger.info('Logging level set to DEBUG')
        elif loglvl.lower().strip() == 'info':
            self.logger.setLevel(logging.INFO)
            self.logger.info('Logging level set to INFO')
        elif loglvl.lower().strip() == 'warn':
            self.logger.setLevel(logging.WARN)
            self.logger.warn('Logging level set to WARN')
        elif loglvl.lower().strip() == '':
            self.logger.setLevel(logging.INFO)
        else:
            self.logger.warn('Unrecognised log level input. Defaulting to INFO.')
        
        self.logger.info('Initialisation started')

        channel_in_accepted = ['screen']
        if channel_in not in channel_in_accepted:
            self.logger.error('Unrecognised channel input value. Must be one of: ' + ', '.join(channel_in_accepted) + '.')
            self.before_quit()
        else:
            self.CHANNEL_IN = channel_in
            self.CHANNELS_OUT = channels_out
            self.CHANNELS_OUT[self.CHANNEL_IN] = True

        config = configparser.ConfigParser()
        
        if config_override.strip() != '':
            config_file = os.path.abspath(config_override.strip())
        else:
            config_file = os.path.abspath(os.path.join('config', 'mlb_config.ini'))
        
        try:
            dataset = config.read([config_file])
            if len(dataset) == 0:
                raise IOError

        except IOError as e:
            self.logger.error('Unable to open config file: ' + str(config_file))
            self.before_quit()
        except configparser.Error as e:
            self.logger.error('Error with config file: ' + str(config_file))
            self.before_quit()

        try:
            # bot items
            self.botname= config.get('bot', 'name')
            self.botsubject = config.get('bot', 'subject')
            # file items
            self.history_file = os.path.abspath(config.get('files', 'history_file'))
            self.pickle_file = os.path.abspath(config.get('files', 'pickle_file'))
        except configparser.Error as e:
            self.logger.error('Error reading configuration ' + str(e))
            self.before_quit()

        self.unpickle_user_dict()
        self.SESSION_TIME_LIMIT = 10 # Time in minutes to consider a subsequent interaction to be from a new session
        self.user_id = '1234'
        self.user = self.get_user(self.user_id)

        self.user['msg_output'] = ''
        self.user['rude_count'] = 0

        self.show_highlight = False
        self.show_parse = False
        self.user_stats = False
        self.show_language = True

        #self.langs_handled = {'en':'English'}
        #self.langs_handled = {'fr':'French'}
        self.langs_handled = {'en':'English', 'fr':'French'}
        #self.langs_handled = {'en':'English', 'fr':'French', 'de':'German'}

        self.lang_interpreters = {}

        # This is a more generic equivalent of:
        #   self.interpreter_de = Interpreter.load('projects/default/current_de', RasaNLUConfig('config/mlb_config_de.json'))

        for lang in self.langs_handled:
            try:
                self.logger.info('Configuring interpreter for {language}'.format(language=self.langs_handled[lang]))
                self.lang_interpreters[lang] = Interpreter.load('projects/default/current_{lang}'.format(lang=lang), RasaNLUConfig('config/mlb_config_{lang}.json'.format(lang=lang)))
            except:
                self.logger.error('Error with creating interpreter for {language} (lang: {lang})'.format(language=self.langs_handled[lang], lang=lang))
                self.logger.info('Maybe you need to train the model? Try equivalent of: python -m rasa_nlu.train -c config/mlb_config_XX.json')
                self.before_quit()

        self.last_input = {}

        self.print_user_stats(self.user_stats)

        self.logger.info('Initialisation complete')


    def check_input(self, u_input, show_parse=False):
        """Checks the user supplied input and passes it to the Rasa NLU model to
        get the intent and entities"""

        self.logger.debug('User input:  ' + u_input)
        u_input = u.clean_input(u_input)
        self.logger.debug('Clean input: ' + u_input)
        if len(u_input) == 0:
            self.handle_empty_input()
            return
        
        langs_det = detect_langs(u_input)
        if self.show_language:
            self.print_settings('\tLanguages detected: ' + str(langs_det))

        
        lang_selected = 'en'
        for l in langs_det:
            if l.lang in self.lang_interpreters:
                lang_selected = l.lang
                break

        self.user['lang_selected'] = lang_selected
        if self.show_language:
            self.print_settings('\tProcessing as {language}'.format(language=self.get_user_language()), invisible=True)
        else:
            self.print_settings('', invisible=True)
        # using invisible=True above as NUMPY currnetly causes this to spit out a pointless deprecation warning
        resp = self.lang_interpreters[lang_selected].parse(u_input)

        if show_parse:
            self.print_settings('\tParse output:\n\t\t' + str(resp))
        if self.show_highlight:
            self.print_settings('\n\t ' + u.STY_STAT_LABEL + resp['intent']['name'] + '\t' + u.STY_DESC + self.highlight(resp['text'], resp['entities']))
        self.last_input = resp
        if 'intent' in resp:

            if resp['intent']['confidence'] < 0.15:
                self.handle_low_confident()
                return

            if resp['intent']['name'] == u'history':
                self.handle_history(resp)
            elif resp['intent']['name'] == u'physics':
                self.handle_physics(resp)
            elif resp['intent']['name'] == u'biology':
                self.handle_biology(resp)
            elif resp['intent']['name'] == u'computing':
                self.handle_computing(resp)
            else:
                self.handle_suitable_answer()
        else:
            self.logger.info('Intent not found in response')


    def main_loop(self):
        """The main loop which repeats continuously until the programme is aborted
        or a crash occurs. It cycles round seeking input from which ever of the
        particular input modes the bot is configured to handle.
        It also handles low-level commands prior to passing input to Rasa NLU, such
        as toggling 'show parse' (s), changing logging level (d=DEBUG, i=INFO, 
        w=WARN) or quiting (q)"""
        if os.path.exists(self.history_file):
            readline.read_history_file(self.history_file)
        self.prompt_text = u.STY_CURSOR + ' > ' + u.STY_USER
        try:
            while True:
                self.user_input = input(self.prompt_text)
                print(style.RESET, end="")
                if self.interaction_controls(self.user_input) : continue
                self.update_user_stats()
                self.print_user_stats(self.user_stats)
                self.check_input(self.user_input, self.show_parse)
        finally:
            readline.write_history_file(self.history_file)


@click.command()
@click.option('--channel', default='screen', help='The input channel (screen). Default is screen.')
@click.option('--config', default='', help='The location of the config file.')
@click.option('--loglvl', default='', help='The level at which logging is done (DEBUG / INFO / WARN). Not case sensitive. Default level is INFO.')
def main(channel, config, loglvl):
    """MLB: a simple multi-lingual bot that can respond to questions on academic subjects"""
    ch_out = {'screen': True}
    c = Core(channels_out = ch_out, channel_in = channel, loglvl = loglvl, config_override = config)
    c.say_text('Hello!  \n\n\tI am configured to handle: ' + ', '.join([c.langs_handled[l] for l in c.lang_interpreters]))
    c.main_loop()


if __name__ == '__main__':
    main()
