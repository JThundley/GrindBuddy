#!/usr/bin/env python2.7
"This script runs while you play and gives you live information based on what you're doing in game."

###################### DOCUMENTATION #############################
#
###BUGS:

######################## IMPORTS ####################
import spaceship
import os, ConfigParser, optparse, datetime
from time import sleep
from threading import Thread, Lock
##################### GLOBALS #######################
DEBUG = True
if DEBUG:
    from pprint import pprint

##################### FUNCTIONS #####################
# Generators:

# Actual functions:
def getDefaultConfigPath():
    "return the default path for the config file on your platform."
    filename = 'grindbuddy.ini'
    try:
        configfiledir = os.path.join(os.environ['APPDATA'], 'grindbuddy')
    except KeyError: # we're not on Windows
        try:
            configfiledir = os.path.join(os.environ['HOME'], '.config')
        except KeyError: # we're not on Linux master race either
            raise Exception("Couldn't detect a default config directory to use!")
    return os.path.join(configfiledir, filename)

def createConfig(configfile=None):
    """
    Create a default config file.
    configfile is the location to the config file. If it's blank, the default is used.
    """
    config = BetterConfigParser()
    config.add_section("Global Settings")
    config.set("Global Settings", "Player Name", 'BlownUterus')
    config.set("Global Settings", "# Your timezone's offset from GMT (game time).")
    config.set("Global Settings", "Timezone Offset", -8)
    config.set("Global Settings", "# Allow speech to be used, set to False to disable all speaking.")
    config.set("Global Settings", "Speech", True)
    config.set("Global Settings", "# how often to check for new events (in seconds).")
    config.set("Global Settings", "Poll Interval", 1)
    
    config.add_section("Landing Pad Location")
    config.set("Landing Pad Location", "# Announce where your landing pad is located inside a large station.")
    config.set("Landing Pad Location", "Speech", True)
    config.set("Landing Pad Location", "text", True)
    config.set("Landing Pad Location", "# Set green on right to False if you're a britbonger. If this is true, then you should line up with the green light on your right when you enter a large station.")
    config.set("Landing Pad Location", "green on right", True)
    
    config.add_section("Money Gained Milestone")
    config.set("Money Gained Milestone", "# Announce when you've made certain amounts of money. This counts all money that you've ever made, spending doesn't take you further away from triggering this.")
    config.set("Money Gained Milestone", "announce every", [1000000000,])
    config.set("Money Gained Milestone", "speech", True)
    config.set("Money Gained Milestone", "text", True)
    
    config.add_section("Announce Physical Materials Full")
    config.set("Announce Physical Materials Full", "# Announce when you've filled up your physical materials (materials that aren't data).")
    config.set("Announce Physical Materials Full", "speech", True)
    config.set("Announce Physical Materials Full", "text", True)
    
    config.add_section("Announce Data Materials Full")
    config.set("Announce Data Materials Full", "# Announce when you've filled up your data materials.")
    config.set("Announce Data Materials Full", "speech", True)
    config.set("Announce Data Materials Full", "text", True)

    config.add_section("Announce Data Materials Optimum Number")
    config.set("Announce Data Materials Optimum Number", "# When you've filled up your data, this will tell you what the optimum number of individual materials are. This one only works if Announce Data Materials Full is also on.")
    config.set("Announce Data Materials Optimum Number", "# For example, if your amount of free space is 20, that means you want 480/500 data used.")
    config.set("Announce Data Materials Optimum Number", "# If this tells you that the optimum number is 23, then you go through your data and make sure you don't have more than 23 of any one material.")
    config.set("Announce Data Materials Optimum Number", "speech", True)
    config.set("Announce Data Materials Optimum Number", "text", True)
    config.set("Announce Data Materials Optimum Number", "free space", 20)

    config.add_section("Announce Physical Materials Optimum Number")
    config.set("Announce Physical Materials Optimum Number", "# When you've filled up your physical materials, this will tell you what the optimum number of individual materials are. This one only works if Announce Physical Materials Full is also on.")
    config.set("Announce Physical Materials Optimum Number", "# For example, if your amount of free space is 20, that means you want 480/500 data used.")
    config.set("Announce Physical Materials Optimum Number", "# If this tells you that the optimum number is 23, then you go through your data and make sure you don't have more than 23 of any one material.")
    config.set("Announce Physical Materials Optimum Number", "speech", True)
    config.set("Announce Physical Materials Optimum Number", "text", True)
    config.set("Announce Physical Materials Optimum Number", "free space", 50)

    config.add_section("Show Missions")
    config.set("Show Missions", "# Whenever your missions change, print useful information about them. No speech supported here. Set text to False to disable all of it.")
    config.set("Show Missions", "text", True)
    config.set("Show Missions", "speech", False)
    config.set("Show Missions", "# total header shows you the total amount of missions that you have.")
    config.set("Show Missions", "Total Header", True)
    config.set("Show Missions", "Current Missions By Destination Port", 'auto')
    config.set("Show Missions", "Current Missions By Reward", 'auto')
    config.set("Show Missions", "Current Missions By Expiration Time", 'auto')

    config.add_section("Count Target Kills")
    config.set("Count Target Kills", "# When you take a mission to kill X number of ships, this will count your progress.")
    config.set("Count Target Kills", "speech", True)
    config.set("Count Target Kills", "text", True)
    config.set("Count Target Kills", "# If total is true, also announce the total number of ships. False is 'you killed 14 ships', True is 'you killed 14 ships out of 18'.")
    config.set("Count Target Kills", "total", True)

    config.add_section("Announce Scoopable Star")
    config.set("Announce Scoopable Star", "# When you jump into a system, this will announce if the star is scoopable.")
    config.set("Announce Scoopable Star", "speech", True)
    config.set("Announce Scoopable Star", "text", True)

    config.add_section("Announce Unscoopable Star")
    config.set("Announce Unscoopable Star", "# When you jump into a system, this will announce if the star is NOT scoopable.")
    config.set("Announce Unscoopable Star", "speech", True)
    config.set("Announce Unscoopable Star", "text", True)

    config.add_section("Show End Of Session Stats")
    config.set("Show End Of Session Stats", "# Print out end of session statistics. No speech supported here.")
    config.set("Show End Of Session Stats", "text", True)
    config.set("Show End Of Session Stats", "speech", False)
    config.set("Show End Of Session Stats", "# The below stats all support True, False, and auto.")
    config.set("Show End Of Session Stats", "# True means always show the statistic.")
    config.set("Show End Of Session Stats", "# False means always hide it.")
    config.set("Show End Of Session Stats", "# auto means show it only if it's nonzero.")
    config.set("Show End Of Session Stats", "# Each statistic has a comment above it explaining what it's for.")
    config.set("Show End Of Session Stats", "#")
    config.set("Show End Of Session Stats", "# Show the commander name.")
    config.set("Show End Of Session Stats", "CMDR Name", "True")
    config.set("Show End Of Session Stats", "# Your current amount of money.")
    config.set("Show End Of Session Stats", "Current Balance", "True")
    config.set("Show End Of Session Stats", "# Show your current ranks in Combat, Trade, Exploration, Empire, Federation, and CQC.")
    config.set("Show End Of Session Stats", "Current Rank", "True")
    config.set("Show End Of Session Stats", "# Show what's currently in your cargo.")
    config.set("Show End Of Session Stats", "Current Cargo", "True")
    config.set("Show End Of Session Stats", "# Show your current physical materials (all materials except data.")
    config.set("Show End Of Session Stats", "Current Physical Materials", "True")
    config.set("Show End Of Session Stats", "# Show your current data materials.")
    config.set("Show End Of Session Stats", "Current Data Materials", "True")
    config.set("Show End Of Session Stats", "# Show the number of current missions that you have (whether they're ready to be turned in or not).")
    config.set("Show End Of Session Stats", "# If you turn this off, the below mission-related reporting will also be disabled.")
    config.set("Show End Of Session Stats", "Current Missions", "True")
    config.set("Show End Of Session Stats", "# Show Current missions sorted by destination port.")
    config.set("Show End Of Session Stats", "Current Missions By Destination Port", "True")
    config.set("Show End Of Session Stats", "# Show current missions sorted by reward, and the total that you stand to gain.")
    config.set("Show End Of Session Stats", "Current Missions By Reward", "True")
    config.set("Show End Of Session Stats", "# Show current missions sorted by expiration time.")
    config.set("Show End Of Session Stats", "current missions by expiration time", "True")
    config.set("Show End Of Session Stats", "# Show a list of current passengers. For each passenger mission you have, this will list out the number of passengers and the type: refugees, tourists, etc.")
    config.set("Show End Of Session Stats", "Current Passengers", "auto")
    config.set("Show End Of Session Stats", "# This shows when your session started, ended, and how long it was. auto is ignored for this one.")
    config.set("Show End Of Session Stats", "Session Time", "True")

    config.set("Show End Of Session Stats", "# How much your money changed overall. The total amount you made minus the total you spent.")
    config.set("Show End Of Session Stats", "Money Net Change", "auto")
    config.set("Show End Of Session Stats", "# Same as above, but per hour.")
    config.set("Show End Of Session Stats", "Money Net Change Per Hour", "auto")
    config.set("Show End Of Session Stats", "# This shows your money net change, but without modules and ships included.")
    config.set("Show End Of Session Stats", "Money Net Change Without Modules Or Ships", "auto")
    config.set("Show End Of Session Stats", "# Same as above, but per hour.")
    config.set("Show End Of Session Stats", "Money Net Change Without Modules Or Ships Per Hour", "auto")
    config.set("Show End Of Session Stats", "# Total money gained.")
    config.set("Show End Of Session Stats", "Total Money Gained", "auto")
    config.set("Show End Of Session Stats", "# Total money gained per hour.")
    config.set("Show End Of Session Stats", "Total Money Gained Per Hour", "auto")
    config.set("Show End Of Session Stats", "# Total money spent on all things.")
    config.set("Show End Of Session Stats", "Total Money Spent", "auto")
    config.set("Show End Of Session Stats", "# Total money spent on all things per hour.")
    config.set("Show End Of Session Stats", "Total Money Spent Per Hour", "auto")
    config.set("Show End Of Session Stats", "# Total money spent on all things except modules and ships.")
    config.set("Show End Of Session Stats", "Total Money Spent Without Modules Or Ships", "auto")
    config.set("Show End Of Session Stats", "# Total money spent on all things except modules and ships per hour.")
    config.set("Show End Of Session Stats", "Total Money Spent Without Modules Or Ships Per Hour", "auto")
    config.set("Show End Of Session Stats", "# How much money you've made from selling commodities.")
    config.set("Show End Of Session Stats", "Total Money Gained From Commodities Sold", "auto")
    config.set("Show End Of Session Stats", "# How many times you've declared bankruptcy.")
    config.set("Show End Of Session Stats", "Bankruptcy Declared", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've delivered for missions.")
    config.set("Show End Of Session Stats", "Cargo Delivered", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've delivered for engineers.")
    config.set("Show End Of Session Stats", "Cargo Delivered Engineer", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've delivered as a part of PowerPlay.")
    config.set("Show End Of Session Stats", "Cargo Delivered Powerplay", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've ejected.")
    config.set("Show End Of Session Stats", "Cargo Ejected", "auto")
    config.set("Show End Of Session Stats", "# How many units of commodities you've bought.")
    config.set("Show End Of Session Stats", "Cargo Gained Bought Commodity", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've gained as haulage from missions.")
    config.set("Show End Of Session Stats", "Cargo Gained Haulage", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've gained as rewards from completed missions.")
    config.set("Show End Of Session Stats", "Cargo Gained Mission Reward", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've gained from PowerPlay.")
    config.set("Show End Of Session Stats", "Cargo Gained Powerplay", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've gained by scooping it out of space or a planet surface.")
    config.set("Show End Of Session Stats", "Cargo Gained Scooped", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've lost because you died :(")
    config.set("Show End Of Session Stats", "Cargo Lost Death", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've sold to markets.")
    config.set("Show End Of Session Stats", "Cargo Sold", "auto")
    config.set("Show End Of Session Stats", "# How many drones/limpets you've sold to markets.")
    config.set("Show End Of Session Stats", "Cargo Sold Drones", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've sold to black markets.")
    config.set("Show End Of Session Stats", "Cargo Sold Illegal", "auto")
    config.set("Show End Of Session Stats", "# How many units of cargo you've \"sold\" to Search And Rescue.")
    config.set("Show End Of Session Stats", "Cargo Sold Search And Rescue", "auto")
    config.set("Show End Of Session Stats", "# How many times you've cleared deleted your character.")
    config.set("Show End Of Session Stats", "Cleared Saves", "auto")
    config.set("Show End Of Session Stats", "# How many times you've had your cockpit breached.")
    config.set("Show End Of Session Stats", "Cockpit Breaches", "auto")
    config.set("Show End Of Session Stats", "# How many Community Goals you've completed.")
    config.set("Show End Of Session Stats", "Community Goals Completed", "auto")
    config.set("Show End Of Session Stats", "# How many Community Goals you've discarded.")
    config.set("Show End Of Session Stats", "Community Goals Discarded", "auto")
    config.set("Show End Of Session Stats", "# How many Community Goals you've joined/accepted.")
    config.set("Show End Of Session Stats", "Community Goals Joined", "auto")
    config.set("Show End Of Session Stats", "# How many Community Goals you've done for scientific research. I'm not really sure about this one.")
    config.set("Show End Of Session Stats", "Community Goals Scientific Research", "auto")
    config.set("Show End Of Session Stats", "# How many times a multicrew session has been ended.")
    config.set("Show End Of Session Stats", "Crew Ended", "auto")
    config.set("Show End Of Session Stats", "# How many times a multicrew session ended because a crime was committed.")
    config.set("Show End Of Session Stats", "Crew Ended Crime", "auto")
    config.set("Show End Of Session Stats", "# How many times you've fired a crew member. I think this is only for NPC crewmembers.")
    config.set("Show End Of Session Stats", "Crew Fired", "auto")
    config.set("Show End Of Session Stats", "# How many times you've hired a crew member.")
    config.set("Show End Of Session Stats", "Crew Hired", "auto")
    config.set("Show End Of Session Stats", "# How many times you've kicked a crew member. I think this is only real players.")
    config.set("Show End Of Session Stats", "Crew Kicked", "auto")
    config.set("Show End Of Session Stats", "# How many times your crew members were kicked because they committed a crime.")
    config.set("Show End Of Session Stats", "Crew Kicked Crime", "auto")
    config.set("Show End Of Session Stats", "# How many times you've quit from a crew.")
    config.set("Show End Of Session Stats", "Crew Quit", "auto")
    config.set("Show End Of Session Stats", "# How many times you've joined a crew.")
    config.set("Show End Of Session Stats", "Crews Joined", "auto")
    config.set("Show End Of Session Stats", "# How many times you've died.")
    config.set("Show End Of Session Stats", "Deaths", "auto")
    config.set("Show End Of Session Stats", "# How many times you've cancelled a docking request.")
    config.set("Show End Of Session Stats", "Docking Cancelled", "auto")
    config.set("Show End Of Session Stats", "# How many times you've been denied a docking request.")
    config.set("Show End Of Session Stats", "Docking Denied", "auto")
    config.set("Show End Of Session Stats", "# How many times your docking requests have been granted.")
    config.set("Show End Of Session Stats", "Docking Granted", "auto")
    config.set("Show End Of Session Stats", "# How many times you've requested docking permissions.")
    config.set("Show End Of Session Stats", "Docking Requested", "auto")
    config.set("Show End Of Session Stats", "# How many times your docking request has timed out. I think you have 5 minutes to dock before it times out.")
    config.set("Show End Of Session Stats", "Docking Timeout", "auto")
    config.set("Show End Of Session Stats", "# How many times you've undocked from a landing pad.")
    config.set("Show End Of Session Stats", "Docking Undocked", "auto")
    config.set("Show End Of Session Stats", "# How much money in bounties you've given to an engineer.")
    config.set("Show End Of Session Stats", "Engineer Bounty Spent", "auto")
    config.set("Show End Of Session Stats", "# How many different modifications you've applied from engineers.")
    config.set("Show End Of Session Stats", "Engineer Modifications Applied", "auto")
    config.set("Show End Of Session Stats", "# How many Engineers you've been invited to visit.")
    config.set("Show End Of Session Stats", "Engineers Invited", "auto")
    config.set("Show End Of Session Stats", "# How many engineers you've discovered.")
    config.set("Show End Of Session Stats", "Engineers Known", "auto")
    config.set("Show End Of Session Stats", "# How many ranks you've gained from all engineers combined.")
    config.set("Show End Of Session Stats", "Engineers Rank Gained", "auto")
    config.set("Show End Of Session Stats", "# How many engineers you've unlocked, or how many will allow you to use them.")
    config.set("Show End Of Session Stats", "Engineers Unlocked", "auto")
    config.set("Show End Of Session Stats", "# How many times a fighter has docked in your ship.")
    config.set("Show End Of Session Stats", "Fighter Docked", "auto")
    config.set("Show End Of Session Stats", "# How many times an NPC has launched a fighter out of your ship.")
    config.set("Show End Of Session Stats", "Fighter Launched NPC", "auto")
    config.set("Show End Of Session Stats", "# How many times you've launched in a fighter out of someone else's ship AND how many times a player has launched a fighter out of your ship.")
    config.set("Show End Of Session Stats", "Fighter Launched Player", "auto")
    config.set("Show End Of Session Stats", "# How many times you've been fined, not the amount of money.")
    config.set("Show End Of Session Stats", "Fines Gained", "auto")
    config.set("Show End Of Session Stats", "# How many times you've paid a legacy fine.")
    config.set("Show End Of Session Stats", "Fines Legacy Paid", "auto")
    config.set("Show End Of Session Stats", "# How many times you've started an FSD jump to enter supercruise or hyperspace. This is still counted if you cancel your FSD.")
    config.set("Show End Of Session Stats", "FSD Jump Started", "auto")
    config.set("Show End Of Session Stats", "# The amount of fuel you've bought.")
    config.set("Show End Of Session Stats", "Fuel Bought", "auto")
    config.set("Show End Of Session Stats", "# How many times you've started fuel scooping.")
    config.set("Show End Of Session Stats", "Fuel Scoop Started", "auto")
    config.set("Show End Of Session Stats", "# The amount of fuel you've scooped.")
    config.set("Show End Of Session Stats", "Fuel Scooped", "auto")
    config.set("Show End Of Session Stats", "# How many times you've loaded a game from the menu.")
    config.set("Show End Of Session Stats", "Games Loaded", "True") # this is always at least 1
    config.set("Show End Of Session Stats", "# The total amount of cargo you've gained from any method.")
    config.set("Show End Of Session Stats", "Total Cargo Gained", "auto") # getTotalCargoGained
    config.set("Show End Of Session Stats", "# The total amount of cargo you've sold to both regular and black markets.")
    config.set("Show End Of Session Stats", "Total Cargo Sold", "auto") # getTotalCargoSold
    config.set("Show End Of Session Stats", "# The total amount of money from selling commodities compared to the galactic average.")
    config.set("Show End Of Session Stats", "# If this number is negative, you took a loss when you sold your commodities. You sold for less than the galactic average.")
    config.set("Show End Of Session Stats", "# This number is only counted when you sell a commodity that was bought. It's not counted for commodities you receive by completing missions.")
    config.set("Show End Of Session Stats", "Total Galactic Average Sales", "auto") # getTotalGalacticAverageSales
    config.set("Show End Of Session Stats", "# How many times you've taken heat damage.")
    config.set("Show End Of Session Stats", "Heat Damage Taken", "auto")
    config.set("Show End Of Session Stats", "# How many times you've had a heat warning.")
    config.set("Show End Of Session Stats", "Heat Warnings", "auto")
    config.set("Show End Of Session Stats", "# How many times you've taken a 5th of hull damage.")
    config.set("Show End Of Session Stats", "Hull Damage Taken Fifths Fuzzy", "False") # useless stat?
    config.set("Show End Of Session Stats", "# How many times you've committed an interdiction to an NPC and they evaded you.")
    config.set("Show End Of Session Stats", "Interdictions Committed Fail NPC", "auto")
    config.set("Show End Of Session Stats", "# How many times you've committed an interdiction to a player and they evaded you.")
    config.set("Show End Of Session Stats", "Interdictions Committed Fail Player", "auto")
    config.set("Show End Of Session Stats", "# How many times you've committed an interdiction to an NPC and you succeeded.")
    config.set("Show End Of Session Stats", "Interdictions Committed Success NPC", "auto")
    config.set("Show End Of Session Stats", "# How many times you've committed an interdiction to a player and you succeeded.")
    config.set("Show End Of Session Stats", "Interdictions Committed Success Player", "auto")
    config.set("Show End Of Session Stats", "# How many times you've escaped from an NPC's interdictions.")
    config.set("Show End Of Session Stats", "Interdictions Escaped NPC", "auto")
    config.set("Show End Of Session Stats", "# How many times you've escaped from a player's interdictions.")
    config.set("Show End Of Session Stats", "Interdictions Escaped Player", "auto")
    config.set("Show End Of Session Stats", "# How many times you've failed to escape from an NPC's interdiction.")
    config.set("Show End Of Session Stats", "Interdictions Escapes Failed NPC", "auto")
    config.set("Show End Of Session Stats", "# How many times you've failed to escape from a player's interdiction.")
    config.set("Show End Of Session Stats", "Interdictions Escapes Failed Player", "auto")
    config.set("Show End Of Session Stats", "# How many times you've submitted to an NPC's interdiction.")
    config.set("Show End Of Session Stats", "Interdictions Submitted NPC", "auto")
    config.set("Show End Of Session Stats", "# How many times you've submitted to a player's interdiction.")
    config.set("Show End Of Session Stats", "Interdictions Submitted Player", "auto")
    config.set("Show End Of Session Stats", "# How many times you've gotten a bounty claim from killing a ship. This is not the amount of money.")
    config.set("Show End Of Session Stats", "Kills Bounty", "auto")
    config.set("Show End Of Session Stats", "# How many times you've killed a capital ship.")
    config.set("Show End Of Session Stats", "Kills Capitalship", "auto")
    config.set("Show End Of Session Stats", "# How many kills you've earned in a combat zone when fighting on one side.")
    config.set("Show End Of Session Stats", "Kills Faction Bond", "auto")
    config.set("Show End Of Session Stats", "# How many other players you've killed.")
    config.set("Show End Of Session Stats", "Kills PVP", "auto")
    config.set("Show End Of Session Stats", "# How many data materials you've discarded.")
    config.set("Show End Of Session Stats", "Materials Data Discarded", "auto")
    config.set("Show End Of Session Stats", "# How many data materials you've gained.")
    config.set("Show End Of Session Stats", "Materials Data Gained", "auto")
    config.set("Show End Of Session Stats", "# How many data materials you've spent on engineering.")
    config.set("Show End Of Session Stats", "Materials Data Spent Engineer", "auto")
    config.set("Show End Of Session Stats", "# How many new materials you've discovered. I think this only counts physical materials.")
    config.set("Show End Of Session Stats", "Materials Discovered", "auto")
    config.set("Show End Of Session Stats", "# How many physical (anything but data) materials you've discarded.")
    config.set("Show End Of Session Stats", "Materials Physical Discarded", "auto")
    config.set("Show End Of Session Stats", "# How many physical materials you've gained.")
    config.set("Show End Of Session Stats", "Materials Physical Gained", "auto")
    config.set("Show End Of Session Stats", "# How many physical materials you've spent on engineering.")
    config.set("Show End Of Session Stats", "Materials Physical Spent Engineer", "auto")
    config.set("Show End Of Session Stats", "# How many physical materials you've spent on synthesis.")
    config.set("Show End Of Session Stats", "Materials Physical Spent Synthesis", "auto")
    config.set("Show End Of Session Stats", "# How many messages you've received on the local channel.")
    config.set("Show End Of Session Stats", "Messages Received Local", "False") # useless stat?
    config.set("Show End Of Session Stats", "# How many messages you've received from NPCs.")
    config.set("Show End Of Session Stats", "Messages Received NPC", "False") # useless?
    config.set("Show End Of Session Stats", "# How many messages you've received from other players.")
    config.set("Show End Of Session Stats", "Messages Received Player", "False") # useless?
    config.set("Show End Of Session Stats", "# How many messages you've received in the voice chat channel.")
    config.set("Show End Of Session Stats", "Messages Received Voicechat", "False") # useless.
    config.set("Show End Of Session Stats", "# How many messages you've received from wingmates when in a wing.")
    config.set("Show End Of Session Stats", "Messages Received Wing", "False") # useless?
    config.set("Show End Of Session Stats", "# How many messages you've sent.")
    config.set("Show End Of Session Stats", "Messages Sent", "False")
    config.set("Show End Of Session Stats", "# How many missions you've abandoned.")
    config.set("Show End Of Session Stats", "Missions Abandoned", "auto")
    config.set("Show End Of Session Stats", "# How many missions you've accepted.")
    config.set("Show End Of Session Stats", "Missions Accepted", "auto")
    config.set("Show End Of Session Stats", "# How many missions you've completed.")
    config.set("Show End Of Session Stats", "Missions Completed", "auto")
    config.set("Show End Of Session Stats", "# How many missions you've failed.")
    config.set("Show End Of Session Stats", "Missions Failed", "auto")
    config.set("Show End Of Session Stats", "# How many passengers you've delivered from missions. The number of individuals, not trips.")
    config.set("Show End Of Session Stats", "Missions Passengers Delivered", "auto")
    config.set("Show End Of Session Stats", "# How many passengers you've failed to deliver as a part of missions.")
    config.set("Show End Of Session Stats", "Missions Passengers Failed", "auto")
    config.set("Show End Of Session Stats", "# How many times you've had a mission redirected to a different station.")
    config.set("Show End Of Session Stats", "Missions Redirected", "auto")
    config.set("Show End Of Session Stats", "# How many times you've bought a module.")
    config.set("Show End Of Session Stats", "Modules Bought", "auto")
    config.set("Show End Of Session Stats", "# How many times you've taken a module out of storage, not necessarily that you've paid to move it.")
    config.set("Show End Of Session Stats", "Modules Retrieved", "auto")
    config.set("Show End Of Session Stats", "# How many times you've sold a module.")
    config.set("Show End Of Session Stats", "Modules Sold", "auto")
    config.set("Show End Of Session Stats", "# How many times you've sold a module that was in storage at another station.")
    config.set("Show End Of Session Stats", "Modules Sold Remote", "auto")
    config.set("Show End Of Session Stats", "# How many times you've swapped modules.")
    config.set("Show End Of Session Stats", "Modules Swapped", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from selling things to black markets.")
    config.set("Show End Of Session Stats", "Money Gained Blackmarket", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from turning in bounties.")
    config.set("Show End Of Session Stats", "Money Gained Bounty", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from participating in community goals.")
    config.set("Show End Of Session Stats", "Money Gained Communitygoal", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from selling exploration data.")
    config.set("Show End Of Session Stats", "Money Gained Exploration", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from bonuses when exploring. Bonuses are awarded for being the first person to discover a place.")
    config.set("Show End Of Session Stats", "Money Gained Exploration Bonus", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained selling stuff to regular markets (not black markets).")
    config.set("Show End Of Session Stats", "Money Gained Market", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from completing missions.")
    config.set("Show End Of Session Stats", "Money Gained Missions", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from your Powerplay salary.")
    config.set("Show End Of Session Stats", "Money Gained Powerplaysalary", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from selling stuff to Search And Rescue.")
    config.set("Show End Of Session Stats", "Money Gained Search And Rescue", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from selling drones/limpets.")
    config.set("Show End Of Session Stats", "Money Gained SellDrones", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from selling modules.")
    config.set("Show End Of Session Stats", "Money Gained SellModules", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from selling ships.")
    config.set("Show End Of Session Stats", "Money Gained ShipSell", "auto")
    config.set("Show End Of Session Stats", "# How much money you've gained from unknown methods. I think I have this narrowed down to glitches in the game now.")
    config.set("Show End Of Session Stats", "# This program tracks all the money you make. When you load a game, the game tells you how much money you currently have.")
    config.set("Show End Of Session Stats", "# Sometimes, this number is more than what this program calculates you should have. This number is added to unknown money.")
    config.set("Show End Of Session Stats", "# If you find that you made unknown money during a play session, please tell me when it happened and send me your logs!")
    config.set("Show End Of Session Stats", "Money Gained Unknown", "auto")
    config.set("Show End Of Session Stats", "# How much money you've made from selling commodities over the galactic average. This amount is the difference.")
    config.set("Show End Of Session Stats", "# For example, if you sell a commodity for $10 and the galactic average is $15, then this amount is $5.")
    config.set("Show End Of Session Stats", "Money Over Market Galactic Average", "auto")
    config.set("Show End Of Session Stats", "# The same, but under the galactic average.")
    config.set("Show End Of Session Stats", "Money Under Market Galactic Average", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on ammunition.")
    config.set("Show End Of Session Stats", "Money Spent Ammo", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent purchasing new ships.")
    config.set("Show End Of Session Stats", "Money Spent BuyShip", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent buying commodities from markets.")
    config.set("Show End Of Session Stats", "Money Spent Commodities", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent hiring crew members.")
    config.set("Show End Of Session Stats", "Money Spent CrewHire", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on drones/limpets.")
    config.set("Show End Of Session Stats", "Money Spent Drones", "auto")
    config.set("Show End Of Session Stats", "# How much money you've donated to engineers.")
    config.set("Show End Of Session Stats", "Money Spent Engineer Contribution", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on exploration data.")
    config.set("Show End Of Session Stats", "Money Spent ExplorationData", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on moving your modules from one station to another.")
    config.set("Show End Of Session Stats", "Money Spent FetchRemoteModule", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on fines.")
    config.set("Show End Of Session Stats", "Money Spent Fines", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on fuel.")
    config.set("Show End Of Session Stats", "Money Spent Fuel", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on legacy fines.")
    config.set("Show End Of Session Stats", "Money Spent LegacyFines", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent donating to factions as a mission.")
    config.set("Show End Of Session Stats", "Money Spent Mission Donations", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on modules.")
    config.set("Show End Of Session Stats", "Money Spent ModuleBuy", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent retrieving modules from storage. The game hasn't ever charged for this.")
    config.set("Show End Of Session Stats", "Money Spent ModuleRetrieve", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent putting modules into storage. The game hasn't ever charged for this either.")
    config.set("Show End Of Session Stats", "Money Spent ModuleStore", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on PowerPlay fast track.")
    config.set("Show End Of Session Stats", "Money Spent PowerPlayFastTrack", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent rebuying your ship after a death.")
    config.set("Show End Of Session Stats", "Money SPent RebuyShip", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on repairs to your ship.")
    config.set("Show End Of Session Stats", "Money Spent Repairs", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent buying a new SRV or fighter after it's been destroyed.")
    config.set("Show End Of Session Stats", "Money Spent RestockVehicle", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent on trade data.")
    config.set("Show End Of Session Stats", "Money Spent TradeData", "auto")
    config.set("Show End Of Session Stats", "# How much money you've spent to have your ship transferred between stations.")
    config.set("Show End Of Session Stats", "Money Spent TransferShip", "auto")
    config.set("Show End Of Session Stats", "# How many times the music has changed.") # useless
    config.set("Show End Of Session Stats", "Music Changed", "False")
    config.set("Show End Of Session Stats", "# How many times you've scanned a navigation beacon.")
    config.set("Show End Of Session Stats", "Nav Beacons Scanned", "auto")
    config.set("Show End Of Session Stats", "# How many times you've damaged your ship from doing a neutron star boost.")
    config.set("Show End Of Session Stats", "Neutron Boost Damages", "auto")
    config.set("Show End Of Session Stats", "# How many times you've gotten a neutron star boost.")
    config.set("Show End Of Session Stats", "Neutron Boosts", "auto")
    config.set("Show End Of Session Stats", "# How much boost you've received from neutron star boosts.")
    config.set("Show End Of Session Stats", "Neutron Boosts Value", "auto") # useless?
    config.set("Show End Of Session Stats", "# How many times you've created a new commander/game.")
    config.set("Show End Of Session Stats", "New Commander Created", "auto")
    config.set("Show End Of Session Stats", "# How many times you've landed on a planet.")
    config.set("Show End Of Session Stats", "Planet Landings", "auto")
    config.set("Show End Of Session Stats", "# How many times you've dismissed your ship, whether it has an NPC pilot or it's unmanned.")
    config.set("Show End Of Session Stats", "Planet Liftoff NPC", "auto")
    config.set("Show End Of Session Stats", "# How many times you've lifted off from a planet surface.")
    config.set("Show End Of Session Stats", "Planet Liftoff Player", "auto")
    config.set("Show End Of Session Stats", "# How many times you've defected from a PowerPlay power.")
    config.set("Show End Of Session Stats", "Powerplay Defect", "auto")
    config.set("Show End Of Session Stats", "# How many times you've joined a PowerPlay power.")
    config.set("Show End Of Session Stats", "Powerplay Join", "auto")
    config.set("Show End Of Session Stats", "# How many times you've left a PowerPlay power.")
    config.set("Show End Of Session Stats", "Powerplay Leave", "auto")
    config.set("Show End Of Session Stats", "# How many times you've collected a PowerPlay salary.")
    config.set("Show End Of Session Stats", "Powerplay Salaries Redeemed", "auto")
    config.set("Show End Of Session Stats", "# How many times you've voted in PowerPlay.")
    config.set("Show End Of Session Stats", "Powerplay Vote", "auto")
    config.set("Show End Of Session Stats", "# How many votes have been casted in powerplay. It's possible that you have more than 1 vote to cast per turn.")
    config.set("Show End Of Session Stats", "Powerplay Votes Casted", "auto")
    config.set("Show End Of Session Stats", "# How many PowerPlay vouchers have been redeemed. I'm not too sure about this one.")
    config.set("Show End Of Session Stats", "Powerplay Vouchers", "auto")
    config.set("Show End Of Session Stats", "# How many combat ranks you've gained this session.")
    config.set("Show End Of Session Stats", "Rank Gained Combat", "auto")
    config.set("Show End Of Session Stats", "# How many Close Quarter Combat ranks you've gained this session.")
    config.set("Show End Of Session Stats", "Rank Gained CQC", "auto")
    config.set("Show End Of Session Stats", "# How many Empire ranks you've gained this session.")
    config.set("Show End Of Session Stats", "Rank Gained Empire", "auto")
    config.set("Show End Of Session Stats", "# How much exploration rank you've gained this session.")
    config.set("Show End Of Session Stats", "Rank Gained Explore", "auto")
    config.set("Show End Of Session Stats", "# How much Federation rank you've gained this session.")
    config.set("Show End Of Session Stats", "Rank Gained Federation", "auto")
    config.set("Show End Of Session Stats", "# How much trade rank you've gained this session.")
    config.set("Show End Of Session Stats", "Rank Gained Trade", "auto")
    config.set("Show End Of Session Stats", "# How many times you've rebooted your ship to repair it.")
    config.set("Show End Of Session Stats", "Reboot Repairs", "auto")
    config.set("Show End Of Session Stats", "# How many data points you've scanned.")
    config.set("Show End Of Session Stats", "Scanned Data Points", "auto")
    config.set("Show End Of Session Stats", "# How many data links you've scanned.")
    config.set("Show End Of Session Stats", "Scanned Datalinks", "auto")
    config.set("Show End Of Session Stats", "# How many times another ship has scanned you looking for cargo.")
    config.set("Show End Of Session Stats", "Scanned For Cargo", "auto")
    config.set("Show End Of Session Stats", "# How many times another ship has scanned you looking for crimes.")
    config.set("Show End Of Session Stats", "Scanned For Crime", "auto")
    config.set("Show End Of Session Stats", "# How many times you've scanned tourist beacons.")
    config.set("Show End Of Session Stats", "Scanned Tourist Beacons", "auto")
    config.set("Show End Of Session Stats", "# How many screenshots you've taken.")
    config.set("Show End Of Session Stats", "Screenshots Taken", "auto")
    config.set("Show End Of Session Stats", "# How many times you've self-destructed.")
    config.set("Show End Of Session Stats", "Self Destructed", "auto")
    config.set("Show End Of Session Stats", "# How many times your shields have been depleted. This isn't counted when you drop your own shields by turning them off, running out of power, silent running, etc.")
    config.set("Show End Of Session Stats", "Shields Depleted", "auto")
    config.set("Show End Of Session Stats", "# How many times your shields have been regained. This *IS* counted after you recover shields from silent running.")
    config.set("Show End Of Session Stats", "Shields Regained", "auto")
    config.set("Show End Of Session Stats", "# How many times you've set your ship's name.")
    config.set("Show End Of Session Stats", "Ship Name Set", "auto")
    config.set("Show End Of Session Stats", "# How many times you've bought a ship.")
    config.set("Show End Of Session Stats", "Ships Bought", "auto")
    config.set("Show End Of Session Stats", "# How many times you've sold a ship.")
    config.set("Show End Of Session Stats", "Ships Sold", "auto")
    config.set("Show End Of Session Stats", "# How many times you've swapped from one ship to another inside a station.")
    config.set("Show End Of Session Stats", "Ships Swapped", "auto")
    config.set("Show End Of Session Stats", "# How many times you've transferred your ship from one place to another.")
    config.set("Show End Of Session Stats", "Ships Transferred", "auto")
    config.set("Show End Of Session Stats", "# How many times you've docked your SRV into your ship.")
    config.set("Show End Of Session Stats", "SRV Docked", "auto")
    config.set("Show End Of Session Stats", "# How many times an NPC has launched an SRV from your ship. The game never actually implemented this either.")
    config.set("Show End Of Session Stats", "SRV Launched NPC", "auto")
    config.set("Show End Of Session Stats", "# How many times you or another player has launched an SRV from your ship.")
    config.set("Show End Of Session Stats", "SRV Launched Player", "auto")
    config.set("Show End Of Session Stats", "# How many times you've scanned a stellar object.")
    config.set("Show End Of Session Stats", "Stellar Object Scanned", "auto")
    config.set("Show End Of Session Stats", "# How many times you've entered supercruise from normal space.")
    config.set("Show End Of Session Stats", "Supercruise Entered", "auto")
    config.set("Show End Of Session Stats", "# How many times you've exited supercruise. Hyperspace to another system is considered a supercruise exit.")
    config.set("Show End Of Session Stats", "Supercruise Exited", "auto")
    config.set("Show End Of Session Stats", "# How many times you've synthesized something.")
    config.set("Show End Of Session Stats", "Synthesized Something", "auto")
    config.set("Show End Of Session Stats", "# How many times you've dropped into an Unknown Signal Source.")
    config.set("Show End Of Session Stats", "USS Drops", "auto")
    config.set("Show End Of Session Stats", "# How many vouchers you've received from scanning data links.")
    config.set("Show End Of Session Stats", "Voucher Count Datalink", "auto")
    config.set("Show End Of Session Stats", "# How much money you've received from turning in vouchers from scanning data links.")
    config.set("Show End Of Session Stats", "Voucher Money Datalink", "auto")
    config.set("Show End Of Session Stats", "# How many vouchers you've redeemed from killing wanted people.")
    config.set("Show End Of Session Stats", "Vouchers Redeemed Bounty", "auto")
    config.set("Show End Of Session Stats", "# How many Vouchers you've redeemed from killing people in a conflict zone.")
    config.set("Show End Of Session Stats", "Vouchers Redeemed CombatBond", "auto")
    config.set("Show End Of Session Stats", "# How many vouchers you've redeemed for scannable things.")
    config.set("Show End Of Session Stats", "Vouchers Redeemed Scannable", "auto")
    config.set("Show End Of Session Stats", "# How many vouchers you've received for settlements? I have no clue what this is. Please email me if you do.")
    config.set("Show End Of Session Stats", "Vouchers Redeemed Settlement", "auto")
    config.set("Show End Of Session Stats", "# How many trade vouchers you've redeemed.")
    config.set("Show End Of Session Stats", "Vouchers Redeemed Trade", "auto")
    config.set("Show End Of Session Stats", "# How many wing invites you've sent.")
    config.set("Show End Of Session Stats", "Wing Invites Sent", "auto")
    config.set("Show End Of Session Stats", "# How many wings you've joined.")
    config.set("Show End Of Session Stats", "Wings Joined", "auto")
    config.set("Show End Of Session Stats", "# How many wings you've left.")
    config.set("Show End Of Session Stats", "Wings Left", "auto")

    config.set("Show End Of Session Stats", "# Show the most visited systems this session.")
    config.set("Show End Of Session Stats", "Top Systems Visited", "auto")
    config.set("Show End Of Session Stats", "# This is the amount of systems to show, must be a number.")
    config.set("Show End Of Session Stats", "Number of Systems Visited", "5")
    config.set("Show End Of Session Stats", "# Show the most visited stations this session.")
    config.set("Show End Of Session Stats", "Top Stations Visited", "auto")
    config.set("Show End Of Session Stats", "# This is the amount of stations to show, must be a number.")
    config.set("Show End Of Session Stats", "Number of Stations Visited", "5")
    config.set("Show End Of Session Stats", "# Show the top mined elements this session.")
    config.set("Show End Of Session Stats", "Top Elements Mined", "auto")
    config.set("Show End Of Session Stats", "# This is the amount of different elements to show, must be a number.")
    config.set("Show End Of Session Stats", "Number of Elements Mined", "5")

    if not configfile:
        configfile = getDefaultConfigPath()
    configfiledir = os.path.split(configfile)[0]

    try:
        os.makedirs(configfiledir)
    except WindowsError, e:
        if e[0] == 183: # Cannot create a file when that file already exists
            pass
        else:
            raise
    with open(configfile, 'w') as config_file:
        config.write(config_file)
    print "Wrote a default config file to %s" % configfile
    print "You must edit this config file before continuing."
    if DEBUG:
        os.startfile(configfile)
    raise SystemExit

def getConfig(path=None):
    "Read the config file. path is the the full path to the file. A default is used if it's left blank. return the config object."
    if not path:
        path = getDefaultConfigPath()
    config = BetterConfigParser()
    config.read(path)
    return config

def printAlignedText(textlist):
    """This function prints out neat little aligned coumns of text. textlist is a list of tuples. Each tuple is exactly 2 items long.
    The first item in the tuple is the text on the left to be measured. The second item is the text to align to the right of it. For example:
    printAlignedText([('lasers:', '4'), ('multicannons:', '5')] ->
    lasers:       4
    multicannons: 5
    This function prints the new string of the text and returns nothing. A colon and one space is automatically added to the left word.
    Each tuple MUST contain strings, ints will not be converted
    """
    # First find out what the longest word is:
    try:
        longest_left_word = max([len(x[0]) for x in textlist])
    except ValueError: # raised from trying to max([])
        return
    # Now go through and print everything with the right amount of padding after it:
    for pair in textlist:
        if pair[0]:  # only print a colon if there was something on the left. Sometimes it's blank for getScorePerHour
            colon = ':'
        else:
            colon = ' '
        print "\t%s%s %s%s" % (pair[0], colon, ' '*(longest_left_word-len(pair[0])), pair[1])

def getOptimumAmountOfMaterials(materials, freespace):
    """This function is for computing the optimum amount of materials to have so that you have freespace amount of free space.
    materials is the dict of the material, physical or data
    freespace is an int of the amount of free space you want to make
    the optimum number of materials to have is returned as an int
    """
    newmaterials = materials.values()
    try:
        newmaterials[0]['Count']
    except TypeError: # this means we're working on data
        pass # newmaterials is already a list of amounts
    else: # this means we're working on physical materials
        newmaterials = [x['Count'] for x in newmaterials] # further refine newmaterials into a list of just the amount
    newmaterials.sort()
    space_made = 0
    while space_made < freespace:
        # discard one from the material of which you have the highest amount:
        newmaterials[-1] -= 1
        space_made += 1
        newmaterials.sort()
    return newmaterials[-1] # return the highest number

##################### CLASSES #######################
class BetterConfigParser(ConfigParser.ConfigParser, object):
    "overload write so we can make some decent looking comments for fuck's sake. And have easy to get defaults, fuck me. AND to implement getlist, shit boy. And to add auto as a true boolean state."
    #def __init__(self):
    #    ConfigParser.ConfigParser.__init__(self)
    #    self._boolean_states['auto'] = True
    def write(self, fp):
        """Write an .ini-format representation of the configuration state."""
        if self._defaults:
            fp.write("[%s]\n" % DEFAULTSECT)
            for (key, value) in self._defaults.items():
                if key.startswith('#'):
                    fp.write(key)
                else:
                    fp.write("%s = %s\n" % (key, str(value).replace('\n', '\n\t')))
            fp.write("\n")
        for section in self._sections:
            fp.write("[%s]\n" % section)
            for (key, value) in self._sections[section].items():
                if key == "__name__":
                    continue
                if (value is not None) or (self._optcre == self.OPTCRE):
                    if not key.startswith('#'):
                        key = " = ".join((key, str(value).replace('\n', '\n\t')))
                fp.write("%s\n" % (key))
            fp.write("\n")
    def get(self, section, option, default='_NoDefault'):
        try:
            return super(BetterConfigParser, self).get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            if default == '_NoDefault':
                raise e
            return default
    def getint(self, section, option, default='_NoDefault'):
        try:
            return super(BetterConfigParser, self).getint(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            if default == '_NoDefault':
                raise e
            return default
    def getboolean(self, section, option, default='_NoDefault'):
        v = self.get(section, option, default=default)
        if v.lower() not in self._boolean_states:
            raise ValueError, 'Not a boolean: %s' % v
        return self._boolean_states[v.lower()]
    def getintlist(self, section, option, default='_NoDefault'):
        "transform an option from a str into a list of ints"
        v = self.get(section, option, default=default)
        thelist = []
        currentnumber = [] # list of chars to later be converted to int
        for c in v:
            if c in '[ ':
                continue
            elif c in ',]':
                thelist.append(int(''.join(currentnumber)))
                currentnumber = []
            else:
                currentnumber.append(c)
        return thelist
    def getbooleanauto(self, section, option, value, default='_NoDefault'):
        # This will get a boolean, but also accept auto. If auto is set, then value is checked to see if it's nonzero/nonempty
        v = self.get(section, option, default=default)
        if v.lower() not in self._boolean_states:
            if v.lower() == 'auto':
                if value:
                    return True
                else:
                    return False
            raise ValueError, 'Not a boolean: %s' % v
        return self._boolean_states[v.lower()]

class AntiSpam(Thread):
    "This object is to be run in a thread by TextToSppech(). It waits a number of seconds and then removes its phrase from speechspam."
    def __init__(self, speechspam, nospam, lockobj, text):
        """speechspam is the speechspam set from TextToSpeech()
        nospam is the number of seconds to sleep for before removing the text
        lockobj is the lock object from TextToSpeech, to make sure we don't have 2 threads trying to add or remove things at the same time.
        text is the phrase that needs to be removed
        """
        self.speechspam = speechspam
        self.nospam = nospam
        self.lockobj = lockobj
        self.text = text
        Thread.__init__(self)
    def run(self):
        sleep(self.nospam)
        with self.lockobj:
            self.speechspam.discard(self.text)

class TextToSpeech():
    "A class that sets up text to speech and then provides a single method to speak it"
    def __init__(self):
        try:  # importing Windows tts
            import win32com.client as wincl
        except ImportError:
            raise Exception("Unable to initialize Windows text to speech!")
        else:
            speechdispatcher = wincl.Dispatch("SAPI.SpVoice")
            self.speakmeth = speechdispatcher.Speak
            self.speechspam = set() # we'll prevent text to speech by putting anything with a nospam argument into this set.
            self.lock = Lock()
    def speak(self, text, delay=0, nospam=0):
        "speak str(text), return nothing. delay is how many seconds to wait before speaking. nospam is the number of seconds to wait before the same exact phrase can be said again."
        sleep(delay)
        if nospam:
            with self.lock:
                if text in self.speechspam: # If this phrase is in speechspam, that means that text was said less than nospam seconds ago.
                    return # So we bail and do nothing
                else: # we're all clear to speak text. Add this phrase to speechspam
                    self.speechspam.add(text)
            AntiSpam(self.speechspam, nospam, self.lock, text).start() # fork off a thread to wait nospam seconds and then remove its phrase from self.speechspam
        self.speakmeth(text)

# class Audio():
#     "This class has one method that plays a wav file that is relative to the sounds folder. Use Audio.play('relpath/to/wav') to play a sound."
#     def __init__(self):
#         try:
#             import winsound
#         except ImportError:
#             print "No audio player detected. Sound effects won't work."
#         else:
#             self.play = self.winPlay()
#     def winPlay(self, wavpath, delay=0):
#         sleep(delay)
#         winsound.PlaySound(wavpath, winsound.SND_FILENAME)

class EventHandler():
    """This is the main class. Each event should be passed in via handleEvent(). This object will update your ship's status and then act on the event if need be.
    config is the config object that will be checked
    logdir is the path to the log dir (str)
    when debug is True, the initial spaceship state is not built so that every event can be run through this script.
    """
    def __init__(self, config, logdir=None, debug=False):
        self.config = config
        self.triggers = {} # This is a dictionary of event names to a list of methods we should call in this object to handle them. {'DockingGranted': ['LandingPadLocation', ...], }
        # it has a special _ALL key that will trigger on every event and _EXIT that runs when exiting this script
        if self.config.getboolean('Global Settings', 'Speech', 'True'):
            self.tts = TextToSpeech()
        else:
            self.tts = False # this provides a way to quickly check if global speech is enabled or not
        # Do initial setup of the spaceship tracker:
        self.spaceship = spaceship.SpaceShip(playername=self.config.get('Global Settings', 'player name'), journaldir=logdir)
        if not debug:
            self.spaceship.handleEvents(self.spaceship.parseJournal(startup=True))
        # Go through the config object and build self.triggers:
        # First let's define some commonly used groups to make this simpler:
        gainmoney_events = ('MissionCompleted', 'CommunityGoalReward', 'MarketSell', 'ModuleBuy', 'ModuleSell', 'ModuleSellRemote', 'NewCommander', 'PowerplaySalary', 'RedeemVoucher', 'Search And Rescue', 'SellDrones', 'SellExplorationData',
                            'ShipyardSell')
        gaincargo_events = ('MissionAccepted', 'MissionCompleted', 'CollectCargo', 'MarketBuy', 'MiningRefined', 'PowerplayCollect')
        gainmaterial_events = ('MaterialCollected',)
        mission_events = ('MissionAbandoned', 'MissionAccepted', 'MissionCompleted', 'MissionFailed', 'MissionRedirected')
        system_jump_events = ('StartJump', 'FSDJump')
        # Next, lets make a big dict of methods to the events that should trigger them:
        methods2events = {
            'LandingPadLocation': ('DockingGranted',),
            'MoneyGainedMilestone': gainmoney_events,
            'AnnouncePhysicalMaterialsFull': gainmaterial_events,
            'AnnounceDataMaterialsFull': gainmaterial_events,
            'ShowEndOfSessionStats': ('_EXIT',),
            'AnnounceDataMaterialsOptimumNumber': (), # this is actually a part of AnnounceDataMaterialsFull
            'AnnouncePhysicalMaterialsOptimumNumber': (), # ditto
            'ShowMissions': mission_events,
            'CountTargetKills': ('MissionAccepted', 'Bounty'),
            'AnnounceScoopableStar': system_jump_events,
            'AnnounceUnscoopableStar': system_jump_events,
        }
        for section in self.config.sections():
            if section == 'Global Settings':
                continue
            elif self.isSectionSpeechTextOn(section, 'speech') or self.isSectionSpeechTextOn(section, 'text'): # if (all speech is on and this individual speech is on) or this text is on...
                methname = ''.join(section.split()) # translate section name into method name by camelcasing it
                for eventtrigger in methods2events[methname]:
                    try:
                        self.triggers[eventtrigger].append(methname)
                    except KeyError: # this event isn't in triggers yet, create it
                        self.triggers[eventtrigger] = [methname,]
                # initialize the method:
                try:
                    methname = getattr(self, ''.join((methname, '_init')))
                except AttributeError:
                    pass
                else:
                    methname()
    def isSectionSpeechTextOn(self, section, textorspeech):
        """return True if sections speech or text is enabled, following global rules.
        section is the name of the section, a str
        textorspeech must be either 'text' or 'speech'.
        """
        if textorspeech == 'speech' and not self.tts: # if we're checking speech but global speech is off...
            return False
        return self.config.getboolean(section, textorspeech, 'False')
    def handleEvents(self, events):
        "Events is a list of journalentry event dicts. This method looks at the events, see if there are any triggers for them, and then runs the triggers and returns nothing."
        for journalentry in events:
            #if DEBUG:
            #    print journalentry['event']
            #    print self.triggers
            #    print self.triggers[journalentry['event']]
            try:
                self.triggers[journalentry['event']]
            except KeyError:
                pass # there are no triggers
            else:
                for trigger in self.triggers[journalentry['event']]:
                    trigger = getattr(self, trigger)
                    trigger(journalentry)
        try: # try to process the special _ALL trigger. Only run the all trigger once per group of events received.
            self.triggers['_ALL']
        except KeyError:
            pass # no all trigger being used
        else:
            for trigger in self.triggers['_ALL']:
                trigger = getattr(self, trigger)
                trigger(journalentry)
    def convertToLocalTime(self, time):
        "Convert time, a datetime object, to a local time by reading the GMT offset from the config file. A new datetime obj is returned."
        return time + datetime.timedelta(hours=self.config.getint('Global Settings', 'timezone offset'))
    def getTimeDifference(self, earlytime, latertime):
        """find out how much time is between earlytime and latertime and return a str describing how much time is between them.
        earlytime is the earlier datetime obj
        latertime is the later datetime obj
        a str like "%d days %dh:%0.2dm" is returned. days is omitted if the time is less than a day."""
        length = latertime - earlytime
        textlist = []
        if length.days > 0:
            textlist.append("%d days " % length.days)
        textlist.append("%sh:%0.2dm" % (length.seconds / 60 / 60, length.seconds / 60 % 60))
        return ''.join(textlist)
    def printMissionsHeader(self):
        "prints the total number of missions you have as a header before more mission information. This code is shared by ShowMissions() and in ShowEndOfSessionStats(). returns nothing."
        print "Current Missions:",
        if not self.spaceship.missions:
            print "None"
        else:
            print '%s/%s' % (len(self.spaceship.missions), self.spaceship.missions.maxmissions)
    def printMissionsByDestinationPort(self):
        "prints a list of missions sorted by events. returns nothing."
        missions = self.spaceship.missions.getSortedDestinations()
        print "\tMissions sorted by destination port: %s total" % len(missions)
        textlist = []
        for num in range(len(missions)):
            textlist.append(('\t%d' % missions[num][0], "%s - %s" % (missions[num][1], missions[num][2])))
        printAlignedText(textlist)
    def printMissionsByReward(self):
        "prints a list of missions sorted by rewards. returns nothing."
        missions = self.spaceship.missions.getSortedRewards()
        print "\tMissions sorted by reward: %s total" % format(sum([x[0] for x in missions]), ',')
        try:
            strlen = len(format(self.spaceship.missions[missions[0][1]]['Reward'], ','))  # This tells us how much to indent the lesser amounts of money
        except KeyError: # Sometimes missions don't have a reward, they just pay you in commodities
            strlen = 1 # consider it 0
        for num in range(len(missions)):
            print "\t\t%s%s: %s - %s" % (' ' * (strlen - len(format(missions[num][0], ','))), format(missions[num][0], ','), self.spaceship.missions[missions[num][1]].get('DestinationSystem', 'None'),
                                         self.spaceship.missions[missions[num][1]].get('DestinationStation', 'None'))
    def printMissionsByExpirationTime(self):
        "prints a list of missions sorted by expiration time. returns nothing."
        missions = self.spaceship.missions.getSortedExpiration()
        # calculate how long you have until the earliest mission expires so we can put that with the header
        print "\tMissions sorted by expiration time: %s until first expiration" % self.getTimeDifference(datetime.datetime.now(), self.convertToLocalTime(missions[0][0]))
        for num in range(len(missions)):
            print "\t\t%s: %s - %s" % (self.convertToLocalTime(missions[num][0]).strftime('%m/%d/%Y %H:%M:%S %Z'), self.spaceship.missions[missions[num][1]].get('DestinationSystem', 'None'),
                                       self.spaceship.missions[missions[num][1]].get('DestinationStation', 'None'))
    ################################ EVENTS ##########################################################
    # All events MUST be named exactly as they are in the config file, but with spaces removed
    # Event methods may have a initialization method with the same name with _init after it. These methods take no parameters
    def LandingPadLocation_init(self):
        self.padlocations = (
            (6, 'front'),
            (6, 'middle'),
            (6, 'middle'),
            (6, 'back'),
            (7, 'front'),
            (7, 'middle'),
            (7, 'middle'),
            (7, 'back'),
            (8, 'front'),
            (8, 'back'),
            (9, 'front'),
            (9, 'middle'),
            (9, 'middle'),
            (9, 'middle'),
            (9, 'back'),
            (10, 'front'),
            (10, 'middle'),
            (10, 'middle'),
            (10, 'back'),
            (11, 'front'),
            (11, 'middle'),
            (11, 'middle'),
            (11, 'back'),
            (12, 'front'),
            (12, 'back'),
            (1, 'front'),
            (1, 'middle'),
            (1, 'middle'),
            (1, 'middle'),
            (1, 'back'),
            (2, 'front'),
            (2, 'middle'),
            (2, 'middle'),
            (2, 'back'),
            (3, 'front'),
            (3, 'middle'),
            (3, 'middle'),
            (3, 'back'),
            (4, 'front'),
            (4, 'back'),
            (5, 'front'),
            (5, 'middle'),
            (5, 'middle'),
            (5, 'middle'),
            (5, 'back'),
        )
    def LandingPadLocation(self, journalentry):
        """Announce your landing pad location
        https://imgur.com/a/3htsd#hw5lAnU for reference. Inside pads are closer, outside ones are in the back.
        """
        # Bugs: this method reacts to all granted docking requests, it can't tell if you're docking at a planetary base or an outpost where the position doesn't apply
        location = self.padlocations[journalentry['LandingPad'] - 1]
        if not self.config.getboolean('Landing Pad Location', 'green on right', 'True'): # green on right is True if we're entering the mailslot with the green light on the right hand side. Set this to false if you're a britbonger.
            clockpos = location[0] - 6 # if green is on the left, inverse the clock location:
            if clockpos < 1:
                clockpos += 12
            location = (clockpos, location[1])
        # now location is a tuple of (clockpos, depth), announce it:
        if self.isSectionSpeechTextOn('Landing Pad Location', 'text'):
            print "Landing pad is at %s o'clock in the %s." % location
        if self.isSectionSpeechTextOn('Landing Pad Location', 'speech'):
            self.tts.speak('Landing pad is at %s oclock in the %s.' % location, delay=4.75)
    def MoneyGainedMilestone_init(self):
        self.money_gained_milestone_oldmoney = self.spaceship.sessionstats['oldest'].getTotalMoneyGained() # take a snapshot of how much money you've gained
        self.money_gained_milestone_announceamount = self.config.getintlist('Money Gained Milestone', 'announce every') # Read the config once, don't build it over and over again
    def MoneyGainedMilestone(self, journalentry):
        "Announce when you've gained certain amounts of money"
        for announceamount in self.money_gained_milestone_announceamount:
            # if your current amount of money is now more divisible than your total money by announceamount when you first ran this script...
            if self.money_gained_milestone_oldmoney / announceamount < self.spaceship.sessionstats['oldest'].getTotalMoneyGained() / announceamount:
                if self.isSectionSpeechTextOn('MoneyGainedMilestone', 'text'):
                    print "Congratulations on making another %s credits!" % format(announceamount, ',')
                if self.isSectionSpeechTextOn('MoneyGainedMilestone', 'speech'):
                    self.tts.speak("Congratulations on making another %s credits!" % format(announceamount, ','), nospam=10)
        self.money_gained_milestone_oldmoney = self.spaceship.sessionstats['oldest'].getTotalMoneyGained() # update your amount of money so it doesn't repeat the same announcement
    def AnnouncePhysicalMaterialsFull(self, journalentry):
        "Announce when you've filled up your physical materials."
        if self.spaceship.materials.getTotalAmount() >= self.spaceship.materials.maximum:
            if self.isSectionSpeechTextOn('Announce Physical Materials Full.', 'text'):
                print 'Physical materials are full.'
            if self.isSectionSpeechTextOn('Announce Physical Materials Full.', 'speech'):
                self.tts.speak('Physical materials are full.', nospam=30)
            if self.isSectionSpeechTextOn("Announce Physical Materials Optimum Number", "text") or self.isSectionSpeechTextOn("Announce Physical Materials Optimum Number", "speech"):
                # compute once, report twice if necessary
                optimum_amount_text = "You shouldn't have more than %s of any type of physical material." % getOptimumAmountOfMaterials(self.spaceship.materials, self.config.getint("Announce Physical Materials Optimum Number", "free space", 50))
                if self.isSectionSpeechTextOn("Announce Physical Materials Optimum Number", "text"):
                    print optimum_amount_text
                if self.isSectionSpeechTextOn("Announce Physical Materials Optimum Number", "speech"):
                    self.tts.speak(optimum_amount_text)
    def AnnounceDataMaterialsFull(self, journalentry):
        "Announce when you've filled up your data materials."
        if self.spaceship.datamaterials.getTotalAmount() >= self.spaceship.datamaterials.maximum:
            if self.isSectionSpeechTextOn('Announce Data Materials Full.', 'text'):
                print 'Data materials are full.'
            if self.isSectionSpeechTextOn('Announce Data Materials Full', 'speech'):
                self.tts.speak('Data materials are full.', nospam=30)
            if self.isSectionSpeechTextOn("Announce Data Materials Optimum Number", "text") or self.isSectionSpeechTextOn("Announce Data Materials Optimum Number", "speech"):
                # compute once, report twice if necessary
                optimum_amount_text = "You shouldn't have more than %s of any type of data." % getOptimumAmountOfMaterials(self.spaceship.datamaterials, self.config.getint("Announce Data Materials Optimum Number", "free space", 20))
                if self.isSectionSpeechTextOn("Announce Data Materials Optimum Number", "text"):
                    print optimum_amount_text
                if self.isSectionSpeechTextOn("Announce Data Materials Optimum Number", "speech"):
                    self.tts.speak(optimum_amount_text)
    def ShowMissions(self, journalentry):
        "Any time your missions change, print useful information about them."
        if self.config.getbooleanauto('Show Missions', 'Total Header', self.spaceship.missions, 'True'):
            self.printMissionsHeader()
        # Now check the rest of the sortings and only display them if there are missions:
        if self.spaceship.missions:
            if self.config.getbooleanauto('Show Missions', 'Current Missions By Destination Port', True, 'True'): # True is passed to getbooleanauto because we're already checking for mission in the above if statement.
                self.printMissionsByDestinationPort()                                                             # So really True is ignored in the config.
            if self.config.getbooleanauto('Show Missions', 'Current Missions By Reward', True, 'True'):
                self.printMissionsByReward()
            if self.config.getbooleanauto('Show Missions', 'Current Missions By Expiration Time', True, 'True'):
                self.printMissionsByExpirationTime()
    def CountTargetKills_init(self):
        self.target_kills = {} # This is a dictionary of target faction names to lists of current kills out of total needed: {'Tau-1 Hydrae Hand Gang': [0, 28], ... }
    def CountTargetKills(self, journalentry):
        "When you take a mission to kill X number of ships, this will announce how many you've killed after each kill."
        if journalentry['event'] == 'MissionAccepted' and 'Massacre' in journalentry['Name']: # if we accepted a massacre mission...
            self.target_kills[journalentry['TargetFaction']] = [0, journalentry['KillCount']] # then set up the counter
        elif journalentry['event'] == 'Bounty': # if we just killed someone in a lawful system...
            try:
                self.target_kills[journalentry['VictimFaction']][0] += 1
            except KeyError: # you just killed someone outside of your mission
                pass
            else: # announce it
                if self.target_kills[journalentry['VictimFaction']][0] == self.target_kills[journalentry['VictimFaction']][1]: # If we've reached the last kill
                    del self.target_kills[journalentry['VictimFaction']] # remove this mission that's being tracked
                    return # and don't announce the last kill, the game will tell you "mission completed" which is enough.
                phrase = "That was kill number %s" % self.target_kills[journalentry['VictimFaction']][0]
                if self.config.getboolean('Count Target Kills', 'total', 'True'):
                    phrase = "%s out of %s." % (phrase, self.target_kills[journalentry['VictimFaction']][1])
                else:
                    phrase += '.'
                if self.isSectionSpeechTextOn('Count Target Kills', 'text'):
                    print phrase
                if self.isSectionSpeechTextOn('Count Target Kills', 'speech'):
                    self.tts.speak(phrase) # no nospam here because it's possible to have 2 massacre missions going at the same time, at the same amount of progress, and to kill both ships at once. I want to hear it twice in that case.
    def AnnounceScoopableStar_init(self):
        self.scoopable_star_types = 'KGBFOAM'
    def AnnounceScoopableStar(self, journalentry):
        """Announce if the star you just jumped to is scoopable. Do nothing if it is not.
        So the way this works is that when you start to jump to another system, a StartJump event is generated. This event tells you the type of star you're jumping to:
        { "timestamp":"2017-11-25T04:43:32Z", "event":"StartJump", "JumpType":"Hyperspace", "StarSystem":"LQ Hydrae", "StarClass":"K" }
        This jump can be aborted, so we can't just announce this every time you *start* the jump, I want it to show when you arrive.
        So what we'll do is remember the StarClass from the StartJump event and then when we actually make the jump a FSDJump event is generated. This will be our queue to announce.
        All this code is shared by Announce Unscoopable Star
        """
        try: # Try recording the type of star if this was a StartJump event
            self.star_class = journalentry['StarClass']
        except KeyError: # this was the FSDJump event, so do the actual announcing.
            if journalentry.get('JumpType') == 'Hyperspace':
                if self.star_class in self.scoopable_star_types:
                    midphrase = ''
                else:
                    midphrase = 'not '
                phrase = "This star is %sscoopable." % midphrase
                # Do the scoopable star stuff:
                if self.isSectionSpeechTextOn('Announce Scoopable Star', 'text') and not midphrase:
                    print phrase
                if self.isSectionSpeechTextOn('Announce Scoopable Star', 'speech') and not midphrase:
                    self.tts.speak(phrase, nospam=10)
                # Do the unscoopable star stuff:
                if self.isSectionSpeechTextOn('Announce Unscoopable Star', 'text') and midphrase:
                    print phrase
                if self.isSectionSpeechTextOn('Announce Unscoopable Star', 'speech') and midphrase:
                    self.tts.speak(phrase, nospam=10)
    def AnnounceUnscoopableStar_init(self):
        self.AnnounceScoopableStar_init()
    def AnnounceUnscoopableStar(self, journalentry):
        if self.isSectionSpeechTextOn('Announce Scoopable Star', 'text') or self.isSectionSpeechTextOn('Announce Scoopable Star', 'speech'):
            pass
        else:
            self.AnnounceScoopableStar(journalentry) # if AnnounceScoopableStar is on, don't call that method a second time
    def ShowEndOfSessionStats(self, journalentry):
        "Print stats at the end of the session"
        session = self.spaceship.sessionstats['appstart']
        if self.config.getbooleanauto('Show End Of Session Stats', 'cmdr name', self.spaceship.playername, 'True'):
            print 'Stats for CMDR %s' % self.spaceship.playername
        if self.config.getbooleanauto('Show End Of Session Stats', 'current balance', self.spaceship.moneycurrentbalance, 'True'):
            print "Current Balance: %s" % format(self.spaceship.moneycurrentbalance, ',')
        if self.config.getbooleanauto('Show End Of Session Stats', 'current rank', True, 'True'):
            print "Current rank:"
            textlist = []
            for rank in ('Combat', 'Trade', 'Explore', 'Empire', 'Federation', 'CQC'):
                rankno = getattr(self.spaceship, 'rank_%s' % rank.lower())
                if rankno < 10: # if rankno is a single digit
                    rankpre = ' ' # prepend a space before so it aligns better
                else:
                    rankpre = ''
                rankvalue = "%s%s - %s" % (rankpre, rankno, getattr(spaceship, '%sRANKS' % rank.upper())[rankno])
                if rank == 'Explore': # change Explore to Exploration
                    textlist.append(('Exploration', rankvalue))
                else:
                    textlist.append(('%s' % rank, rankvalue))
            printAlignedText(textlist)
        if self.config.getbooleanauto('Show End Of Session Stats', 'current cargo', self.spaceship.cargo, 'True'):
            print "Current Cargo:",
            if not self.spaceship.cargo:
                print "None"
            else:
                print self.spaceship.cargo.getTotalAMount()
                for cargo in self.spaceship.cargo: # no need for aligning here as the haulage amount will screw it up anyway
                    print "\t%s: %s" % (cargo, self.spaceship.cargo[cargo]['amount'])
                    if self.spaceship.cargo[cargo]['haulage']:
                        print '\t\thaulage: %s' % self.spaceship.cargo[cargo]['haulage']
                    if self.spaceship.cargo[cargo]['haulage']:
                        print '\t\thaulage: %s' % self.spaceship.cargo[cargo]['haulage']
        if self.config.getbooleanauto('Show End Of Session Stats', 'current physical materials', self.spaceship.materials, 'True'):
            print "Current Physical Materials: %s/1000" % self.spaceship.materials.getTotalAmount()
        if self.config.getbooleanauto('Show End Of Session Stats', 'current data materials', self.spaceship.datamaterials, 'True'):
            print "Current Data Materials: %s/500" % self.spaceship.datamaterials.getTotalAmount()
        if self.config.getbooleanauto('Show End Of Session Stats', 'current missions', self.spaceship.missions, 'True'):
            self.printMissionsHeader()
            if self.spaceship.missions:
                if self.config.getbooleanauto('Show End Of Session Stats', 'current missions by destination port', True, 'True'):
                    self.printMissionsByDestinationPort()
                if self.config.getbooleanauto('Show End Of Session Stats', 'current missions by reward', True, 'True'):
                    self.printMissionsByReward()
                if self.config.getbooleanauto('Show End Of Session Stats', 'current missions by expiration time', True, 'True'):
                    self.printMissionsByExpirationTime()
        if self.config.getbooleanauto('Show End Of Session Stats', 'current passengers', self.spaceship.passengers, 'True'):
            print "Current Passengers:",
            if not self.spaceship.passengers:
                print "None"
            else:
                print
                for pax in self.spaceship.passengers:
                    print "\t%s %ss" % (self.spaceship.passengers[pax]['count'], self.spaceship.passengers[pax]['type']),
                    if self.spaceship.passengers[pax]['vip']:
                        print '\tVIP',
                    if self.spaceship.passengers[pax]['wanted']:
                        print '\tWanted',
                    print
        if self.config.getbooleanauto('Show End Of Session Stats', 'session time', True, 'True'):
            # print out a nice little session title header with information about when the session started, ended, and it's duration:
            try:
                sessionlength = session.latesttime - session.starttime
            except TypeError: # raised from unsupported operand type(s) for -: 'NoneType' and 'NoneType' when you haven't played at all
                print "You didn't play at all this session."
            else:
                local_starttime = self.convertToLocalTime(session.starttime)
                local_endtime = self.convertToLocalTime(session.latesttime)
                # I used to use a lot of print statements to print the time header, but then I had to resort to sys.stdout.write to avoid having an extra space. This is much simpler.
                # Also please note that although we're using the same textlist variable name, this textlist is NOT printed by printAlignedText()
                textlist = ["\nStats since app start (%s-%0.2d-%0.2d %s:%0.2d" % (local_starttime.year, local_starttime.month, local_starttime.day, local_starttime.hour, local_starttime.minute)]
                # if this session lasted between 2 dates, print both dates. If the session was all on the same day, only print the end time and not the end date
                if local_starttime.day != local_endtime.day:
                    textlist.append(" - %s-%0.2d-%0.2d " % (local_endtime.year, local_endtime.month, local_endtime.day))
                else:  # the session was all in the same day, don't show the date a second time
                    textlist.append("-")
                textlist.append("%s:%0.2d, duration: " % (local_endtime.hour, local_endtime.minute))
                textlist.append(self.getTimeDifference(session.starttime, session.latesttime))
                textlist.append('):')
                print ''.join(textlist) # so much fucking simpler, look at this same code in spaceship.py, what a clusterfuck

        # Now we print the individual statistics. This all has to be formatted properly, so we'll add it all to a list and pass it to printAlignedText()
        def mkScorePerHour(configname, attributename):
            """Create a textlist item of stats that have per hour. This
            configname is the name of the variable from the config, str()
            attributename is a string, the name of the attribute we are reading or method we are executing of this session
            returns a list of textlist stuff, so make sure you extend the list and not append to it. This will check the regular value as well as per hour.
            """
            textlist = []
            if self.config.getbooleanauto('Show End Of Session Stats', configname, getattr(session, attributename), 'True'):
                textlist.append((configname, format(getattr(session, attributename)(), ',')))
            if self.config.getbooleanauto('Show End Of Session Stats', '%s Per Hour' % configname, getattr(session, attributename), 'True'):
                textlist.append(('', '%s per hour' % format(session.getScorePerHour(attributename), ',')))
            return textlist

        textlist = []
        # Print the important stuff at the top with their per hour stats
        for pair in (('Money Net Change', 'getNetMoneyChange'),
                     ('Money Net Change Without Modules Or Ships', 'getNetMoneyChangeWithoutModulesOrShips'),
                     ('Total Money Gained', 'getTotalMoneyGained'),
                     ('Total Money Spent', 'getTotalMoneySpent'),
                     ('Total Money Spent Without Modules Or Ships', 'getTotalMoneySpentWithoutModulesOrShips'),
                     ):
            textlist.extend(mkScorePerHour(*pair))
        # Now print out all the other individual stats:
        for configname in ('Total Money Gained From Commodities Sold', 'Bankruptcy Declared', 'Cargo Delivered', 'Cargo Delivered Engineer', 'Cargo Delivered Powerplay', 'Cargo Ejected', 'Cargo Gained Bought Commodity', 'Cargo Gained Haulage',
                           'Cargo Gained Mission Reward', 'Cargo Gained Powerplay', 'Cargo Gained Scooped', 'Cargo Lost Death', 'Cargo Sold', 'Cargo Sold Drones', 'Cargo Sold Illegal', 'Cargo Sold Search And Rescue', 'Cleared Saves',
                           'Cockpit Breaches', 'Community Goals Completed', 'Community Goals Discarded', 'Community Goals Joined', 'Community Goals Scientific Research', 'Crew Ended', 'Crew Ended Crime', 'Crew Fired', 'Crew Hired',
                           'Crew Kicked', 'Crew Kicked Crime', 'Crew Quit', 'Crews Joined', 'Deaths', 'Docking Cancelled', 'Docking Denied', 'Docking Granted', 'Docking Requested', 'Docking Timeout', 'Docking Undocked', 'Engineer Bounty Spent',
                           'Engineer Modifications Applied', 'Engineers Invited', 'Engineers Known', 'Engineers Rank Gained', 'Engineers Unlocked', 'Fighter Docked', 'Fighter Launched Npc', 'Fighter Launched Player', 'Fines Gained',
                           'Fines Legacy Paid', 'Fsd Jump Started', 'Fuel Bought', 'Fuel Scoop Started', 'Fuel Scooped', 'Games Loaded', 'Total Cargo Gained', 'Total Cargo Sold', 'Total Galactic Average Sales', 'Heat Damage Taken',
                           'Heat Warnings', 'Hull Damage Taken Fifths Fuzzy', 'Interdictions Committed Fail Npc', 'Interdictions Committed Fail Player', 'Interdictions Committed Success Npc', 'Interdictions Committed Success Player',
                           'Interdictions Escaped Npc', 'Interdictions Escaped Player', 'Interdictions Escapes Failed Npc', 'Interdictions Escapes Failed Player', 'Interdictions Submitted Npc', 'Interdictions Submitted Player', 'Kills Bounty',
                           'Kills Capitalship', 'Kills Faction Bond', 'Kills Pvp', 'Materials Data Discarded', 'Materials Data Gained', 'Materials Data Spent Engineer', 'Materials Discovered', 'Materials Physical Discarded',
                           'Materials Physical Gained', 'Materials Physical Spent Engineer', 'Materials Physical Spent Synthesis', 'Messages Received Local', 'Messages Received Npc', 'Messages Received Player', 'Messages Received Voicechat',
                           'Messages Received Wing', 'Messages Sent', 'Missions Abandoned', 'Missions Accepted', 'Missions Completed', 'Missions Failed', 'Missions Passengers Delivered', 'Missions Passengers Failed', 'Missions Redirected',
                           'Modules Bought', 'Modules Retrieved', 'Modules Sold', 'Modules Sold Remote', 'Modules Swapped', 'Money Gained Blackmarket', 'Money Gained Bounty', 'Money Gained Communitygoal', 'Money Gained Exploration',
                           'Money Gained Exploration Bonus', 'Money Gained Market', 'Money Gained Missions', 'Money Gained Powerplaysalary', 'Money Gained Search And Rescue', 'Money Gained Selldrones', 'Money Gained Sellmodules',
                           'Money Gained Shipsell', 'Money Gained Unknown', 'Money Over Market Galactic Average', 'Money Under Market Galactic Average', 'Money Spent Ammo', 'Money Spent Buyship', 'Money Spent Commodities', 'Money Spent Crewhire',
                           'Money Spent Drones', 'Money Spent Engineer Contribution', 'Money Spent Explorationdata', 'Money Spent Fetchremotemodule', 'Money Spent Fines', 'Money Spent Fuel', 'Money Spent Legacyfines',
                           'Money Spent Mission Donations', 'Money Spent Modulebuy', 'Money Spent Moduleretrieve', 'Money Spent Modulestore', 'Money Spent Powerplayfasttrack', 'Money Spent Rebuyship', 'Money Spent Repairs',
                           'Money Spent Restockvehicle', 'Money Spent Tradedata', 'Money Spent Transfership', 'Music Changed', 'Nav Beacons Scanned', 'Neutron Boost Damages', 'Neutron Boosts', 'Neutron Boosts Value', 'New Commander Created',
                           'Planet Landings', 'Planet Liftoff Npc', 'Planet Liftoff Player', 'Powerplay Defect', 'Powerplay Join', 'Powerplay Leave', 'Powerplay Salaries Redeemed', 'Powerplay Vote', 'Powerplay Votes Casted', 'Powerplay Vouchers',
                           'Rank Gained Combat', 'Rank Gained Cqc', 'Rank Gained Empire', 'Rank Gained Explore', 'Rank Gained Federation', 'Rank Gained Trade', 'Reboot Repairs', 'Scanned Data Points', 'Scanned Datalinks', 'Scanned For Cargo',
                           'Scanned For Crime', 'Scanned Tourist Beacons', 'Screenshots Taken', 'Self Destructed', 'Shields Depleted', 'Shields Regained', 'Ship Name Set', 'Ships Bought', 'Ships Sold', 'Ships Swapped', 'Ships Transferred',
                           'Srv Docked', 'Srv Launched Npc', 'Srv Launched Player', 'Stellar Object Scanned', 'Supercruise Entered', 'Supercruise Exited', 'Synthesized Something', 'Uss Drops', 'Voucher Count Datalink', 'Voucher Money Datalink',
                           'Vouchers Redeemed Bounty', 'Vouchers Redeemed Combatbond', 'Vouchers Redeemed Scannable', 'Vouchers Redeemed Settlement', 'Vouchers Redeemed Trade', 'Wing Invites Sent', 'Wings Joined', 'Wings Left'):
            try:
                value = getattr(session, configname.lower().replace(' ', '_'))
            except AttributeError: # raised from trying to get an attribute from a method, call the method instead:
                value = getattr(session, ''.join(('get', configname.title().replace(' ', ''))))()
            if self.config.getbooleanauto('Show End Of Session Stats', configname, value, 'True'):
                textlist.append((configname, format(value, ',')))
        # Finally, print it all:
        printAlignedText(textlist)
        # Now print the top visited systems and stations:
        for visitedtype in ('systems', 'stations'):
            totalvisited = getattr(session, ''.join(('visited_', visitedtype))).getTotalVisited()
            if self.config.getbooleanauto('Show End Of Session Stats', 'Top %s Visited' % visitedtype.title(), totalvisited, 'True'):
                textlist = []
                topnum = self.config.getint('Show End Of Session Stats', 'Number of %s Visited' % visitedtype.title(), 5)
                top = getattr(session, ''.join(('visited_', visitedtype))).getMostVisited()[:topnum]
                print "Top %s most visited %s: (%s total)" % (topnum, visitedtype, totalvisited)
                for num in range(len(top)):
                    try:
                        hyphenstation = " - %s" % top[num][2]
                    except IndexError:
                        hyphenstation = ''
                    textlist.append(("%d" % top[num][0], "%s%s" % (top[num][1], hyphenstation)))
                printAlignedText(textlist)
        # Now do mined elements:
        if self.config.getbooleanauto('Show End Of Session Stats', 'Top Elements Mined', len(session.mined_elements), 'True'):
            topnum = self.config.getint('Show End Of Session Stats', 'Number of Elements Mined', 5)
            print "Top %s most mined elements: (%s total)" % (topnum, session.mined_elements.getTotalMined())
            textlist = []
            top = session.mined_elements.getMostMined()
            for num in range(len(top)):
                textlist.append((str(top[num][0]), top[num][1]))
            printAlignedText(textlist)

##################### MAIN ##########################
if __name__ == '__main__':
    opts = optparse.OptionParser(usage="%prog [options]")
    opts.add_option('-c', '--configfile', action='store', dest='configfile', help='Specify the path to your config file')
    opts.add_option('-l', '--logdir', action='store', dest='logdir', help='Specify the path to your log folder')
    options = opts.parse_args()[0]

    config = getConfig(options.configfile)
    if not config.has_section("Global Settings"):
        createConfig()
    print "Loading logs..."
    eventhandler = EventHandler(config, logdir=options.logdir)
    eventhandler.spaceship.missions.purgeExpired()
    eventhandler.spaceship.sessionstats['appstart'].startRecording()
    print "Grindbuddy is Running! Press CTRL-C to exit."
    while True:
        try:
            events = eventhandler.spaceship.parseJournal()
            # if DEBUG:
            #     events = [{ "timestamp":"2018-01-05T21:36:45Z", "event":"ModuleSell", "Slot":"TinyHardpoint2", "SellItem":"$hpt_plasmapointdefence_turret_tiny_name;", "SellItem_Localised":"Point Defence", "SellPrice":1000000000, "Ship":"asp", "ShipID":2 },]
            eventhandler.spaceship.handleEvents(events) # update your spaceship's internal state
            eventhandler.handleEvents(events) # run event handlers here, in this live script
            sleep(config.getint("Global Settings", "poll interval"))
        except KeyboardInterrupt:
            eventhandler.handleEvents([{'event': '_EXIT'},])
            break