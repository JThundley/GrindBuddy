#!/usr/bin/env python2.7
"This script runs all your logs through grindbuddy-cli to test things and watch for crashes. TTS stuff is printed instead of spoken."

###################### DOCUMENTATION #############################
#
###BUGS:

######################## IMPORTS ####################
import optparse
import spaceship
import grindbuddy_cli


##################### GLOBALS #######################
DEBUG = True
if DEBUG:
    from pprint import pprint

##################### FUNCTIONS #####################
# Actual functions:

##################### CLASSES #######################
class TextToSpeech():
    "A dummy class that prints all tts stuff"
    def speak(self, text, delay=0, nospam=0):
        "print text, ignore delay and nospam."
        print ' '.join(('TTS:', text))
##################### MAIN ##########################
if __name__ == '__main__':
    opts = optparse.OptionParser(usage="%prog [options]")
    opts.add_option('-c', '--configfile', action='store', dest='configfile', help='Specify the path to your config file')
    opts.add_option('-l', '--logdir', action='store', dest='logdir', help='Specify the path to your log folder')
    options = opts.parse_args()[0]

    config = grindbuddy_cli.getConfig(options.configfile)
    if not config.has_section("Global Settings"):
        createConfig()

    eventhandler = grindbuddy_cli.EventHandler(config, logdir=options.logdir, debug=True)
    eventhandler.spaceship.missions.purgeExpired()
    if eventhandler.tts:
        eventhandler.tts = TextToSpeech()
    eventhandler.spaceship.sessionstats['appstart'].startRecording()
    print "Running through logs..."

    events = eventhandler.spaceship.parseJournal(startup=True)
    for event in events: # process one event at a time so we don't load up spaceship with a ton of state information and then start over from the beginning running triggers.
        #print "journalentry is:", event
        eventhandler.spaceship.handleEvents([event]) # update your spaceship's internal state
        eventhandler.handleEvents([event]) # run event handlers here, in this live script
    print "Done!"
    eventhandler.handleEvents([{'event': '_EXIT'},])