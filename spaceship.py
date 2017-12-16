#!/usr/bin/env python2.7
"""This module contains the base parser of the Elite: Dangerous player journal logs. It provides a SpaceShip object that
 keeps track of the current state of the ship. It also contains all of the session tracking. It does not handle higher level things such as alerting on events."""
# TODO Things to test:
# Powerplay
# 2 people playing on the same computer
# community goals
# 2.4 events that I haven't come across

###################### DOCUMENTATION #############################
# Documentation of the log API: http://edcodex.info/?m=doc
###BUGS:
# Your initial 1000 credits that you get when you start a game is counted as money_gained_missions. I didn't want to create a new type of money to track that only happens once and isn't much.
# The amount of haulage and stolen cargo can become wrong because the ejectCargo event doesn't specify which kind of cargo you ejected.
#   I assume it's possible to buy clothes from the market, get clothes from 2 missions and then abandon one of the missions to have all 3 types cargo in your hold at once.
#   This program assumes that you only eject stolen cargo so try to do that please ;)
# I can't track bonus payment from missions because when you accept a mission, it doesn't tell you the completion reward and the NPC messages asking you to rush or fight people don't show up at all.
# Hunting down the missing money bug: It seems like almost every time I start a game and a LoadGame event is generated, the money that it says I have is more than what your last session is added up to.
# This did not trigger it: a session of fighting in a combat zone, repairing, restocking, buying fuel, taking and turning in kill x faction in a combat zone missions, one where I got a bonus for killing a guy, and I turned in a "murder pirate lord"
# mission.
# OK, most of this was fixed in ModuleBuy. When you buy a module and exchange your old one, it gives you a sell price in that event, NOT the ModuleSell event. ModuleSell is only for selling modules, not exchanging them.
######################## IMPORTS ####################
import os, datetime
from json import loads

##################### GLOBALS #######################
DEBUG = False
# The indices in these ranks below correspond to how the logs describe ranks. For example, a combat rank of 0 is Harmless,
COMBATRANKS = ['Harmless', 'Mostly Harmless', 'Novice', 'Competent', 'Expert', 'Master', 'Dangerous', 'Deadly', 'Elite']
EXPLORERANKS = ['Penniless', 'Mostly Pennliess', 'Peddler', 'Dealer', 'Merchant', 'Broker', 'Entrepreneur', 'Tycoon', 'Elite']
TRADERANKS = ['Penniless', 'Mostly Penniless', 'Peddler', 'Dealer', 'Merchant', 'Broker', 'Entrepreneur', 'Tycoon', 'Elite']
FEDERATIONRANKS = ['None', 'Recruit', 'Cadet', 'Midshipman', 'Petty Officer', 'Chief Petty Officer', 'Warrant Officer',
                   'Ensign', 'Lieutenant', 'Lt. Commander', 'Post Commander', 'Post Captain', 'Rear Admiral', 'Vice Admiral', 'Admiral']
EMPIRERANKS = ['None', 'Outsider', 'Serf', 'Master', 'Squire', 'Knight', 'Lord', 'Baron', 'Viscount ', 'Count', 'Earl', 'Marquis',
               'Duke', 'Prince', 'King']
CQCRANKS = ['Helpless', 'Mostly Helpless', 'Amateur', 'Semi Professional', 'Professional', 'Champion', 'Hero', 'Legend', 'Elite']

##################### FUNCTIONS #####################
def sanitizeCargo( name ):
    "name is a string, return that string lowered and without spaces."
    # This must be done because sometimes the game refers to "Survival Equipment", other times it's called "survivalequipment"
    # Sometimes they use all lower case, sometimes it's camelcase, sometimes it includes spaces like above.
    # also they sometimes use Non-Lethal Weapons, other times it's nonlethalweapons. They do this with a couple different things as you can see
    if name[1:] == 'arcotics': # hack because if we 'basicnarcotics'.replace('narcotics', 'basicnarcotics') -> 'basicbasicnarcotics'
        name = 'basicnarcotics'
    return ''.join( name.split() ).lower().replace('non-lethal', 'nonlethal')

def playerOrNpc(journalentry):
    """This function takes a journalentry dict and checks the IsPlayer and PlayerControlled keys.
    If it's a player, 'player' is returned, 'npc' if it's an npc."""
    try:
        if journalentry['IsPlayer']:
            return 'player'
        elif not journalentry['IsPlayer']:
            return 'npc'
    except KeyError:
        if journalentry['PlayerControlled']:
            return 'player'
        elif not journalentry['PlayerControlled']:
            return 'npc'
    raise Exception("Unable to detect player or npc. journalentry was: %s" % journalentry)

def reverse_readline(filename, buf_size=8192):
    "A generator that returns the lines of a file in reverse order, stolen from https://stackoverflow.com/questions/2301789/read-a-file-in-reverse-order-using-python lolololololol"
    with open(filename) as fh:
        segment = None
        offset = 0
        fh.seek(0, os.SEEK_END)
        file_size = remaining_size = fh.tell()
        while remaining_size > 0:
            offset = min(file_size, offset + buf_size)
            fh.seek(file_size - offset)
            buffer = fh.read(min(remaining_size, buf_size))
            remaining_size -= buf_size
            lines = buffer.split('\n')
            # the first line of the buffer is probably not a complete line so
            # we'll save it and append it to the last line of the next buffer
            # we read
            if segment is not None:
                # if the previous chunk starts right from the beginning of line
                # do not concat the segment to the last line of new chunk
                # instead, yield the segment first
                if buffer[-1] is not '\n':
                    lines[-1] += segment
                else:
                    yield segment
            segment = lines[0]
            for index in range(len(lines) - 1, 0, -1):
                if len(lines[index]):
                    yield lines[index]
        # Don't yield None if the file was empty
        if segment is not None:
            yield segment

def timestamp_to_datetimeobj(timestamp):
    "return a datetime object from a timestamp str from the logs."
    try:
        return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")

##################### CLASSES #######################
class NoLogsFound( Exception ):
    "Raised when no logs are found, critical error"
    pass

class PositiveInt(int):
    "This is an int object that can never fall below 0. It's used for cargo where sometimes we subtract things into the negative."
    def __new__(cls, value, *args, **kwargs):
        if value < 0:
            raise ValueError, "positive types must not be less than zero"
        return  super(PositiveInt, cls).__new__(cls, value)
    def __add__(self, other):
        res = super(PositiveInt, self).__add__(other)
        return self.__class__(max(res, 0))
    def __sub__(self, other):
        res = super(PositiveInt, self).__sub__(other)
        return self.__class__(max(res, 0))
    def __mul__(self, other):
        res = super(PositiveInt, self).__mul__(other)
        return self.__class__(max(res, 0))
    def __div__(self, other):
        res = super(PositiveInt, self).__div__(other)
        return self.__class__(max(res, 0))

class SessionStat():
    "This represents one session worth of stats. Multiple sessions run simultaneously to track stats starting from different points in time"
    def __init__(self, name):
        """name is the name of this session. Different sessions start tracking at different times.
        The default ones are: oldest is the oldest log we can find, game is at start of game, appstart is at start of program.
        All attributes of this object should be positive, even when counting bad things or reductions."""
        self.name = name
        self.reset()
    def reset(self, recording=False):
        "Reset the session back to 0. This can also be used to initialize a new session. isrecording is whether the reset session will be actively recording or not. returns nothing."
        self.starttime = None  # a datetime obj of when the first even was seen
        self.latesttime = None  # ^^ for the latest event
        if recording:
            self.startRecording()
        else:
            self.isrecording = False
        ### GAINING MONEY
        self.money_gained_missions = 0 # how much money you've made from completing missions
        self.money_gained_communitygoal = 0 # how much money you've made from turning in community goals
        self.money_gained_market = 0 # how much money you've made selling commodoties to regular markets
        self.money_gained_blackmarket = 0 # how much money you've made selling commodities on the black market
        self.money_gained_selldrones = 0 # how much money you've made selling drones/limpets
        self.money_gained_sellmodules = 0 # how much money you've received from selling ship modules
        self.money_gained_shipsell = 0 # how much money you've made from selling your entire ship. This might include its modules, I'm not sure.
        self.money_gained_powerplaysalary = 0 # how much money you've made from collecting powerplay salary
        self.money_gained_bounty = 0 # how much money you've made from turning in bounty vouchers. This is not how much money people owe you for killing people.
        self.money_gained_exploration = 0
        self.money_gained_exploration_bonus = 0 # how much bonus money you've made from being the first to discover a place
        self.money_gained_unknown = 0 # Money that you've received outside of events somehow. When you start the game, you have 1000 credits in your account that you didn't "earn"
        self.money_gained_search_and_rescue = 0 # how much money you've made selling things to the search and rescue store
        ### SPENDING MONEY
        self.money_spent_commodities = 0 # how much money you've spent on commodities
        self.money_spent_fines = 0  # how much money in fines you've paid
        self.money_spent_legacyfines = 0
        self.money_spent_ammo = 0 # how much money you've spent on ammo
        self.money_spent_drones = 0 # how much money you've spent on drones/limpets
        self.money_spent_explorationdata = 0 # how much money you spent on exploration data
        self.money_spent_tradedata = 0 # how much you've spent on trade data
        self.money_spent_crewhire = 0 # do I really have to keep commenting these?
        self.money_spent_fetchremotemodule = 0 # how much you've spent on moving a module from one system to another
        self.money_spent_moduleretrieve = 0 # how much money you've spent retrieving modules. I don't think this ever costs anything in the game currently.
        self.money_spent_modulestore = 0 # I don't think this ever costs money either.
        self.money_spent_modulebuy = 0 # how much money you've spent on modules
        self.money_spent_powerplayfasttrack = 0 # I haven't done powerplay yet lol
        self.money_spent_fuel = 0 # how much money you've spent refueling your ship, not buying hydrogen fuel for other people
        self.money_spent_repairs = 0 # how much money you've spent repairing your ship(s)
        self.money_spent_restockvehicle = 0 # Restocking vehicles such as SRV and maybe fighter
        self.money_spent_rebuyship = 0 # what you've spent rebuying your ship/modules after a death
        self.money_spent_buyship = 0 # what you've spent buying new ship(s)
        self.money_spent_transfership = 0 # what you've spent paying to have your ship moved to your current system
        self.money_spent_engineer_contribution = 0
        self.money_spent_mission_donations = 0 # how much money you've spent on donation/charity missions
        self.materials_physical_spent_synthesis = 0 # how many materials you've spent on synthesis.
        ### VOUCHERS # voucher_money_* is how much money in vouchers that you've received, but NOT necessarily cashed in. This can be used to tell how much money was wasted by not being able to cash in vouchers.
        # voucher_count_* is just the number of these vouchers you've received, but again not necessarily turned in
        self.voucher_count_datalink = 0
        self.voucher_money_datalink = 0
        self.vouchers_redeemed_bounty = 0 # how many times you've redeemed vouchers
        self.vouchers_redeemed_combatbond = 0
        self.vouchers_redeemed_scannable = 0
        self.vouchers_redeemed_settlement = 0
        self.vouchers_redeemed_trade = 0
        ### CARGO
        self.cargo_gained_haulage = 0# how much cargo you've taken into your ship from missions
        self.cargo_gained_scooped = 0 # how much cargo you've picked up in open space or transferred from your SRV... I think
        self.cargo_gained_mission_reward = 0 # commodity rewards from doing missions
        self.cargo_gained_bought_commodity = 0 # how much cargo you've bought from markets
        self.cargo_delivered = 0  # How much cargo was delivered as part of a mission
        self.cargo_sold = 0  # how much cargo was sold to a normal market
        self.cargo_sold_illegal = 0  # How much cargo was sold on the black market
        self.cargo_sold_drones = 0 # how many limpets you've sold
        self.cargo_sold_search_and_rescue = 0 # how much cargo you've sold to the search and rescue store
        self.cargo_ejected = 0  # how much cargo has been jettisoned/abandoned/discarded
        self.cargo_delivered_engineer = 0 # how much cargo has been delivered to an engineer
        self.cargo_gained_powerplay = 0 # how much cargo you've received from PowerplayCollect
        self.cargo_delivered_powerplay = 0
        self.cargo_lost_death = 0 # how much cargo you've lost from dying
        self.materials_physical_gained = 0 # How much Raw or Manufactured material you've taken onto your ship
        self.materials_data_gained = 0
        self.materials_physical_discarded = 0
        self.materials_data_discarded = 0
        self.materials_data_spent_engineer = 0 # how many data materials you've spent on engineering
        self.materials_physical_spent_engineer = 0  # how many raw or manufactured materials you've spent on engineering
        ### COMBAT & DAMAGE
        self.kills_bounty = 0 # how many bounties you got from killing a ship
        self.kills_capitalship = 0 # Well aren't you a fuckin' badass
        self.kills_faction_bond = 0
        self.kills_pvp = 0 # how many real players you've killed
        self.cockpit_breaches = 0 # how many times you've had a cockpit breach
        self.deaths = 0 # How many times you've died in the game, not necessarily from combat. I sorted this here because fuck you, that's why
        self.interdictions_escaped_npc = 0 # how many times you've escaped from an npc's interdictions
        self.interdictions_escaped_player = 0
        self.interdictions_submitted_npc = 0
        self.interdictions_submitted_player = 0
        self.interdictions_escapes_failed_npc = 0 # How many times an enemy succesfully interdicted you; how many times you failed to escape
        self.interdictions_escapes_failed_player = 0
        self.interdictions_committed_success_npc = 0 # how many times YOU have succesfully interdicted an npc
        self.interdictions_committed_success_player = 0
        self.interdictions_committed_fail_npc = 0
        self.interdictions_committed_fail_player = 0
        self.heat_warnings = 0 # how many times you've had a heat warning
        self.heat_damage_taken = 0 # how many times you've taken heat damage
        self.hull_damage_taken_fifths_fuzzy = 0 # How much hull damage your ship has taken. This number isn't very accurate because the game only generates a HullDamage event after you take 20% hull damage. if you consistently take 19% damage and
        # then repair your ship, then all that damage will never be counted.
        self.reboot_repairs = 0 # how many times you've done a reboot and repair sequence
        self.self_destructed = 0
        self.shields_depleted = 0 # How many times your shields have been completely depleted. This only counts when it happens from combat.
        self.shields_regained = 0 # this counts if from combat or charging them back up after silent running.
        ### MISSIONS & COMMUNITY GOALS & POWERPLAY
        self.missions_abandoned = 0 # How many missions you've abandoned
        self.missions_accepted = 0
        self.missions_completed = 0
        self.missions_failed = 0
        self.missions_redirected = 0 # how many times a mission has redirected you to a different destination than they originally gave you
        self.missions_passengers_failed = 0 # How many individuals have left your ship because you failed their passenger mission
        self.missions_passengers_delivered = 0  # How many individuals have been delivered to their destination by you
        self.community_goals_discarded = 0 # how many community goals you've discarded
        self.community_goals_joined = 0
        self.community_goals_completed = 0
        self.community_goals_scientific_research = 0 # how many times you've done scientific research
            # powerplay cargo stuff is up in cargo
        self.powerplay_defect = 0 # how many times you've defected from a powerplay power
        self.powerplay_join = 0 # how many times you've joined a powerplay power
        self.powerplay_leave = 0
        self.powerplay_salaries_redeemed = 0 # how many times you've redeemed a powerplay salary
        self.powerplay_vote = 0 # how many times you've voted
        self.powerplay_votes_casted = 0 # how many votes you've casted
        self.powerplay_vouchers = 0 # I don't really know what this is yet
        ### CREW
        self.crew_hired = 0
        self.crew_fired = 0
        self.crew_ended = 0 #how many multicrew sessions were ended. I'm not sure if this is useful or not.
        self.crew_ended_crime = 0 # How many multicrew sessions were ended because of a crime being comitted
        self.crews_joined = 0 # how many times you've joined someone else's multicrew
        self.crew_kicked = 0 # how many times a crew member has been kicked from your multicrew session
        self.crew_kicked_crime = 0 # ^^ due to crime
        self.crew_quit = 0 # how many times you've quit from a crew
        ### SCANS
        self.scanned_datalinks = 0
        self.scanned_tourist_beacons = 0
        self.scanned_data_points = 0
        self.nav_beacons_scanned = 0
        ### TRAVEL
        self.visited_systems = DestinationTracker()
        self.visited_stations = DestinationTracker()
        self.docking_cancelled = 0 # how many times docking has been cancelled
        self.fuel_scooped = 0 # how much fuel you've scooped in tons
        self.fuel_scoop_started = 0 # how many times you've initiated a fuel scoop. If you get too hot and fly away and back, that counts as 2 fuel scoops
        self.neutron_boosts = 0 # how many times you've gotten a JetConeBoost from a neutron star
        self.neutron_boosts_value = 0 # how much boost you've received from your JetConeBoosts
        self.neutron_boost_damages = 0 # how many times you've damaged your ship doing a neutron star boost
        self.fsd_jump_started = 0 # how many times you've fired up the FSD to enter supercruise or hyperspace. This still counts if the jump is aborted before it happens.
        self.supercruise_entered = 0
        self.supercruise_exited = 0
        ### DOCKING
        self.docking_denied = 0
        self.docking_granted = 0 # how many times docking has been granted
        self.docking_requested = 0
        self.docking_timeout = 0 # how many times your granted docking request has timed out
        self.fighter_docked = 0  # how many times a fighter has been docked in your ship. Not necessarily flown by you.
        self.fighter_launched_player = 0 # how many times you've launched in a fighter or a player has launched a fighter in your ship
        self.fighter_launched_npc = 0 # how many times you've launched an NPC in a fighter from your ship.
        self.srv_docked = 0  # how many times your SRV has docked
        self.srv_launched_player = 0 # how many times a player-controlled srv has been launched
        self.srv_launched_npc = 0 # ^^ for NPCs. This isn't actually implemented in the game yet
        self.planet_liftoff_player = 0 # how many times you've lifted off from a planet's surface
        self.planet_liftoff_npc = 0 # how many times you've dismissed your ship, whether it has an NPC pilot or it's unmanned
        self.planet_landings = 0 # how many times you've landed on a planet
        self.uss_drops = 0 # how many times you've dropped out at an Unknown Signal Source
        self.docking_undocked = 0 # how many times you've left a landing pad
        ### ENGINEERING
        self.engineer_modifications_applied = 0 # How many times you've applied a modification from an engineer
        #self.engineer_materials_spent = 0 # How many material items you've spent engineering
        self.engineers_invited = 0 # how many engineers have invited you
        self.engineers_unlocked = 0 # how many engineers you've unlocked
        self.engineers_known = 0 # how many engineers you know about
        self.engineers_rank_gained = 0 # How many times you've ranked all engineers to a new level
        self.engineer_bounty_spent = 0 # how many bounties you've given to engineers to unlock them
        ### RANK
        self.rank_gained_combat = 0
        self.rank_gained_trade = 0
        self.rank_gained_explore = 0
        self.rank_gained_empire = 0
        self.rank_gained_federation = 0
        self.rank_gained_cqc = 0
        # self.engineer_contribution = 0 Nope, this is up in SPENDING MONEY
        ### MISC
        self.crimes_committed = 0 # how many crimes you've committed
        self.fines_gained = 0 # how many times you've been fined
        self.fines_legacy_paid = 0 # how many times you've paid off a legacy fine
        self.materials_discovered = 0 # How many new materials you've discovered this session
        self.fuel_bought = 0 # how much total fuel you've bought, not the cost of it
        self.cleared_saves = 0 # how many times you've cleared out your saved game
        self.new_commander_created = 0
        self.games_loaded = 0 # How many times you've loaded into the game
        self.modules_stored = 0 # how many times you've stored a module. When mass storing modules, each module counts as 1.
        self.mined_elements = RefineryTracker()
        self.modules_bought = 0 # how many modules you've bought
        self.modules_retrieved = 0 # how many times you've taken a module out of storage, not necessarily paid to move it
        self.modules_sold = 0
        self.modules_sold_remote = 0
        self.modules_stored = 0 # how many times you've stored a module
        self.modules_swapped = 0
        self.music_changed = 0 # how many times the music started or changed. This event is new to 2.4
        self.messages_received_npc = 0 # how many messages you've received in the npc channel
        self.messages_received_player = 0
        self.messages_received_local = 0
        self.messages_received_wing = 0
        self.messages_received_voicechat = 0
        self.messages_sent = 0
        self.bankruptcy_declared = 0
        self.stellar_object_scanned = 0 # how many times you've gotten a detailed scan of a star or planet
        ### commodity market galactic average stats.
        # This is how much more potential money you made by selling something above the galactic average. If you sold below average, record the difference between how much you got and how
        # much you could have got if you had sold for the average. If the average was 0, don't add to these totals, that's cheating. These are NOT added to getTotalMoneyGained() since money_gained_market is also counting this.
        self.money_over_market_galactic_average = 0
        self.money_under_market_galactic_average = 0
        self.scanned_for_cargo = 0 # how many times another ship has scanned you looking for cargo
        self.scanned_for_crime = 0
        self.screenshots_taken = 0
        self.ship_name_set = 0 # how many times you've set or changed a ship's name
        self.ships_bought = 0
        self.ships_sold = 0
        self.ships_swapped = 0
        self.ships_transferred = 0
        self.synthesized_something = 0
        self.wing_invites_sent = 0
        self.wings_joined = 0
        self.wings_left = 0
    def addStat(self, journalentry, attribute, amount):
        "Add amount to self.attribute if we're recording. journalentry is the full journalentry so we can extract the timestamp. return nothing"
        if self.isrecording:
            if not self.starttime:
                self.starttime = timestamp_to_datetimeobj(journalentry['timestamp'])
            self.latesttime = timestamp_to_datetimeobj(journalentry['timestamp'])
            setattr(self, attribute, getattr(self, attribute) + amount)
            #if DEBUG:
                # if 'money' in attribute:
                #     print journalentry
                # if self.getNetMoneyChange() < 0:
                #     print self.getNetMoneyChange()
                #pass
    def startRecording(self):
        "Start tracking stats."
        self.isrecording = True # Only record stats in this session if this is True.
        # There used to be more stuff in this method, I swear
    def getTotalMoneyGained(self):
        "return how much money you've earned from everything, regardless of what you've spent."
        return sum((self.money_gained_missions, self.money_gained_communitygoal, self.money_gained_market, self.money_gained_blackmarket, self.money_gained_selldrones, self.money_gained_sellmodules, self.money_gained_powerplaysalary,
                        self.money_gained_bounty, self.money_gained_shipsell, self.money_gained_exploration, self.money_gained_exploration_bonus, self.money_gained_unknown, self.money_gained_search_and_rescue))
    def getTotalMoneySpentWithoutModulesOrShips(self):
        "return how much money you've spent on everything except modules or ships. This number will always be >= 0! Positive numbers only!"
        return sum((self.money_spent_commodities,
                    self.money_spent_fines,
                    self.money_spent_legacyfines,
                    self.money_spent_ammo,
                    self.money_spent_drones,
                    self.money_spent_explorationdata,
                    self.money_spent_tradedata,
                    self.money_spent_crewhire,
                    self.money_spent_fetchremotemodule,
                    self.money_spent_moduleretrieve,
                    self.money_spent_modulestore,
                    self.money_spent_powerplayfasttrack,
                    self.money_spent_fuel,
                    self.money_spent_repairs,
                    self.money_spent_restockvehicle,
                    self.money_spent_rebuyship,
                    self.money_spent_transfership,
                    self.money_spent_engineer_contribution,
                    self.money_spent_mission_donations,
                    ))
    def getTotalMoneySpent(self):
        "return how much money you've spent on everything. This number will always be >= 0! Positive numbers only!"
        return sum((self.getTotalMoneySpentWithoutModulesOrShips(), self.money_spent_buyship, self.money_spent_modulebuy,))
    def getNetMoneyChange(self):
        "return how much your money has changed during this session. If this number is negative, you've spent more than you've earned."
        return self.getTotalMoneyGained() - self.getTotalMoneySpent()
    def getNetMoneyChangeWithoutModulesOrShips(self):
        "return how much your money has changed during this session, but leave out ships and module purchases. If this number is negative, you've spent more than you've earned."
        return self.getTotalMoneyGained() - self.getTotalMoneySpentWithoutModulesOrShips()
    def getTotalCargoSold(self):
        "Get the total amount of cargo sold to both regular and black markets"
        return sum((self.cargo_sold, self.cargo_sold_illegal, self.cargo_sold_search_and_rescue))
    def getTotalCargoGained(self):
        "return the total amount of cargo that's gone into your ship"
        return sum((self.cargo_gained_haulage, self.cargo_gained_powerplay, self.cargo_gained_scooped, self.cargo_gained_mission_reward, self.cargo_gained_bought_commodity))
    def getTotalMoneyGainedFromCommoditiesSold(self):
        "Get the total amount of money made from selling commodities"
        return self.money_gained_market + self.money_gained_blackmarket
    def getTotalGalacticAverageSales(self):
        """return the total amount of money from selling commodities compared to the galactic average. If this number is negative, the difference between how much you sold stuff for and the galactic average is greater than how much money you made
        selling commodities above the galactic average."""
        return self.money_over_market_galactic_average - self.money_under_market_galactic_average
    def getScorePerHour(self, attribute):
        """calculate how much attribute per hour you made based on how long this session has been recording.
        attribute is a string of the attribute to read or method to execute.
        returns an int"""
        # First find out how long this session has been running
        try:
            tdelta = self.latesttime - self.starttime
        except TypeError: # one of the times was None
            return 0
        try: # try calling it as a method
            amount = getattr(self, attribute)()
        except TypeError: # read the variable name
            amount = getattr(self, attribute)
        #if DEBUG:
        #    print '\n', tdelta, 'lapsed.'
        #    print "%s: %s" % (attribute, amount)
        #    print round((amount / tdelta.total_seconds()) * 60**2, 2)
        try:
            return round((amount / tdelta.total_seconds()) * 60**2, 2)
        except ZeroDivisionError:
            return 0

class Missions(dict):
    "This is a dict object with a few extra methods just for missions."
    maxmissions = 20 # No enforcement on this limit in this dict
    def purgeExpired(self):
        "Purge expired missions and call them failed. return the number of purged missions."
        total = 0
        for k in self.keys():
            past = timestamp_to_datetimeobj(self[k]['Expiry']) < datetime.datetime.utcnow()
            if past:
                #if DEBUG:
                #    print "Removing mission: %s < %s" % (self[k]['Expiry'], datetime.datetime.utcnow().isoformat())
                del self[k]
                total += 1
        return total
    def getSortedDestinations(self):
        "return a list of destinations that your missions are going to. The list is the same format as DestinationTracker.getMostVisited() because that's what used."
        # Create a new dict of missions and change DestinationSystem to StarSystem and DestinationStation to StationName for use with DestinationTracker()
        d = DestinationTracker()
        for mission in self.keys():
            m = self[mission].copy()
            try:
                m['StarSystem'] = m['DestinationSystem']
            except KeyError: # Donation missions do not have destinations
                m['StarSystem'] = m['StationName'] = 'None'
            else:
                try:
                    m['StationName'] = m['DestinationStation']
                except KeyError: # sometimes a mission will have a DestinationSystem, but no DestinationStation
                    m['StationName'] = 'None'
            d.addPlace(m)
        return d.getMostVisited()
    def getSortedRewards(self):
        "return a list of your missions sorted by highest reward. The list contains tuples of [(int(rewardamount), missionid), ...]"
        datboi = []
        for m in self:
            try:
                datboi.append((self[m]['Reward'], m))
            except KeyError: # some missions don't give you credits so they don't have a Reward:
                datboi.append((0, m))
        datboi.sort(reverse=True)
        return datboi
    def getSortedExpiration(self):
        "return a list of your missions sorted by soonest expiring mission: [(datetime(time), missionid), ...]"
        openbob = []
        for m in self:
            try:
                openbob.append((datetime.datetime.strptime(self[m]['Expiry'], "%Y-%m-%dT%H:%M:%SZ"), m))
            except KeyError: # in some rare circumstances, missions don't have an expiry: {u'TargetType': u'$MissionUtil_FactionTag_Politician;', u'Name': u'Mission_Assassinate_Illegal_Lockdown', u'DestinationStation': u'Lopez de Haro Colony', u'Faction': u'Dragons of LP 726-6', u'MissionID': 225777778, u'timestamp': u'2017-10-13T04:46:10Z', u'Influence': u'Med', u'TargetFaction': u'Liberals of NLTT 19808', u'LocalisedName': u'Take out Politician: Noel T Bilson', u'Reputation': u'Low', u'DestinationSystem': u'NLTT 19808', u'Reward': 584868, u'TargetType_Localised': u'Politician', u'event': u'MissionAccepted', u'Target': u'Noel T Bilson'}
                openbob.append((datetime.datetime.now() + datetime.timedelta(days=365), m)) # set the expiration date to this mission to about 1 year from now so it appears to be one of the last to expire
        openbob.sort()
        return openbob

class PhysicalMaterial(dict):
    "This is a dict object with a method that gets you the total amount of materials that you have."
    maximum = 1000
    def getTotalAmount(self):
        return sum([x['Count'] for x in self.values()])

class DataMaterial(dict):
    "This is a dict object with a method that gets you the total amount of materials that you have."
    maximum = 500
    def getTotalAmount(self):
        return sum(self.values())

class Cargo(dict):
    "A dict with a method that gets you the total amount of cargo."
    def getTotalAMount(self):
        return sum([x['amount'] for x in self.values()])

class DestinationTracker():
    "This object tracks destinations that you fly to. This is used when jumping to systems and docking at stations."
    def __init__(self):
        self.history = [] # This is a list of the destinations that you've visited in order from oldest to newest
        self.count = {} # This is a dictionary of places to times visited.
        # in the case of tracking systems visited, the dict will look like {'SystemName': int(timesvisited), ...}. When tracking stations docked at, it'll look like {'SystemName': {'StationName': int(timesvisited), ...}, ...}
    def addPlace(self, journalentry):
        "Add one place. journalentry is a journalentry from either the Docked or FSDJump events. return nothing."
        # { "timestamp":"2017-08-31T04:20:07Z", "event":"Docked", "StationName":"Bode Hub", "StationType":"Outpost", "StarSystem":"Wu Guinagi", "StationFaction":"Ajoku Industries", "FactionState":"Boom", "StationGovernment":"$government_Corporate;", "StationGovernment_Localised":"Corporate", "StationAllegiance":"Empire", "StationEconomy":"$economy_Industrial;", "StationEconomy_Localised":"Industrial", "DistFromStarLS":754.817932 }
        # { "timestamp":"2017-08-31T04:46:46Z", "event":"FSDJump", "StarSystem":"HIP 10716", "StarPos":[53.063,-226.188,-60.938], "SystemAllegiance":"Empire", "SystemEconomy":"$economy_Military;", "SystemEconomy_Localised":"Military", "SystemGovernment":"$government_Corporate;", "SystemGovernment_Localised":"Corporate", "SystemSecurity":"$SYSTEM_SECURITY_low;", "SystemSecurity_Localised":"Low Security", "JumpDist":11.867, "FuelUsed":3.155944, "FuelLevel":12.217494, "Factions":[ { "Name":"HIP 10716 Vision PLC", "FactionState":"Lockdown", "Government":"Corporate", "Influence":0.242242, "Allegiance":"Empire", "PendingStates":[ { "State":"Boom", "Trend":1 }, { "State":"CivilUnrest", "Trend":0 } ], "RecoveringStates":[ { "State":"Election", "Trend":0 } ] }, { "Name":"Ahaut Front", "FactionState":"Boom", "Government":"Dictatorship", "Influence":0.251251, "Allegiance":"Empire", "PendingStates":[ { "State":"Bust", "Trend":0 }, { "State":"CivilUnrest", "Trend":-1 } ] }, { "Name":"Wu Guinagi Crimson Creative Corp", "FactionState":"Boom", "Government":"Corporate", "Influence":0.112112, "Allegiance":"Empire", "PendingStates":[ { "State":"War", "Trend":0 } ] }, { "Name":"Ajoku Industries", "FactionState":"Boom", "Government":"Corporate", "Influence":0.196196, "Allegiance":"Empire", "PendingStates":[ { "State":"CivilUnrest", "Trend":0 } ], "RecoveringStates":[ { "State":"Election", "Trend":0 } ] }, { "Name":"Tewinicnii Vision Corporation", "FactionState":"Boom", "Government":"Corporate", "Influence":0.023023, "Allegiance":"Empire", "PendingStates":[ { "State":"Bust", "Trend":1 }, { "State":"CivilUnrest", "Trend":0 }, { "State":"Retreat", "Trend":0 } ] }, { "Name":"Nobles of HIP 10716", "FactionState":"Bust", "Government":"Feudal", "Influence":0.079079, "Allegiance":"Independent", "PendingStates":[ { "State":"Boom", "Trend":0 }, { "State":"War", "Trend":0 } ], "RecoveringStates":[ { "State":"CivilUnrest", "Trend":0 } ] }, { "Name":"Lords of the DarkStar Imperium", "FactionState":"Boom", "Government":"Dictatorship", "Influence":0.096096, "Allegiance":"Empire" } ], "SystemFaction":"HIP 10716 Vision PLC", "FactionState":"Lockdown" }
        self.history.append(journalentry)
        try: # first try incrementing an existing station visit by 1
            self.count[journalentry['StarSystem']][journalentry['StationName']] += 1
        except KeyError: # StarSystem or StationName did not exist
            try: # try incrementing an existing system visit by 1
                self.count[journalentry['StarSystem']] += 1
            except (KeyError, TypeError): # Now we know that this is either a newly visited system or station. TypeError was raised from trying to {} += 1
                try: # try creating a newly visited station where the StarSystem already exists:
                    self.count[journalentry['StarSystem']][journalentry['StationName']] = 1
                except KeyError: # Raised by StationName not being in journalentry OR the StarSystem not existing yet.
                    try: # try creating a new system with a newly visited station:
                        self.count[journalentry['StarSystem']] = {journalentry['StationName']: 1}
                    except KeyError: # The only thing left to do is to create a newly visited system
                        self.count[journalentry['StarSystem']] = 1
    def getMostVisited(self):
        """"return an ordered list of the most visited places in order from most visited to least visited.
        The list contains tuples of (int(timesvisited), 'SystemName') in the case of tracking systems.
        The list is tuples of (int(timesvisited), 'SystemName', 'StationName')
        """
        ordered = [(y, x) for x, y in self.count.items()]
        try:
            int(ordered[0][0])
        except IndexError: # self.count is empty
            return ordered
        except TypeError: # we built ordered into a list of ({'StationName': int(visits), ...,} 'SystemName'). Change it:
            newordered = []
            for item in ordered:
                for station in item[0]:
                    newordered.append((item[0][station], item[1], station))
            return sorted(newordered, reverse=True)
        return sorted(ordered, reverse=True)
    def getTotalVisited(self):
        "Count the total number of places visited, return an int"
        return len(self.history)

class RefineryTracker():
    "This object tracks which types of precious minerals you've refined from mining and how much of each you've mined."
    def __init__(self):
        self.mined = {} # a dict of {'ElementName':int(amount), ...}
    def __len__(self): # TODO: change this whole object to a dict subclass? this __len__ seems stupid and hacky
        return len(self.mined)
    def addElement(self, name):
        "add a single mined element. name is the name of the element."
        try:
            self.mined[name.lower()] += 1
        except KeyError:
            self.mined[name.lower()] = 1
    def getMostMined(self):
        """"return an ordered list of the most mined elements in order from most mined to least mined.
        The list contains tuples of [(int(amountmined), 'ElementName'), ...]
        """
        ordered = [(y, x) for x, y in self.mined.items()]
        try:
            ordered[0][0]
        except IndexError: # self.mined is empty
            return ordered
        return sorted(ordered, reverse=True)
    def getTotalMined(self):
        "return the total amount of all things mined."
        return sum(self.mined.viewvalues())

class SpaceShip():
    """
    This represents an instance of your ship and everything we can find out about its state through the journal logs.
    playername is the name of the player that we'll track. If left blank, the first player encountered is used.
    journaldir is the directory where all the journal logs are. If left blank, the default location on Windows is used.
    Most of the magic happens in parseJournal(). When another program subclasses this object, it should run parseJournal and then act on the journal entries that are returned, before
    passing that data back to handleEvents so this object can update the status of your ship. Alternatively, your program can pass the output of parseJournal straight to handleEvents
    and then just read the state of SpaceShip's variables.
    This object represents data a little differently than the journal does. The journal entries typically use lists of dicts, with each property of the item being a key. For example,
    the Cargo event lists like this: [ { "Name":"domesticappliances", "Count":24 }, ... ] So each item in this list is an unnamed dictionary, each with a name property. I think that
    makes things more difficult, so I generally will use dicts where the unique name is the key. For example, that previous example would be stored like this:
    { 'domesticappliances': 24}, ... }
    """
    def __init__(self, playername='', journaldir=None):
        if not journaldir:
            try:
                self.journaldir = os.path.join( os.environ['HOMEDRIVE'], os.environ['HOMEPATH'], 'Saved Games', 'Frontier Developments', 'Elite Dangerous' )
            except KeyError: # running on unix
                raise NoLogsFound("No log dir was specified and you're probably not using Windows.")
        else:
            self.journaldir = journaldir
        self.timestamp = None # This is the timestamp from the latest event that has been processed.
        self.shiptype = None
        self.shipname = None
        self.playername = playername
        self.wrongplayer = False # This is used to signal that another player's game has been loaded so we don't add their stats to your ship.
        self.rank_combat = 0
        self.rank_trade = 0
        self.rank_explore = 0
        self.rank_empire = 0
        self.rank_federation = 0
        self.rank_cqc = 0
        self.cargo = Cargo() # Your regular current cargo. Consists of a dictionary of cargonames to the amount of that item and the amount of it that is haulage and stolen: { 'domesticappliances': {'amount':PositiveInt(24), 'stolen':PositiveInt(4),
        # 'haulage':PositiveInt(0)}}, ... }
        # All cargo names MUST be sanitized first, read the comments in sanitizeCargo to see why.
        # maximum physical materials is 1000
        # maximum data materials is 500
        self.materials = PhysicalMaterial() # dictionary of material names to the amount and type: { 'nickel': {'Type':'Raw', 'Count':PositiveInt(9)}, ... }
        self.datamaterials = DataMaterial() # AKA Encoded materials, names to count: {'embeddedfirmware': PositiveInt(9), ... } Data is split off from Materials since Data has its own storage & maximum amount
        self.missions = Missions() # a special dict of your missions, organized as a dict of missionid to the full line from the log minus the missionid: {MissionID: { "event":"MissionAccepted", "Faction":"Ahaut Front", ...}, }
        self.passengers = {} # organized as a dict of missionid to a normalized dict of passenger info: {MissionID: { "Type":"Business", "VIP":false, "Wanted":false, "Count":5 }, ...} }
        # "Name":"Chain_PlanetaryIncursions",
        # "TargetFaction":"Traditional Wu Guinagi Bureau", "DestinationSystem":"HIP 10716", "DestinationStation":"Morgan Depot", "Expiry":"2017-09-04T13:08:31Z", "Influence":"High", "Reputation":"Med" }
        self.moneycurrentbalance = 0 # Your current amount of funds
        self.ignore_next_docked = False # This is a flag set by Location and used by Docked. Before I implemented this, starting a game docked somewhere would count as a visited station.
        # self.sessionstats is a dict of {'sessionname': sessionobject} dictionaries.
        self.sessionstats = {}
        for name in 'oldest', 'game', 'appstart':
            self.sessionstats[name] = SessionStat(name)
        self.sessionstats['oldest'].startRecording() # Turn on the longest-running stats
        #if DEBUG:
        #    self.sessionlines = [] # used for debugging money_gained_unknown
    def parseJournal(self, startup=False):
        """
        This method parses the journal up until self.timestamp is found.
        If startup=True, start from the beginning of all logs. If it's False, start at the newest log and work backwards until we find the last timestamp.
        if journaldir is a zip file, parse that and assume startup=True
        return a list of event dicts ordered from oldest to newest. This method also updates self.timestamp. NoLogsFound exception is raised if no log files were found.
        """
        if self.journaldir.lower().endswith('.zip'):
            import zipfile
            # just assume that it's actually zip at this point since it was already checked in main
            self.journaldir = zipfile.ZipFile(self.journaldir)
            filelist = sorted(self.journaldir.namelist())
            is_zip = True
            startup = True
        else:
            is_zip = False
            try:
                filelist = sorted( os.listdir( self.journaldir ) ) #sorted is probably redundant
            except (WindowsError, OSError), e:
                if e[1] in ('No such file or directory', 'The system cannot find the path specified'):
                    print "Invalid log location specified!"
                raise
            if not filelist:
                raise NoLogsFound
        if startup:
            filelist.reverse() # start from the oldest log
        journalentries = [] # a list of journal entries ordered from oldest to newest.
        try:
            while True: # Keep reading through log files until either the right timestamp. If startup=True, we start at the beginning of the logs and go forward.
                try:
                    currentfile = filelist.pop()
                except IndexError: # No more log files to parse
                    raise StopIteration
                lineno = 0
                if startup:
                    if is_zip:
                        iterate_this = self.journaldir.open(currentfile).readlines()
                    else:
                        iterate_this = open( os.path.join( self.journaldir, currentfile ) )
                    for line in iterate_this:
                        lineno += 1
                        try:
                            j = loads(line, strict=False)
                        except ValueError:
                            print "Skipping malformed line in %s, line: %s" % (currentfile, lineno),
                            if not startup:
                                print "from the end"
                            else:
                                print
                            # if DEBUG:
                            #     print line
                            continue
                        journalentries.append( j )
                else: # work through the log file backwards. zip files aren't supported here
                    for line in reverse_readline( os.path.join( self.journaldir, currentfile ) ):
                        try:
                            journalentry = loads( line )
                        except ValueError, e: # sometimes this error happens because the log file is read while the game is in the middle of writing it. We should ignore those errors and continue
                            if not e[0].startswith('Expecting') or not e[0].startswith('No JSON object'):
                                raise
                            raise StopIteration
                        if self.timestamp >= journalentry['timestamp']: # if we've caught up to the current timestamp...
                            raise StopIteration
                        else:
                            journalentries.insert( 0, journalentry )
        except StopIteration: # I'm sure this is bad form, but should I really create my own exception for this?
            try:
                self.timestamp = journalentries[-1]['timestamp'] # set the timestamp to the most recent event read
            except IndexError: # raised when trying to get the last journal entry and there was none
                pass
            return journalentries
    def handleEvents(self, journalentries):
        "Parse journalentries which is a list of journalentry dicts ordered from oldest to newest. This method actually passes each journal entry onto a specialized helper method which updates the ship's state variables. return nothing."
        for journalentry in journalentries:
            try:
                #if DEBUG:
                #   print '\n\nJournalEntry:\n' + str(journalentry) + '\n'
                method = getattr( self, '_SpaceShip__%s%s' % ('handleEvent_', journalentry['event']) )
            except AttributeError:
                print "Unknown log event found. Please report this to the developer. Log event is:"
                print journalentry
                raise Exception
            if self.wrongplayer and journalentry['event'] != 'LoadGame': # do not call any methods except for LoadGame to see if we came back to the correct player
                return
            method(journalentry)
            #if DEBUG: # this is for debugging unknown money
            #    for k in journalentry:
            #        try:
            #            int(journalentry[k])
            #        except (ValueError, TypeError):
            #            pass
            #        else:
            #            self.sessionlines.append(str(journalentry))
            #            self.sessionlines.append('money is now %s' % format(self.moneycurrentbalance, ','))
            #            break
    def __addSessionStat(self, journalentry, attribute, amount=1):
        "Add something to the session tracker. key is self.sessionstats[key], value must be a positive number and is 1 by default. return nothing."
        assert amount >= 0
        for session in self.sessionstats:
            self.sessionstats[session].addStat(journalentry, attribute, amount)
    def __addSessionVisitedStat(self, journalentry):
        "Add a visited place to the DestinationTracker within a SessionStat. return nothing."
        for session in self.sessionstats:
            if self.sessionstats[session].isrecording:
                if journalentry[u'event'] == 'Docked':
                    attribute = 'stations'
                elif journalentry['event'] == 'FSDJump':
                    attribute = 'systems'
                else:
                    raise Exception("WTF someone used __addSessionVisitedStat incorrectly")
                visited = getattr(self.sessionstats[session], ''.join(('visited_', attribute)))
                visited.addPlace(journalentry)
    def __addSessionRefineryStat(self, elementname):
        "Add a single element to the RefineryTracker within a SessionStat. return nothing."
        for session in self.sessionstats:
            if self.sessionstats[session].isrecording:
                self.sessionstats[session].mined_elements.addElement(sanitizeCargo(elementname))
    def __gainMoney(self, journalentry, type, amount):
        """Add money to our sessions and our current live total.
        journalentry is the full journalentry
        type is a str which denotes how you gained this money. It must match a variable in SessionStat.money_gained_type
        amount is an int of how much money, always positive
        return nothing
        """
        self._SpaceShip__addSessionStat(journalentry, 'money_gained_' + type, amount)
        self.moneycurrentbalance += amount
    def __loseMoney(self, journalentry, statname, amount):
        """Add spent money to our sessions and our current live total.
        journalentry is the full journalentry
        statname is a str which denotes how you gained this money. It must match a variable in SessionStat.money_spent_type. money_spent_ is assumed so you should only pass in what's after that.
        amount is an int of how much money, always positive.
        return nothing
        """
        self._SpaceShip__addSessionStat(journalentry, 'money_spent_%s' % statname, amount)
        self.moneycurrentbalance -= amount
    def __gainCargo(self, journalentry, name, amount, statname, haulage=False, stolen=False, nostat=False):
        """Add a single type of cargo to self.cargo.
        journalentry is the full journalentry
        name is a string
        amount is an int
        statname is a string corresponding to a stat name that follows cargo_gained
        haulage indicates that this is cargo you got from taking a mission
        stolen indicates that it is stolen
        nostat indicates that we should not count a stat for this. (I don't care about how much cargo you've taken in from mining since that's already tracked by RefinerTracker)
        update self.cargo and stat trackers and return nothing"""
        if amount == 0: # sometimes missions will give you 0 of something, wtf: {u'Name': u'MISSION_Scan_name', u'DestinationStation': u'Dahm Exchange', u'Faction': u'Quince Creative Holdings', u'MissionID': 175978164, u'timestamp': u'2017-07-23T21:01:36Z', u'CommodityReward': [{u'Count': 0, u'Name': u'CoolingHoses'}], u'DestinationSystem': u'Quince', u'Reward': 1257632, u'event': u'MissionCompleted'}
            return
        name = sanitizeCargo( name )
        try:
            self.cargo[name]['amount'] += amount
        except KeyError:
            self.cargo[name] = {'amount': amount, 'haulage': PositiveInt(0), 'stolen': PositiveInt(0)}

        for attr in 'haulage', 'stolen':
            if locals()[attr]:
                self.cargo[name][attr] += amount
        if not nostat:
            self._SpaceShip__addSessionStat(journalentry, 'cargo_gained_%s' % statname, amount)
    def __loseCargo(self, journalentry, name, amount, statname, haulage=False, stolen=False):
        "Remove a single type of cargo from self.cargo. amount is an int. statname is the name of the stat following cargo_, for example if statname='delivered', add this to the stat cargo_delivered"
        name = sanitizeCargo( name )
        try:
            self.cargo[name]['amount'] -= amount
        except KeyError:
            return # losing something the logs couldn't provide
        if not self.cargo[name]['amount']: # delete this item of cargo if the total amount reached 0
            del self.cargo[name]
        else: # otherwise also remove the haulage & stolen amount if that's what we lost
            for attr in 'haulage', 'stolen':
                if locals()[attr]:
                    self.cargo[name][attr] -= amount
        self._SpaceShip__addSessionStat(journalentry, 'cargo_%s' % statname, amount)
    def __changeMaterial(self, journalentry, type, name, amount, statname):
        """"
        Gain or lose a type of material in storage. This updates internal values and adds to material_*_gained stats, but NOT spent since we dont' know how they were spent
        type must be either Raw, Manufactured, Encoded.
        name is the name of material.
        amount is an int, must be negative if we're losing material.
        discarded is True if it was discarded. If discarded is false and you lost materials, it's assumed to be spent on an engineer
        returns nothing.
        """
        assert amount != 0
        if type == 'Encoded':
            stattype = 'data'
            try: # to increase the existing amount
                self.datamaterials[name.lower()] += amount
            except KeyError: # you didn't have any of this material, set your current amount of this material to amount
                self.datamaterials[name.lower()] = PositiveInt(amount)
            if not self.datamaterials[name.lower()]: # If we now have 0 of this material, delete it
                del self.datamaterials[name.lower()]
        elif type in ('Raw', 'Manufactured'):
            stattype = 'physical'
            try:
                self.materials[name.lower()]['Count'] += amount
            except KeyError:
                self.materials[name.lower()] = {'Type':type, 'Count':PositiveInt(amount)}
            if not self.materials[name.lower()]['Count']:
                del self.materials[name.lower()]
        else:
            raise Exception("Unknown material type. journalentry is: %s" % journalentry)
        # Now add the stats:
        if amount > 0:
            transaction = 'gained'
        else: # we lost materials
            if statname == 'discarded':
                transaction = 'discarded'
                statname = ''
            else:
                transaction = 'spent'
                statname = ''.join(('_', statname))
        self._SpaceShip__addSessionStat(journalentry, 'materials_%s_%s%s' % (stattype, transaction, statname), abs(amount))
    def __removeMission(self, journalentry):
        "Remove and process a single mission. This is shared my _MissionCompleted/Abandoned/Failed. return nothing"
        if journalentry['event'] == 'MissionCompleted':
            try:  # collect the reward
                self._SpaceShip__gainMoney(journalentry, 'missions', journalentry['Reward'])
            except KeyError:  # we didn't get any money from this mission (abandoned and failed missions also use this method to clear them out, you aren't rewarded for failure obviously).
                pass
            try:  # collect commodity reward
                journalentry['CommodityReward']
            except KeyError:  # Didn't get any commodity from the mission
                pass
            else:  # Add the cargo reward
                for cr in journalentry['CommodityReward']:
                    self._SpaceShip__gainCargo(journalentry, cr['Name'], cr['Count'], 'mission_reward')
            try: # remove successfully delivered cargo
                journalentry["Commodity_Localised"]
            except KeyError:  # You did not deliver any cargo as part of this mission
                pass
            else:
                self._SpaceShip__loseCargo(journalentry, journalentry["Commodity_Localised"], journalentry["Count"], 'delivered', haulage=True)
        else: # the mission was either Failed or Abandoned. mark the cargo as stolen and passengers as failed
            try:  # mark haulage cargo from this mission as stolen
                self.missions[journalentry['MissionID']]['Commodity_Localised']
            except KeyError:  # There was no cargo
                pass
            else:
                try:  # see if we have this item in our cargo still:
                    self.cargo[sanitizeCargo(self.missions[journalentry['MissionID']]['Commodity_Localised'])]
                except KeyError:  # we don't have it
                    pass
                else:  # we do have it
                    # Find out how much cargo this mission had, subtract it from from haulage and add it to stolen:
                    self.cargo[sanitizeCargo(self.missions[journalentry['MissionID']]['Commodity_Localised'])]['haulage'] -= self.missions[journalentry['MissionID']]['Count']
                    self.cargo[sanitizeCargo(self.missions[journalentry['MissionID']]['Commodity_Localised'])]['stolen'] += self.missions[journalentry['MissionID']]['Count']
            try: # record passengers that bailed on you
                self.passengers[journalentry['MissionID']]
            except KeyError: # there were no passengers
                pass
            else:
                self._SpaceShip__addSessionStat(journalentry, 'missions_passengers_failed', self.passengers[journalentry['MissionID']]['count'])
        try:  # remove passengers on fail or success, they're friggin' gone dude
            del self.passengers[journalentry['MissionID']]
        except KeyError:
            pass
        try: # finally, delete the mission
            del self.missions[ journalentry['MissionID'] ]
        except KeyError: # tried to remove a mission that we didn't have
            pass # I guess you still get the rewards from a mission that wasn't in your logs from before.
    def __setRank(self, journalentry):
        """"This method sets your current progress and counts it as a gained rank if the event is 'Promotion'
        return nothing
        This was written because Progress and Promotion share the same code."""
        for k in journalentry:
            if k in ('timestamp', 'event'):
                continue
            setattr(self, 'rank_%s' % k.lower(), journalentry[k])
            if journalentry['event'] == 'Promotion':
                self._SpaceShip__addSessionStat(journalentry, 'rank_gained_%s' % k.lower())
    ############## event handler methods ######################
    # All of these methods accept a single journalentry dict, update the SpaceShip object's variables and returns nothing. Many of them don't actually do anything but are still here so they can be easily expanded upon.
    def __handleEvent_ApproachSettlement(self, journalentry):
        # { "timestamp":"2017-08-31T04:58:48Z", "event":"ApproachSettlement", "Name":"Morgan Depot" }
        pass
    def __handleEvent_Bounty(self, journalentry):
        "This is when you kill someone, not when you actually get the money"
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"Bounty", "Rewards": [ {"Faction":"Federation", "Reward":1000 }, {"Faction":"Nuenets Corp.", "Reward": 10280} ],"Target":"Skimmer", "TotalReward":11280, "VictimFaction":"MMU" }
        self._SpaceShip__addSessionStat(journalentry, 'kills_bounty')
    def __handleEvent_BuyAmmo(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"BuyAmmo", "Cost":80 }
        self._SpaceShip__loseMoney(journalentry, 'ammo', journalentry['Cost'])
    def __handleEvent_BuyDrones(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"BuyDrones", "Type":"Drones", "Count":2, "SellPrice":101, "TotalCost":202 }
        self._SpaceShip__loseMoney(journalentry, 'drones', journalentry['TotalCost'])
    def __handleEvent_BuyExplorationData(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"BuyExplorationData", "System":"Styx", "Cost":352 }
        self._SpaceShip__loseMoney(journalentry, 'explorationdata', journalentry['Cost'])
    def __handleEvent_BuyTradeData(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"BuyTradeData", "System":"i Bootis", "Cost":100 }
        self._SpaceShip__loseMoney(journalentry, 'tradedata', journalentry['Cost'])
    def __handleEvent_CapShipBond(self, journalentry):
        # Not sure: { "timestamp":"2016-06-10T14:32:03Z", "event":"CapShipBond", "AwardingFaction":"SomeFaction", "Reward":11280, "VictimFaction":"MMU" }
        self._SpaceShip__addSessionStat(journalentry, 'kills_capitalship')
    def __handleEvent_Cargo(self, journalentry):
        "This event happens at the start of the game to tell you what is in your cargo."
        # { "timestamp":"2017-08-27T04:28:14Z", "event":"Cargo", "Inventory":[ { "Name":"domesticappliances", "Count":24 } ] }
        # Clobber the existing cargo with whatever is here
        oldcargo = self.cargo.copy()
        self.cargo.clear()
        for cargoitem in journalentry['Inventory']:
            cargoitem['Name'] = sanitizeCargo(cargoitem['Name'])
            try:
                oldcargo[cargoitem['Name']]
            except KeyError: # this item wasn't in cargo before
                pass
            else: # copy the haulage and stolen amounts to this cargoitem so it can be added to the new cargo.
                if oldcargo[cargoitem['Name']]['amount'] == cargoitem['Count']: # if the amounts of new cargo is the same as the old...
                    for trait in ('haulage', 'stolen'):
                        cargoitem[trait] = oldcargo[cargoitem['Name']][trait]
            self.cargo[cargoitem['Name']] = {'amount':PositiveInt(cargoitem['Count']), 'haulage':cargoitem.get('haulage', PositiveInt(0)), 'stolen':cargoitem.get('stolen', PositiveInt(0))}
    def __handleEvent_ChangeCrewRole(self, journalentry):
        # {u'timestamp': u'2017-07-03T04:24:16Z', u'Role': u'Idle', u'event': u'ChangeCrewRole'}
        pass
    def __handleEvent_ClearSavedGame(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"ClearSavedGame", "Name":"HRC1" }
        self._SpaceShip__addSessionStat(journalentry, 'cleared_saves')
    def __handleEvent_CockpitBreached(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"CockpitBreached" }
        self._SpaceShip__addSessionStat(journalentry, 'cockpit_breaches')
    def __handleEvent_CollectCargo(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"CollectCargo", "Type":"agriculturalmedicines", "Stolen":false }
        # There is no amount in this entry because it's always 1, you can only scoop one thing at a time
        self._SpaceShip__gainCargo(journalentry, journalentry['Type'], 1, 'scooped', stolen=journalentry['Stolen'])
    def __handleEvent_CommitCrime(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"CommitCrime", "CrimeType":"assault", "Faction":"The Pilots Federation", "Victim":"Potapinski", "Bounty":210 }
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"CommitCrime", "CrimeType":"fireInNoFireZone", "Faction":"Jarildekald Public Industry", "Fine":100 }
        self._SpaceShip__addSessionStat(journalentry, 'crimes_committed')
    def __handleEvent_CommunityGoalDiscard(self, journalentry):
        # No example given, I think it's { "timestamp":"2016-06-10T14:32:03Z", "event":"CommunityGoalDiscard", "Name":"Goalname", "System":"systemname" }
        self._SpaceShip__addSessionStat(journalentry, 'community_goals_discarded')
    def __handleEvent_CommunityGoalJoin(self, journalentry):
        # No example given, I think it's { "timestamp":"2016-06-10T14:32:03Z", "event":"CommunityGoalJoin", "Name":"Goalname", "System":"systemname" }
        self._SpaceShip__addSessionStat(journalentry, 'community_goals_joined')
    def __handleEvent_CommunityGoalReward(self, journalentry):
        # No example given, I think it's { "timestamp":"2016-06-10T14:32:03Z", "event":"CommunityGoalReward", "Name":"Goalname", "System":"systemname", "Reward":1234 }
        self._SpaceShip__gainMoney(journalentry, 'communitygoal', journalentry['Reward'])
        self._SpaceShip__addSessionStat(journalentry, 'community_goals_completed')
    def __handleEvent_Continued(self, journalentry):
        "This signals that the log file grew past 500k lines and a new log file is being started. This can be ignored since this class always reads newest logs and works backwards until the last event is found"
        # Not sure
        pass
    def __handleEvent_CrewAssign(self, journalentry):
        # { "timestamp":"2016-08-09T08:45:31Z", "event":"CrewAssign", "Name":"Dannie Koller", "Role":"Active" }
        pass
    def __handleEvent_CrewFire(self, journalentry):
        # { "timestamp":"2016-08-09T08:46:11Z", "event":"CrewFire", "Name":"Whitney Pruitt-Munoz" }
        self._SpaceShip__addSessionStat(journalentry, 'crew_fired')
    def __handleEvent_CrewHire(self, journalentry):
        # { "timestamp":"2016-08-09T08:46:29Z", "event":"CrewHire", "Name":"Margaret Parrish", "Faction":"The Dark Wheel", "Cost":15000, "CombatRank":1 }
        self._SpaceShip__loseMoney(journalentry, 'crewhire', journalentry['Cost'])
        self._SpaceShip__addSessionStat(journalentry, 'crew_hired')
    def __handleEvent_CrewLaunchFighter(self, journalentry):
        # {u'timestamp': u'2017-09-18T01:19:58Z', u'event': u'CrewLaunchFighter', u'Crew': u'BlownUterus'}
        pass
    def __handleEvent_CrewMemberJoins(self, journalentry):
        # {u'timestamp': u'2017-07-22T04:18:15Z', u'event': u'CrewMemberJoins', u'Crew': u'BinaryEpidemic'}
        pass
    def __handleEvent_CrewMemberQuits(self, journalentry):
        # {u'timestamp': u'2017-07-22T04:19:49Z', u'event': u'CrewMemberQuits', u'Crew': u'BinaryEpidemic'}
        pass
    def __handleEvent_CrewMemberRoleChange(self, journalentry):
        # {u'timestamp': u'2017-08-20T04:10:36Z', u'Role': u'Idle', u'event': u'CrewMemberRoleChange', u'Crew': u'BinaryEpidemic'}
        pass
    def __handleEvent_DatalinkScan(self, journalentry):
        # { "timestamp":"2017-08-31T04:53:47Z", "event":"DatalinkScan", "Message":"$DATAPOINT_GAMEPLAY_complete;", "Message_Localised":"Alert: All Data Point telemetry links established, Intel package created." }
        self._SpaceShip__addSessionStat(journalentry, 'scanned_datalinks')
    def __handleEvent_DatalinkVoucher(self, journalentry):
        # { "timestamp":"2017-08-31T04:53:47Z", "event":"DatalinkVoucher", "Reward":12952, "VictimFaction":"Empire", "PayeeFaction":"Alliance" }
        self._SpaceShip__addSessionStat(journalentry, 'voucher_count_datalink')
        self._SpaceShip__addSessionStat(journalentry, 'voucher_money_datalink', journalentry['Reward'])
    def __handleEvent_DataScanned(self, journalentry):
        # { "timestamp":"2017-09-06T04:06:23Z", "event":"DataScanned", "Type":"DataPoint" }
        # { "timestamp":"2017-09-03T05:01:58Z", "event":"DataScanned", "Type":"TouristBeacon" }
        if journalentry['Type'] == 'TouristBeacon':
            type = 'scanned_tourist_beacons'
        elif journalentry['Type'] == 'DataPoint':
            type = 'scanned_data_points'
        else:
            raise Exception('Unknown DataScanned type. Please report this message to the developer: %s' % journalentry)
        self._SpaceShip__addSessionStat(journalentry, type)
    def __handleEvent_Died(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"Died", "KillerName":"$ShipName_Police_Independent;", "KillerShip":"viper", "KillerRank":"Deadly" }
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"Died", "Killers":[ { "Name":"Cmdr HRC1", "Ship":"Vulture", "Rank":"Competent" }, { "Name":"Cmdr HRC2", "Ship":"Python", "Rank":"Master" } ] }
        # This entry has 2 possible formats depending on whether you killed by a single ship or a wing of ships
        self._SpaceShip__addSessionStat(journalentry, 'deaths')
        # MissionFailed events are generated shortly after dying.
        for cargo in self.cargo.keys(): # Don't just set self.cargo to empty, count each item as lost
            self._SpaceShip__loseCargo(journalentry, cargo, self.cargo[cargo]['amount'], 'lost_death')
    def __handleEvent_Docked(self, journalentry):
        #{ "timestamp":"2017-08-31T04:20:07Z", "event":"Docked", "StationName":"Bode Hub", "StationType":"Outpost", "StarSystem":"Wu Guinagi", "StationFaction":"Ajoku Industries", "FactionState":"Boom", "StationGovernment":"$government_Corporate;", "StationGovernment_Localised":"Corporate", "StationAllegiance":"Empire", "StationEconomy":"$economy_Industrial;", "StationEconomy_Localised":"Industrial", "DistFromStarLS":754.817932 }
        if self.ignore_next_docked:
            self.ignore_next_docked = False
        else:
            self._SpaceShip__addSessionVisitedStat(journalentry)
    def __handleEvent_DockFighter(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"DockFighter" }
        self._SpaceShip__addSessionStat(journalentry, 'fighter_docked')
    def __handleEvent_DockingCancelled(self, journalentry):
        # { "timestamp":"2017-08-31T03:42:54Z", "event":"DockingCancelled", "StationName":"Bode Hub" }
        self._SpaceShip__addSessionStat(journalentry, 'docking_cancelled')
    def __handleEvent_DockingDenied(self, journalentry):
        # { "timestamp":"2017-08-31T04:41:11Z", "event":"DockingDenied", "Reason":"Distance", "StationName":"Camm Enterprise" }
        self._SpaceShip__addSessionStat(journalentry, 'docking_denied')
    def __handleEvent_DockingGranted(self, journalentry):
        # { "timestamp":"2017-08-31T04:35:25Z", "event":"DockingGranted", "LandingPad":38, "StationName":"Ziegel Dock" }
        self._SpaceShip__addSessionStat(journalentry, 'docking_granted')
    def __handleEvent_DockingRequested(self, journalentry):
        # { "timestamp":"2017-08-31T04:35:24Z", "event":"DockingRequested", "StationName":"Ziegel Dock" }
        self._SpaceShip__addSessionStat(journalentry, 'docking_requested')
    def __handleEvent_DockingTimeout(self, journalentry):
        # Not positive, but I think { "timestamp":"2016-06-10T14:32:03Z", "event":"DockingTimeout", "StationName":"Kotov Refinery" }
        self._SpaceShip__addSessionStat(journalentry, 'docking_timeout')
    def __handleEvent_DockSRV(self, journalentry):
        # { "timestamp":"2017-09-06T04:16:41Z", "event":"DockSRV" }
        self._SpaceShip__addSessionStat(journalentry, 'srv_docked')
    def __handleEvent_EjectCargo(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"EjectCargo", "Type":"tobacco", "Count":1, "Abandoned":true }
        # { "timestamp":"2016-09-21T14:18:23Z", "event":"EjectCargo", "Type":"alliancelegaslativerecords", "Count":2, "Abandoned":true, "PowerplayOrigin":"Tau Bootis" }
        # This stupid event doesn't tell you if the cargo you're ejecting is haulage or stolen. I'll just assume stolen here as that's the logical thing to abandon. If it's not stolen, the internal state of haulage/stolen cargo will be wrong.
        self._SpaceShip__loseCargo(journalentry, journalentry['Type'], journalentry['Count'], 'ejected', stolen=True)
    def __handleEvent_EndCrewSession(self, journalentry):
        # {u'timestamp': u'2017-07-22T04:21:48Z', u'OnCrime': False, u'event': u'EndCrewSession'}
        # I think this only happens when you're the host of multicrew
        self._SpaceShip__addSessionStat(journalentry, 'crew_ended')
        if journalentry['OnCrime']:
            self._SpaceShip__addSessionStat(journalentry, 'crew_ended_crime')
    def __handleEvent_EngineerApply(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"EngineerApply", "Engineer":"Elvira Martuuk", "Blueprint":"ShieldGenerator_Reinforced", "Level":1 }
        self._SpaceShip__addSessionStat(journalentry, 'engineer_modifications_applied')
    def __handleEvent_EngineerContribution(self, journalentry):
        # {u'Commodity': u'metaalloys', u'timestamp': u'2017-09-03T05:47:44Z', u'TotalQuantity': 1, u'Engineer': u'Felicity Farseer', u'Type': u'Commodity', u'event': u'EngineerContribution', u'Quantity': 1}
        # {"timestamp": "2017-09-11T05:12:33Z", "event": "EngineerContribution", "Engineer": "The Dweller", "Type": "Credits", "Quantity": 500000, "TotalQuantity": 500000}
        # {"timestamp":"2017-10-01T18:41:08Z", "event":"EngineerContribution", "Engineer":"Tod 'The Blaster' McQuinn", "Type":"Bounty", "Quantity":45562, "TotalQuantity":45562 }
        if journalentry['Type'] == 'Credits':
            self._SpaceShip__loseMoney(journalentry, 'engineer_contribution', journalentry['TotalQuantity'])
        elif journalentry['Type'] == 'Commodity':
            self._SpaceShip__loseCargo(journalentry, journalentry['Commodity'], journalentry['Quantity'], 'delivered_engineer')
        elif journalentry['Type'] == 'Bounty':
            self._SpaceShip__addSessionStat(journalentry, 'engineer_bounty_spent', journalentry['Quantity'])
        else:
            raise Exception('Unknown EngineerContribution Type: %s.' % journalentry['Type'])
    def __handleEvent_EngineerCraft(self, journalentry):
        # {u'Blueprint': u'ShieldBooster_HeavyDuty', u'Level': 1, u'timestamp': u'2017-08-26T03:29:18Z', u'Ingredients': [{u'Count': 1, u'Name': u'gridresistors'}], u'event': u'EngineerCraft', u'Engineer': u'Felicity Farseer'}
        # { "timestamp":"2017-09-13T03:49:26Z", "event":"EngineerCraft", "Engineer":"The Dweller", "Blueprint":"PowerDistributor_HighFrequency", "Level":2, "Ingredients":[ { "Name":"legacyfirmware", "Count":1 }, { "Name":"chemicalprocessors", "Count":1 } ] }
        # First transform the Ingredients to a dict of {'IngredientName': int(count), ...}
        ingredients = {}
        for i in journalentry['Ingredients']:
            ingredients[i['Name']] = i['Count']
        for ingredient in ingredients:
            for typestore in self.materials, self.datamaterials: # We need to look into our current store to find the ingredients so we can determine the type
                try:
                    typestore[ingredient]
                except KeyError:
                    continue
                else: # found it!
                    try:
                        type = typestore[ingredient]['Type']
                    except TypeError: # This means there was no type and the material was found in Encoded
                        type = 'Encoded'
                    self._SpaceShip__changeMaterial(journalentry, type, ingredient, -ingredients[ingredient], 'engineer')
                    break
            else:
                raise Exception("Unknown material used in engineering: %s" % ingredient)
    def __handleEvent_EngineerProgress(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"EngineerProgress", "Progress":"Unlocked", "Engineer":"Elvira Martuuk" }
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"EngineerProgress", "Engineer":"Elvira Martuuk", "Rank":2 }
        try:
            journalentry['Progress']
        except KeyError: # No new progress was made, but you ranked up with this engineer
            self._SpaceShip__addSessionStat(journalentry, 'engineers_rank_gained')
        else: # record the new progress that was made
            if journalentry['Progress'] == 'Unlocked':
                self._SpaceShip__addSessionStat(journalentry, 'engineers_unlocked')
            elif journalentry['Progress'] == 'Invited':
                self._SpaceShip__addSessionStat(journalentry, 'engineers_invited')
            elif journalentry['Progress'] == 'Known':
                self._SpaceShip__addSessionStat(journalentry, 'engineers_known')
            else:
                raise Exception('Unknown EngineerProgress: %s' % journalentry)
    def __handleEvent_EscapeInterdiction(self, journalentry):
        # { "timestamp":"2017-08-31T04:47:23Z", "event":"EscapeInterdiction", "Interdictor":"Tamira Thunderstar", "IsPlayer":false }
        self._SpaceShip__addSessionStat(journalentry, 'interdictions_escaped_%s' % playerOrNpc(journalentry))
    def __handleEvent_FSDJump(self, journalentry):
        # { "timestamp":"2017-08-31T04:46:46Z", "event":"FSDJump", "StarSystem":"HIP 10716", "StarPos":[53.063,-226.188,-60.938], "SystemAllegiance":"Empire", "SystemEconomy":"$economy_Military;", "SystemEconomy_Localised":"Military", "SystemGovernment":"$government_Corporate;", "SystemGovernment_Localised":"Corporate", "SystemSecurity":"$SYSTEM_SECURITY_low;", "SystemSecurity_Localised":"Low Security", "JumpDist":11.867, "FuelUsed":3.155944, "FuelLevel":12.217494, "Factions":[ { "Name":"HIP 10716 Vision PLC", "FactionState":"Lockdown", "Government":"Corporate", "Influence":0.242242, "Allegiance":"Empire", "PendingStates":[ { "State":"Boom", "Trend":1 }, { "State":"CivilUnrest", "Trend":0 } ], "RecoveringStates":[ { "State":"Election", "Trend":0 } ] }, { "Name":"Ahaut Front", "FactionState":"Boom", "Government":"Dictatorship", "Influence":0.251251, "Allegiance":"Empire", "PendingStates":[ { "State":"Bust", "Trend":0 }, { "State":"CivilUnrest", "Trend":-1 } ] }, { "Name":"Wu Guinagi Crimson Creative Corp", "FactionState":"Boom", "Government":"Corporate", "Influence":0.112112, "Allegiance":"Empire", "PendingStates":[ { "State":"War", "Trend":0 } ] }, { "Name":"Ajoku Industries", "FactionState":"Boom", "Government":"Corporate", "Influence":0.196196, "Allegiance":"Empire", "PendingStates":[ { "State":"CivilUnrest", "Trend":0 } ], "RecoveringStates":[ { "State":"Election", "Trend":0 } ] }, { "Name":"Tewinicnii Vision Corporation", "FactionState":"Boom", "Government":"Corporate", "Influence":0.023023, "Allegiance":"Empire", "PendingStates":[ { "State":"Bust", "Trend":1 }, { "State":"CivilUnrest", "Trend":0 }, { "State":"Retreat", "Trend":0 } ] }, { "Name":"Nobles of HIP 10716", "FactionState":"Bust", "Government":"Feudal", "Influence":0.079079, "Allegiance":"Independent", "PendingStates":[ { "State":"Boom", "Trend":0 }, { "State":"War", "Trend":0 } ], "RecoveringStates":[ { "State":"CivilUnrest", "Trend":0 } ] }, { "Name":"Lords of the DarkStar Imperium", "FactionState":"Boom", "Government":"Dictatorship", "Influence":0.096096, "Allegiance":"Empire" } ], "SystemFaction":"HIP 10716 Vision PLC", "FactionState":"Lockdown" }
        self._SpaceShip__addSessionVisitedStat(journalentry)
    def __handleEvent_FactionKillBond(self, journalentry):
        # {"timestamp":"2016-06-10T14:32:03Z", "event":"FactionKillBond", "Reward": 500, "AwardingFaction":"Jarildekald Public Industry", "VictimFaction": "Lencali Freedom Party" }
        self._SpaceShip__addSessionStat(journalentry, 'kills_faction_bond')
    def __handleEvent_FetchRemoteModule(self, journalentry):
        # { "timestamp":"2017-09-20T02:49:36Z", "event":"FetchRemoteModule", "StorageSlot":31, "StoredItem":"$hpt_beamlaser_fixed_huge_name;", "StoredItem_Localised":"Beam Laser", "ServerId":128049431, "TransferCost":8152, "Ship":"ferdelance", "ShipID":10 }
        self._SpaceShip__loseMoney(journalentry, 'fetchremotemodule', journalentry['TransferCost'])
    def __handleEvent_Fileheader(self, journalentry):
        # { "timestamp":"2017-09-27T05:05:31Z", "event":"Fileheader", "part":1, "language":"English\\UK", "gameversion":"2.4", "build":"r154869/r0 " }
        pass
    def __handleEvent_Friends(self, journalentry):
        # { "timestamp":"2017-09-08T03:53:05Z", "event":"Friends", "Status":"Online", "Name":"BinaryEpidemic" }
        pass
    def __handleEvent_FuelScoop(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"FuelScoop", "Scooped":0.498700, "Total":16.000000 }
        # Total is your fuel level after scooping
        self._SpaceShip__addSessionStat(journalentry, 'fuel_scooped', journalentry['Scooped'])
        self._SpaceShip__addSessionStat(journalentry, 'fuel_scoop_started')
    def __handleEvent_HeatDamage(self, journalentry):
        # { "timestamp":"2017-08-28T01:05:22Z", "event":"HeatDamage" }
        self._SpaceShip__addSessionStat(journalentry, 'heat_damage_taken')
    def __handleEvent_HeatWarning(self, journalentry):
        # { "timestamp":"2017-08-29T06:09:23Z", "event":"HeatWarning" }
        self._SpaceShip__addSessionStat(journalentry, 'heat_warnings')
    def __handleEvent_HullDamage(self, journalentry):
        # When written: when hull health drops below a threshold (20% steps)
        # { "timestamp":"2016-07-25T14:46:23Z", "event":"HullDamage", "Health":0.798496 }
        self._SpaceShip__addSessionStat(journalentry, 'hull_damage_taken_fifths_fuzzy')
    def __handleEvent_Interdicted(self, journalentry):
        # { "timestamp":"2017-08-31T04:59:04Z", "event":"Interdicted", "Submitted":true, "Interdictor":"Ralph McKraven", "IsPlayer":false, "Faction":"Nobles of HIP 10716" }
        # This is when you were succesfully interdicted.
        if journalentry['Submitted']:
            result = 'submitted'
        else:
            result = 'escapes_failed'
        self._SpaceShip__addSessionStat(journalentry, 'interdictions_%s_%s' % (result, playerOrNpc(journalentry)))
    def __handleEvent_Interdiction(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"interdiction", "Success":true, "Interdicted":"Fred Flintstone", "IsPlayer":true, "CombatRank":5 }
        # { "timestamp":"2017-09-10T06:24:43Z", "event":"Interdiction", "Success":true, "IsPlayer":false, "Faction":"Revolutionary Party of Chamunda" }
        if journalentry['Success']:
            result = 'success'
        else:
            result = 'fail'
        self._SpaceShip__addSessionStat(journalentry, 'interdictions_committed_%s_%s' % (result, playerOrNpc(journalentry)))
    def __handleEvent_JetConeBoost(self, journalentry):
        # Not Sure: { "timestamp":"2016-06-10T14:32:03Z", "event":"JetConeBoost", "BoostValue":1234}
        self._SpaceShip__addSessionStat(journalentry, 'neutron_boosts')
        self._SpaceShip__addSessionStat(journalentry, 'neutron_boosts_value', journalentry['BoostValue'])
    def __handleEvent_JetConeDamage(self, journalentry):
        # Not sure: { "timestamp":"2016-06-10T14:32:03Z", "event":"JetConeDamage", "Module":"FSD"}
        self._SpaceShip__addSessionStat(journalentry, 'neutron_boost_damages')
    def __handleEvent_JoinACrew(self, journalentry):
        # {u'timestamp': u'2017-07-03T04:24:10Z', u'Captain': u'BinaryEpidemic', u'event': u'JoinACrew'}
        self._SpaceShip__addSessionStat(journalentry, 'crews_joined')
    def __handleEvent_KickCrewMember(self, journalentry):
        # {u'timestamp': u'2017-07-03T04:25:57Z', u'OnCrime': False, u'event': u'KickCrewMember', u'Crew': u'BlownUterus'}
        if journalentry['OnCrime']:
            post = '_crime'
        else:
            post = ''
        self._SpaceShip__addSessionStat(journalentry, 'crew_kicked%s' % post)
    def __handleEvent_LaunchFighter(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"LaunchFighter", "Loadout":"starter", "PlayerControlled":true }
        self._SpaceShip__addSessionStat(journalentry, 'fighter_launched_%s' % playerOrNpc(journalentry))
    def __handleEvent_LaunchSRV(self, journalentry):
        # { "timestamp":"2017-08-31T04:52:44Z", "event":"LaunchSRV", "Loadout":"starter", "PlayerControlled":true }
        self._SpaceShip__addSessionStat(journalentry, 'srv_launched_%s' % playerOrNpc(journalentry))
    def __handleEvent_Liftoff(self, journalentry):
        # { "timestamp":"2017-08-31T04:54:34Z", "event":"Liftoff", "PlayerControlled":true, "Latitude":-4.009589, "Longitude":153.113800 }
        # when taking off from planet surface
        self._SpaceShip__addSessionStat(journalentry, 'planet_liftoff_%s' % playerOrNpc(journalentry))
    def __handleEvent_LoadGame(self, journalentry):
        # { "timestamp":"2017-08-31T04:20:00Z", "event":"LoadGame", "Commander":"BlownUterus", "Ship":"Python", "ShipID":7, "ShipName":"", "ShipIdent":"", "FuelLevel":16.203438, "FuelCapacity":32.000000, "GameMode":"Group", "Group":"BinaryEpidemic", "Credits":205343662, "Loan":0 }
        if self.playername and (self.playername.lower() != journalentry['Commander'].lower()): # If the playername has been set in the past and the newly loaded game is for another CMDR...
            self.wrongplayer = True # don't do shit
        else: # playername hasn't been set yet or the right player loaded the game
            self.wrongplayer = False
            self.playername = journalentry['Commander']
            self.sessionstats['game'].reset(recording=True)
            self.moneycurrentbalance = journalentry['Credits']
            # Find out how much unknown money we've gained. This is calculated by looking at our current money as calculated by this script and comparing it to what loadgame says it should be.
            session = self.sessionstats['oldest']
            if (session.getTotalMoneyGained() - session.getTotalMoneySpent()) < self.moneycurrentbalance:
                #if DEBUG:
                #    print "Unknown money gained: %s. script says %s, LoadGame says %s @ %s" % (format(self.moneycurrentbalance - (session.getTotalMoneyGained() - session.getTotalMoneySpent()), ','), format(session.getTotalMoneyGained() -
                #                                                                                                                                                                                             session.getTotalMoneySpent(), ','), format(self.moneycurrentbalance, ','), journalentry['timestamp'])
                #    logfilenum = 1
                #    self.sessionlines.append('Loadgame says %s' % journalentry['Credits'])
                #    while True:
                #        if os.path.isfile('unknownmoney-%s.txt' % logfilenum):
                #            logfilenum += 1
                #        else:
                #            open('unknownmoney-%s.txt' % logfilenum, 'w').write('\r\n'.join(self.sessionlines))
                #            break
            #if DEBUG:
            #    self.sessionlines = []
            # we have to add directly to the sessionstat here otherwise gainMoney() will also count this money toward our currentbalance which is wrong
                session.addStat(journalentry, 'money_gained_unknown', self.moneycurrentbalance - (session.getTotalMoneyGained() - session.getTotalMoneySpent()))
            try:
                self.shipname = journalentry['ShipName']
            except KeyError: # sometimes LoadGame doesn't give a ShipName
                pass
            self._SpaceShip__addSessionStat(journalentry, 'games_loaded')
    def __handleEvent_Loadout(self, journalentry):
        "only set ship type and name here. This journal entry is made on session start."
        #{ "timestamp":"2017-08-31T04:20:00Z", "event":"Loadout", "Ship":"Python", "ShipID":7, "ShipName":"", "ShipIdent":"", "Modules":[ { "Slot":"LargeHardpoint1", "Item":"Hpt_BeamLaser_Gimbal_Large", "On":true, "Priority":1, "Health":1.000000, "Value":2396160 }, { "Slot":"LargeHardpoint2", "Item":"Hpt_BeamLaser_Gimbal_Large", "On":true, "Priority":1, "Health":1.000000, "Value":2396160 }, { "Slot":"LargeHardpoint3", "Item":"Hpt_MultiCannon_Gimbal_Large", "On":true, "Priority":1, "AmmoInClip":90, "AmmoInHopper":2100, "Health":1.000000, "Value":578436 }, { "Slot":"MediumHardpoint1", "Item":"Hpt_MultiCannon_Turret_Medium", "On":true, "Priority":1, "AmmoInClip":90, "AmmoInHopper":2100, "Health":1.000000, "Value":1292800 }, { "Slot":"MediumHardpoint2", "Item":"Hpt_MultiCannon_Turret_Medium", "On":true, "Priority":1, "AmmoInClip":90, "AmmoInHopper":2100, "Health":1.000000, "Value":1292800 }, { "Slot":"TinyHardpoint1", "Item":"Hpt_ShieldBooster_Size0_Class5", "On":true, "Priority":1, "Health":1.000000, "Value":281000 }, { "Slot":"TinyHardpoint2", "Item":"Hpt_ShieldBooster_Size0_Class5", "On":true, "Priority":1, "Health":1.000000, "Value":281000 }, { "Slot":"TinyHardpoint3", "Item":"Hpt_ChaffLauncher_Tiny", "On":true, "Priority":0, "AmmoInClip":1, "AmmoInHopper":10, "Health":1.000000, "Value":8500 }, { "Slot":"TinyHardpoint4", "Item":"Hpt_ShieldBooster_Size0_Class5", "On":true, "Priority":1, "Health":1.000000, "Value":281000 }, { "Slot":"PaintJob", "Item":"PaintJob_Python_Squadron_Green", "On":true, "Priority":1, "Health":1.000000, "Value":0 }, { "Slot":"Decal1", "Item":"Decal_Trade_Broker", "On":true, "Priority":1, "Health":1.000000, "Value":0 }, { "Slot":"Decal2", "Item":"Decal_Trade_Broker", "On":true, "Priority":1, "Health":1.000000, "Value":0 }, { "Slot":"Decal3", "Item":"Decal_Trade_Broker", "On":true, "Priority":1, "Health":1.000000, "Value":0 }, { "Slot":"Armour", "Item":"Python_Armour_Grade3", "On":true, "Priority":1, "Health":1.000000, "Value":51280361 }, { "Slot":"PowerPlant", "Item":"Int_Powerplant_Size7_Class5", "On":true, "Priority":1, "Health":1.000000, "Value":51289112 }, { "Slot":"MainEngines", "Item":"Int_Engine_Size6_Class5", "On":true, "Priority":0, "Health":1.000000, "Value":16179531 }, { "Slot":"FrameShiftDrive", "Item":"Int_Hyperdrive_Size5_Class5", "On":true, "Priority":0, "Health":1.000000, "Value":5103953 }, { "Slot":"LifeSupport", "Item":"Int_LifeSupport_Size4_Class2", "On":true, "Priority":0, "Health":1.000000, "Value":28373 }, { "Slot":"PowerDistributor", "Item":"Int_PowerDistributor_Size7_Class5", "On":true, "Priority":0, "Health":1.000000, "Value":9731925 }, { "Slot":"Radar", "Item":"Int_Sensors_Size6_Class2", "On":true, "Priority":0, "Health":1.000000, "Value":222444 }, { "Slot":"FuelTank", "Item":"Int_FuelTank_Size5_Class3", "On":true, "Priority":1, "Health":1.000000, "Value":97754 }, { "Slot":"Slot01_Size6", "Item":"Int_ShieldGenerator_Size6_Class5", "On":true, "Priority":0, "Health":1.000000, "Value":16179531 }, { "Slot":"Slot02_Size6", "Item":"Int_CargoRack_Size6_Class1", "On":true, "Priority":1, "Health":1.000000, "Value":362591 }, { "Slot":"Slot03_Size6", "Item":"Int_CargoRack_Size6_Class1", "On":true, "Priority":1, "Health":1.000000, "Value":362591 }, { "Slot":"Slot04_Size5", "Item":"Int_CargoRack_Size5_Class1", "On":true, "Priority":1, "Health":1.000000, "Value":111566 }, { "Slot":"Slot05_Size5", "Item":"Int_CargoRack_Size5_Class1", "On":true, "Priority":1, "Health":1.000000, "Value":111566 }, { "Slot":"Slot06_Size4", "Item":"Int_CargoRack_Size4_Class1", "On":true, "Priority":1, "Health":1.000000, "Value":34328 }, { "Slot":"Slot07_Size3", "Item":"Int_CargoRack_Size3_Class1", "On":true, "Priority":1, "Health":1.000000, "Value":10563 }, { "Slot":"Slot08_Size3", "Item":"Int_ShieldCellBank_Size3_Class5", "On":true, "Priority":1, "AmmoInClip":1, "AmmoInHopper":3, "Health":1.000000, "Value":158331 }, { "Slot":"Slot09_Size2", "Item":"Int_BuggyBay_Size2_Class2", "On":true, "Priority":2, "Health":1.000000, "Value":21600 }, { "Slot":"PlanetaryApproachSuite", "Item":"Int_PlanetApproachSuite", "On":true, "Priority":1, "Health":1.000000, "Value":500 }, { "Slot":"ShipCockpit", "Item":"Python_Cockpit", "On":true, "Priority":1, "Health":1.000000, "Value":0 }, { "Slot":"CargoHatch", "Item":"ModularCargoBayDoor", "On":true, "Priority":2, "Health":1.000000, "Value":0 } ] }
        self.shiptype = journalentry['Ship']
        self.shipname = journalentry['ShipName']
    def __handleEvent_Location(self, journalentry):
        # { "timestamp":"2017-08-31T04:20:07Z", "event":"Location", "Docked":true, "StationName":"Bode Hub", "StationType":"Outpost", "StarSystem":"Wu Guinagi", "StarPos":[60.281,-231.844,-53.406], "SystemAllegiance":"Empire", "SystemEconomy":"$economy_Industrial;", "SystemEconomy_Localised":"Industrial", "SystemGovernment":"$government_Corporate;", "SystemGovernment_Localised":"Corporate", "SystemSecurity":"$SYSTEM_SECURITY_medium;", "SystemSecurity_Localised":"Medium Security", "Body":"Bode Hub", "BodyType":"Station", "Factions":[ { "Name":"HIP 10716 Vision PLC", "FactionState":"Lockdown", "Government":"Corporate", "Influence":0.238477, "Allegiance":"Empire", "PendingStates":[ { "State":"Boom", "Trend":1 }, { "State":"CivilUnrest", "Trend":0 } ] }, { "Name":"Ahaut Front", "FactionState":"Boom", "Government":"Dictatorship", "Influence":0.256513, "Allegiance":"Empire", "PendingStates":[ { "State":"Bust", "Trend":0 }, { "State":"CivilUnrest", "Trend":-1 } ] }, { "Name":"Wu Guinagi Crimson Creative Corp", "FactionState":"Boom", "Government":"Corporate", "Influence":0.114228, "Allegiance":"Empire" }, { "Name":"Ajoku Industries", "FactionState":"Boom", "Government":"Corporate", "Influence":0.207415, "Allegiance":"Empire", "PendingStates":[ { "State":"CivilUnrest", "Trend":0 } ] }, { "Name":"Progressive Party of Wu Guinagi", "FactionState":"CivilWar", "Government":"Democracy", "Influence":0.023046, "Allegiance":"Independent", "PendingStates":[ { "State":"CivilUnrest", "Trend":-1 } ] }, { "Name":"Traditional Wu Guinagi Bureau", "FactionState":"CivilWar", "Government":"Dictatorship", "Influence":0.020040, "Allegiance":"Independent", "PendingStates":[ { "State":"Boom", "Trend":0 } ] }, { "Name":"Wu Guinagi Pirates", "FactionState":"Boom", "Government":"Anarchy", "Influence":0.045090, "Allegiance":"Independent", "PendingStates":[ { "State":"CivilUnrest", "Trend":0 } ], "RecoveringStates":[ { "State":"Bust", "Trend":0 } ] }, { "Name":"Lords of the DarkStar Imperium", "FactionState":"Boom", "Government":"Dictatorship", "Influence":0.095190, "Allegiance":"Empire" } ], "SystemFaction":"Wu Guinagi Crimson Creative Corp", "FactionState":"Boom" }
        # This event is when you spawn, not when you land or arrive somewhere. This happens when you load the game or you die and respawn somewhere else
        # I don't think this should be counted as a visited destination
        if journalentry['Docked']:
            self.ignore_next_docked = True
    def __handleEvent_MarketBuy(self, journalentry):
        "This event is always for a single item type."
        # {"timestamp": "2016-06-10T14:32:03Z", "event": "MarketBuy", "Type": "foodcartridges", "Count": 10, "BuyPrice": 39, "TotalCost": 390}
        self._SpaceShip__gainCargo(journalentry, journalentry['Type'], journalentry['Count'], 'bought_commodity')
        self._SpaceShip__loseMoney(journalentry,  'commodities', journalentry['TotalCost'] )
    def __handleEvent_MarketSell(self, journalentry):
        "This event is always for a single item type."
        # { "timestamp":"2017-08-31T04:42:33Z", "event":"MarketSell", "Type":"hnshockmount", "Count":4, "SellPrice":1239, "TotalSale":4956, "AvgPricePaid":0 }
        # { "timestamp":"2017-09-11T05:40:32Z", "event":"MarketSell", "Type":"lithium", "Count":1, "SellPrice":684, "TotalSale":684, "AvgPricePaid":0, "StolenGoods":true, "BlackMarket":true }
        # Now add the money that we received from this sale:
        if journalentry.get('BlackMarket'):
            type = 'blackmarket'
            cargosold = '_illegal'
        else:
            type = 'market'
            cargosold = ''
        self._SpaceShip__gainMoney(journalentry, type, journalentry['TotalSale'])
        # Now get rid of the cargo and mark it as sold
        self._SpaceShip__loseCargo(journalentry, journalentry['Type'], journalentry['Count'], 'sold%s' % cargosold, stolen=journalentry.get('BlackMarket', False))
        if (journalentry['AvgPricePaid'] > 0) and (journalentry['SellPrice'] - journalentry['AvgPricePaid'] > 0): # if there was an average price and we sold for more than the average, add the amount to the proper stat:
            word = 'over'
        elif (journalentry['AvgPricePaid'] > 0) and (journalentry['SellPrice'] - journalentry['AvgPricePaid'] < 0): # if there was an average price, but we made less money than the average...
            word = 'under'
        else:
            return # don't add a galactic_average stat if there was none
        self._SpaceShip__addSessionStat(journalentry, 'money_%s_market_galactic_average' % word, abs(journalentry['TotalSale'] - (journalentry['AvgPricePaid'] * journalentry['Count'])))
    def __handleEvent_MassModuleStore(self, journalentry):
        # { "timestamp":"2017-09-06T04:32:32Z", "event":"MassModuleStore", "Ship":"asp", "ShipID":2, "Items":[ { "Slot":"TinyHardpoint1", "Name":"$hpt_shieldbooster_size0_class5_name;", "EngineerModifications":"ShieldBooster_HeavyDuty" }, { "Slot":"TinyHardpoint2", "Name":"$hpt_shieldbooster_size0_class5_name;", "EngineerModifications":"ShieldBooster_HeavyDuty" }, { "Slot":"TinyHardpoint3", "Name":"$hpt_shieldbooster_size0_class5_name;", "EngineerModifications":"ShieldBooster_HeavyDuty" }] }
        self._SpaceShip__addSessionStat(journalentry, 'modules_stored', len(journalentry['Items']))
    def __handleEvent_MaterialCollected(self, journalentry):
        "This event always gives you one type of material at a time."
        # { "timestamp":"2017-08-31T04:36:27Z", "event":"MaterialCollected", "Category":"Encoded", "Name":"scrambledemissiondata", "Count":1 }
        self._SpaceShip__changeMaterial(journalentry, journalentry['Category'], journalentry['Name'], journalentry['Count'], '')
    def __handleEvent_MaterialDiscarded(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"MaterialDiscarded", "Category":"Raw", "Name":"sulphur", "Count": 5 }
        self._SpaceShip__changeMaterial(journalentry, journalentry['Category'], journalentry['Name'], -journalentry['Count'], 'discarded')
    def __handleEvent_MaterialDiscovered(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"MaterialDiscovered", "Category":"Manufactured", "Name":"focuscrystals", "DiscoveryNumber":3 }
        self._SpaceShip__addSessionStat(journalentry, 'materials_discovered')
    def __handleEvent_Materials(self, journalentry):
        "This journal entry is made on session start."
        #{ "timestamp":"2017-08-31T04:20:00Z", "event":"Materials", "Raw":[ { "Name":"nickel", "Count":9 }, { "Name":"germanium", "Count":6 } ], "Manufactured":[ { "Name":"salvagedalloys", "Count":20 }, { "Name":"galvanisingalloys", "Count":29 }, { "Name":"compoundshielding", "Count":15 }, { "Name":"shieldingsensors", "Count":16 }, { "Name":"shieldemitters", "Count":17 }, { "Name":"mechanicalequipment", "Count":32 }, { "Name":"wornshieldemitters", "Count":23 }, { "Name":"conductivecomponents", "Count":26 }, { "Name":"focuscrystals", "Count":22 }, { "Name":"refinedfocuscrystals", "Count":38 }, { "Name":"chemicalprocessors", "Count":22 }, { "Name":"temperedalloys", "Count":1 }, { "Name":"basicconductors", "Count":1 }, { "Name":"phasealloys", "Count":24 }, { "Name":"mechanicalscrap", "Count":15 }, { "Name":"hybridcapacitors", "Count":24 }, { "Name":"heatconductionwiring", "Count":18 }, { "Name":"heatdispersionplate", "Count":12 }, { "Name":"gridresistors", "Count":24 }, { "Name":"mechanicalcomponents", "Count":31 }, { "Name":"highdensitycomposites", "Count":30 }, { "Name":"precipitatedalloys", "Count":45 }, { "Name":"conductiveceramics", "Count":27 }, { "Name":"electrochemicalarrays", "Count":25 }, { "Name":"chemicaldistillery", "Count":15 }, { "Name":"heatvanes", "Count":9 }, { "Name":"heatexchangers", "Count":3 }, { "Name":"uncutfocuscrystals", "Count":26 }, { "Name":"imperialshielding", "Count":57 }, { "Name":"biotechconductors", "Count":6 }, { "Name":"thermicalloys", "Count":7 }, { "Name":"conductivepolymers", "Count":17 }, { "Name":"configurablecomponents", "Count":9 }, { "Name":"exquisitefocuscrystals", "Count":8 }, { "Name":"protolightalloys", "Count":9 }, { "Name":"fedproprietarycomposites", "Count":3 }, { "Name":"polymercapacitors", "Count":3 }, { "Name":"protoradiolicalloys", "Count":3 } ], "Encoded":[ { "Name":"shielddensityreports", "Count":21 }, { "Name":"shieldcyclerecordings", "Count":2 }, { "Name":"legacyfirmware", "Count":8 }, { "Name":"shieldpatternanalysis", "Count":27 }, { "Name":"decodedemissiondata", "Count":36 }, { "Name":"shieldsoakanalysis", "Count":9 }, { "Name":"scrambledemissiondata", "Count":3 }, { "Name":"disruptedwakeechoes", "Count":4 }, { "Name":"emissiondata", "Count":49 }, { "Name":"encodedscandata", "Count":8 }, { "Name":"bulkscandata", "Count":1 }, { "Name":"archivedemissiondata", "Count":7 }, { "Name":"consumerfirmware", "Count":13 }, { "Name":"wakesolutions", "Count":13 }, { "Name":"scanarchives", "Count":8 }, { "Name":"scandatabanks", "Count":32 }, { "Name":"encryptioncodes", "Count":9 }, { "Name":"symmetrickeys", "Count":18 }, { "Name":"encryptedfiles", "Count":2 }, { "Name":"encryptionarchives", "Count":57 }, { "Name":"adaptiveencryptors", "Count":40 }, { "Name":"industrialfirmware", "Count":21 }, { "Name":"embeddedfirmware", "Count":5 }, { "Name":"hyperspacetrajectories", "Count":3 }, { "Name":"dataminedwake", "Count":3 }, { "Name":"securityfirmware", "Count":3 }, { "Name":"compactemissionsdata", "Count":3 }, { "Name":"fsdtelemetry", "Count":2 } ] }
        self.materials.clear()
        self.datamaterials.clear()
        for materialtype in ('Raw', 'Manufactured'):
            try:
                journalentry[materialtype]
            except KeyError: # material type didn't exist
                pass
            else:
                for material in journalentry[ materialtype ]:
                    self.materials[ material[ 'Name' ] ] = {'Type': materialtype, 'Count': PositiveInt(material['Count'])}
        try:
            journalentry[ 'Encoded' ]
        except KeyError: # There was no encoded data.
            pass
        else:
            for material in journalentry[ 'Encoded' ]:
                self.datamaterials[ material[ 'Name' ] ] = PositiveInt(material['Count'])
    def __handleEvent_MiningRefined(self, journalentry):
        # { "timestamp":"2017-08-14T14:16:43Z", "event":"MiningRefined", "Type":"$methaneclathrate_name;", "Type_Localised":"Methane Clathrate" }
        # Always a single amount
        self._SpaceShip__gainCargo(journalentry, journalentry['Type_Localised'], 1, 'fake', nostat=True)
        self._SpaceShip__addSessionRefineryStat(journalentry['Type_Localised'])
    def __handleEvent_MissionAbandoned(self, journalentry):
        # {u'MissionID': 199638197, u'timestamp': u'2017-08-31T04:44:01Z', u'event': u'MissionAbandoned', u'Name': u'Mission_Courier_Boom_name'}
        self._SpaceShip__removeMission(journalentry)
        self._SpaceShip__addSessionStat(journalentry, 'missions_abandoned')
    def __handleEvent_MissionAccepted(self, journalentry):
        # { "timestamp":"2017-09-20T03:04:18Z", "event":"MissionAccepted", "Faction":"Lords of the DarkStar Imperium", "Name":"Mission_Delivery", "Commodity":"$Liquor_Name;", "Commodity_Localised":"Liquor", "Count":16, "Destination System":"HIP 10716", "DestinationStation":"Morgan Depot", "Expiry":"2017-09-21T02:36:06Z", "Influence":"Low", "Reputation":"Low", "MissionID":209729133 }
        # remove the event type and the MissionID from the event as the MissionID becomes the key for this dict.
        newjournalentry = journalentry.copy()
        del newjournalentry['event']
        missionid = newjournalentry.pop('MissionID')
        self.missions[ missionid ] = newjournalentry
        try: # Add any cargo you gained from taking the mission:
            newjournalentry['Commodity_Localised']
        except KeyError:
            pass
        else:
            if not journalentry['Name'].lower().startswith('mission_collect'): # Collect missions (industry needs x amount of y commodity) don't give you the commodity you need
                self._SpaceShip__gainCargo(newjournalentry, newjournalentry['Commodity_Localised'], newjournalentry['Count'], 'haulage', haulage=True )
        try: # Add any passengers you gained from taking the mission:
            newjournalentry['PassengerCount']
        except KeyError:
            pass
        else:
            self.passengers[missionid] = {'count': newjournalentry['PassengerCount'], 'vip': newjournalentry['PassengerVIPs'], 'wanted': newjournalentry['PassengerWanted'], 'type': newjournalentry['PassengerType']}
        self._SpaceShip__addSessionStat(journalentry, 'missions_accepted')
    def __handleEvent_MissionCompleted(self, journalentry):
        # { "timestamp":"2017-08-31T04:42:10Z", "event":"MissionCompleted", "Faction":"Ahaut Front", "Name":"Mission_Delivery_Boom_name", "MissionID":199640174, "Commodity":"$Clothing_Name;", "Commodity_Localised":"Clothing", "Count":12, "DestinationSystem":"Wu Guinagi", "DestinationStation":"Camm Enterprise", "Reward":125086, "CommodityReward":[ { "Name":"HNShockMount", "Count":4 } ] }
        try: # count donations if this was a donation mission
            journalentry['Donation']
        except KeyError:
            pass
        else:
            self._SpaceShip__loseMoney(journalentry, 'mission_donations', journalentry['Donation'])
        try: # count passengers successfully delivered if this was a passenger mission
            self.missions[journalentry['MissionID']]['PassengerCount']
        except KeyError: # no passengers
            pass
        else:
            self._SpaceShip__addSessionStat(journalentry, 'missions_passengers_delivered', self.missions[journalentry['MissionID']]['PassengerCount'])
        self._SpaceShip__removeMission(journalentry)
        self._SpaceShip__addSessionStat(journalentry, 'missions_completed')
    def __handleEvent_MissionFailed(self, journalentry):
        # { "timestamp":"2017-09-17T22:13:50Z", "event":"MissionFailed", "Name":"Mission_Delivery_name", "MissionID":208682468 }
        self._SpaceShip__removeMission(journalentry)
        self._SpaceShip__addSessionStat(journalentry, 'missions_failed')
    def __handleEvent_MissionRedirected(self, journalentry):
        # {u'Name': u'Chain_PlanetaryIncursions_name', u'MissionID': 213305752, u'timestamp': u'2017-09-27T04:43:01Z', u'OldDestinationStation': u'', u'event': u'MissionRedirected', u'NewDestinationSystem': u'Wu Guinagi', u'OldDestinationSystem': u'HIP 10716', u'NewDestinationStation': u'Camm Enterprise'}
        try:
            self.missions[journalentry['MissionID']]
        except KeyError: # sometimes when you create a new character, you get a missionredirected from a non-existant mission, like this event from ruffyen:
            pass # {u'Name': u'Mission_Welcome_name', u'MissionID': 231022183, u'timestamp': u'2017-10-21T00:30:38Z', u'OldDestinationStation': u'', u'event': u'MissionRedirected', u'NewDestinationSystem': u'Eravate', u'OldDestinationSystem': u'', u'NewDestinationStation': u'Maine Hub'}
            # I grepped his logs for the missionID and nothing else came up
        else:
            for k in ('DestinationSystem', 'DestinationStation'):
                self.missions[journalentry['MissionID']][k] = journalentry[''.join(('New', k))]
            self._SpaceShip__addSessionStat(journalentry, 'missions_redirected')
    def __handleEvent_ModuleBuy(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"ModuleBuy", "Slot":"MediumHardpoint2", "SellItem":"hpt_pulselaser_fixed_medium", "SellPrice":0, "BuyItem":"hpt_multicannon_gimbal_medium", "BuyPrice":50018, "Ship":"cobramkiii","ShipID":1 }
        # {u'Slot': u'Slot04_Size5', u'ShipID': 7, u'BuyPrice': 777600, u'timestamp': u'2017-10-06T03:55:59Z', u'BuyItem': u'$int_dronecontrol_prospector_size5_class5_name;', u'Ship': u'python', u'BuyItem_Localised': u'Prospector', u'event': u'ModuleBuy'}
        # I think I found out where the missing money is coming from! This event *includes* selling the module that you're replacing with the newly bought one!
        # { "timestamp":"2017-10-27T02:08:09Z", "event":"ModuleBuy", "Slot":"MediumHardpoint1", "SellItem":"$hpt_beamlaser_turret_medium_name;", "SellItem_Localised":"Beam Laser", "SellPrice":2099900, "BuyItem":"$hpt_pulselaserburst_turret_medium_name;", "BuyItem_Localised":"Burst Laser", "BuyPrice":162800, "Ship":"anaconda", "ShipID":14 }
        self._SpaceShip__loseMoney(journalentry, 'modulebuy', journalentry['BuyPrice'])
        self._SpaceShip__addSessionStat(journalentry, 'modules_bought')
        try:
            journalentry['SellPrice']
        except KeyError:
            pass
        else:
            self._SpaceShip__gainMoney(journalentry, 'sellmodules', journalentry['SellPrice'])
            self._SpaceShip__addSessionStat(journalentry, 'modules_sold')
    def __handleEvent_ModuleRetrieve(self, journalentry):
        # { "timestamp":"2017-09-06T04:34:14Z", "event":"ModuleRetrieve", "Slot":"TinyHardpoint4", "RetrievedItem":"$hpt_shieldbooster_size0_class5_name;", "RetrievedItem_Localised":"Shield Booster", "Ship":"python", "ShipID":7, "EngineerModifications":"ShieldBooster_HeavyDuty" }
        # { "timestamp":"2017-09-03T04:28:47Z", "event":"ModuleRetrieve", "Slot":"Slot04_Size3", "RetrievedItem":"$int_fuelscoop_size3_class5_name;", "RetrievedItem_Localised":"Fuel Scoop", "Ship":"asp", "ShipID":2, "SwapOutItem":"$int_cargorack_size3_class1_name;", "SwapOutItem_Localised":"Cargo Rack", "Cost":0 }
        # This entry doesn't always have a cost or SwapOutItem
        try:
            journalentry['Cost']
        except KeyError:
            pass
        else:
            self._SpaceShip__loseMoney(journalentry, 'moduleretrieve', journalentry['Cost'])
        self._SpaceShip__addSessionStat(journalentry, 'modules_retrieved')
    def __handleEvent_ModuleSell(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"ModuleSell", "Slot":"Slot06_Size2", "SellItem":"int_cargorack_size1_class1", "SellPrice":877, "Ship":"asp", "ShipID":1 }
        self._SpaceShip__gainMoney(journalentry, 'sellmodules', journalentry['SellPrice'])
        self._SpaceShip__addSessionStat(journalentry, 'modules_sold')
    def __handleEvent_ModuleSellRemote(self, journalentry):
        # { "timestamp":"2017-09-08T06:18:36Z", "event":"ModuleSellRemote", "StorageSlot":59, "SellItem":"$int_cargorack_size5_class1_name;", "SellItem_Localised":"Cargo Rack", "ServerId":128064342, "SellPrice":111566, "Ship":"python", "ShipID":7 }\
        self._SpaceShip__gainMoney(journalentry, 'sellmodules', journalentry['SellPrice'])
        self._SpaceShip__addSessionStat(journalentry, 'modules_sold_remote')
    def __handleEvent_ModuleStore(self, journalentry):
        # { "timestamp":"2017-09-06T04:32:32Z", "event":"MassModuleStore", "Ship":"asp", "ShipID":2, "Items":[ { "Slot":"TinyHardpoint1", "Name":"$hpt_shieldbooster_size0_class5_name;", "EngineerModifications":"ShieldBooster_HeavyDuty" }, { "Slot":"TinyHardpoint2", "Name":"$hpt_shieldbooster_size0_class5_name;", "EngineerModifications":"ShieldBooster_HeavyDuty" }, { "Slot":"TinyHardpoint3", "Name":"$hpt_shieldbooster_size0_class5_name;", "EngineerModifications":"ShieldBooster_HeavyDuty" }] }
        try: # apparently sometimes there's a cost for this, I've never seen it happen though
            journalentry['Cost']
        except KeyError:
            pass
        else:
            self._SpaceShip__loseMoney(journalentry, 'modulestore', journalentry['Cost'])
        self._SpaceShip__addSessionStat(journalentry, 'modules_stored')
    def __handleEvent_ModuleSwap(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"ModuleSwap", "FromSlot":"MediumHardpoint1", "ToSlot":"MediumHardpoint2", "FromItem":"hpt_pulselaser_fixed_medium", "ToItem":"hpt_multicannon_gimbal_medium", "Ship":"cobramkiii", "ShipID":1 }
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"ModuleSwap", "FromSlot":"SmallHardpoint2", "ToSlot":"SmallHardpoint1", "FromItem":"hpt_pulselaserburst_fixed_small_scatter", "ToItem":"Null", "Ship":"cobramkiii", "ShipID":1 }
        self._SpaceShip__addSessionStat(journalentry, 'modules_swapped')
    def __handleEvent_Music(self, journalentry):
        # {u'event': u'Music', u'timestamp': u'2017-09-27T04:19:10Z', u'MusicTrack': u'NoTrack'}
        self._SpaceShip__addSessionStat(journalentry, 'music_changed')
    def __handleEvent_NavBeaconScan(self, journalentry):
        # {u'timestamp': u'2017-09-27T11:33:35Z', u'event': u'NavBeaconScan', u'NumBodies': 12}
        self._SpaceShip__addSessionStat(journalentry, 'nav_beacons_scanned')
    def __handleEvent_NewCommander(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"NewCommander", "Name":"HRC1", "Package":"ImperialBountyHunter" }
        # {"timestamp": "2017-06-12T04:19:56Z", "event": "NewCommander", "Name": "BlownUterus", "Package": "Default"}
        self._SpaceShip__addSessionStat(journalentry, 'new_commander_created')
        self._SpaceShip__gainMoney(journalentry, 'missions', 1000) # you start with a grand, we'll call it mission money because I don't want a new stat for this
    def __handleEvent_Passengers(self, journalentry):
        # {u'timestamp': u'2017-10-08T04:34:46Z', u'event': u'Passengers', u'Manifest': [{u'MissionID': 222448224, u'Count': 2, u'VIP': True, u'Wanted': False, u'Type': u'Tourist'}, {u'MissionID': 222448871, u'Count': 4, u'VIP': False, u'Wanted': False, u'Type': u'Refugee'}]}
        # This is a state-setting event, it always happens before Loadout to tell what passengers you currently have onboard.
        self.passengers = {}
        for pax in journalentry['Manifest']:
            missionid = pax.pop('MissionID')
            self.passengers[missionid] = {}
            for key in pax:
                self.passengers[missionid][key.lower()] = pax[key]
    def __handleEvent_PayFines(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"PayFines", "Amount":1791 }
        self._SpaceShip__loseMoney(journalentry, 'fines', journalentry['Amount'])
        self._SpaceShip__addSessionStat(journalentry, 'fines_gained')
    def __handleEvent_PayLegacyFines(self, journalentry):
        # { "timestamp":"2017-09-07T05:07:06Z", "event":"PayLegacyFines", "Amount":385 }
        # {"timestamp": "2017-09-06T04:50:26Z", "event": "PayLegacyFines", "Amount": 131445, "BrokerPercentage": 25.000000}
        self._SpaceShip__loseMoney(journalentry, 'legacyfines', journalentry['Amount'])
        self._SpaceShip__addSessionStat(journalentry, 'fines_legacy_paid')
    def __handleEvent_PowerplayCollect(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"PowerplayCollect", "Power":"Li Yong-Rui", "Type":"siriusfranchisepackage", "Count":10 }
        # TODO: Is this necessary or is there a regular CollectCargo event generated?
        self._SpaceShip__gainCargo(journalentry, journalentry['Type'], journalentry['Count'], 'powerplay')
    def __handleEvent_PowerplayDefect(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"PowerplayDefect", "FromPower":"Zachary Hudson", "ToPower":"Li Yong-Rui" }
        self._SpaceShip__addSessionStat(journalentry, 'powerplay_defect')
    def __handleEvent_PowerplayDeliver(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"PowerplayDeliver", "Power":"Li Yong-Rui", "Type":"siriusfranchisepackage", "Count":10 }
        self._SpaceShip__loseCargo(journalentry, journalentry['Type'], journalentry['Count'], 'delivered_powerplay')
    def __handleEvent_PowerplayFastTrack(self, journalentry):
        # Not sure: { "timestamp":"2016-06-10T14:32:03Z", "event":"PowerplayFastTrack", "Power":"Li Yong-Rui", "Cost":1234 }
        self._SpaceShip__loseMoney(journalentry, 'powerplayfasttrack', journalentry['Cost'])
    def __handleEvent_PowerplayJoin(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"PowerplayJoin", "Power":"Zachary Hudson" }
        self._SpaceShip__addSessionStat(journalentry, 'powerplay_join')
    def __handleEvent_PowerplayLeave(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"PowerplayLeave", "Power":"Li Yong-Rui" }
        self._SpaceShip__addSessionStat(journalentry, 'powerplay_leave')
    def __handleEvent_PowerplaySalary(self, journalentry):
        # { "timestamp":"2017-09-08T04:32:17Z", "event":"PowerplaySalary", "Power":"Aisling Duval", "Amount":1000 }
        self._SpaceShip__gainMoney(journalentry, 'powerplaysalary', journalentry['Amount'])
        self._SpaceShip__addSessionStat(journalentry, 'powerplay_salaries_redeemed')
    def __handleEvent_PowerplayVote(self, journalentry):
        # Not Sure: { "timestamp":"2017-09-08T04:32:17Z", "event":"PowerplayVote", "Power":"Aisling Duval", "Votes":1234, "System":"Jo Momma" }
        self._SpaceShip__addSessionStat(journalentry, 'powerplay_vote')
        self._SpaceShip__addSessionStat(journalentry, 'powerplay_votes_casted', journalentry['Votes'])
    def __handleEvent_PowerplayVoucher(self, journalentry):
        # Not sure: { "timestamp":"2017-09-08T04:32:17Z", "event":"PowerplayVoucher", "Power":"Aisling Duval", "Systems":["Jo Momma", "Another System"] }
        self._SpaceShip__addSessionStat(journalentry, 'powerplay_vouchers')# TODO I think this gives you money somehow
    def __handleEvent_Progress(self, journalentry):
        # { "timestamp":"2017-08-31T04:20:00Z", "event":"Progress", "Combat":5, "Trade":53, "Explore":9, "Empire":66, "Federation":30, "CQC":0 }
        # This is written at startup to tell you your current progress to the next rank. "Trade":53 means you're 53% to the next rank
        pass # can we actually do anything with this? probably not
    def __handleEvent_Promotion(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"Promotion", "Explore":2 }
        self._SpaceShip__setRank(journalentry)
    def __handleEvent_PVPKill(self, journalentry):
        # Not sure: { "timestamp":"2016-06-10T14:32:03Z", "event":"PVPKill", "Victim":"Bill Wentz", "CombatRank":5 }
        self._SpaceShip__addSessionStat(journalentry, 'kills_pvp')
    def __handleEvent_QuitACrew(self, journalentry):
        # {u'timestamp': u'2017-07-03T04:25:10Z', u'Captain': u'BinaryEpidemic', u'event': u'QuitACrew'}
        self._SpaceShip__addSessionStat(journalentry, 'crew_quit')
    def __handleEvent_Rank(self, journalentry):
        # { "timestamp":"2017-08-31T04:20:00Z", "event":"Rank", "Combat":3, "Trade":5, "Explore":6, "Empire":8, "Federation":0, "CQC":0 }
        self._SpaceShip__setRank(journalentry)
    def __handleEvent_RebootRepair(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"RebootRepair", "Modules":[ "MainEngines", "TinyHardpoint1" ] }
        self._SpaceShip__addSessionStat(journalentry, 'reboot_repairs')
    def __handleEvent_ReceiveText(self, journalentry):
        # { "timestamp":"2017-08-31T04:30:04Z", "event":"ReceiveText", "From":"Bode Hub", "Message":"$STATION_NoFireZone_exited;", "Message_Localised":"No fire zone left.", "Channel":"npc" }
        self._SpaceShip__addSessionStat(journalentry, 'messages_received_%s' % journalentry['Channel'].lower())
    def __handleEvent_RedeemVoucher(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"RedeemVoucher", "Type":"bounty", "Amount":1000 }
        # { "timestamp":"2017-09-08T05:02:09Z", "event":"RedeemVoucher", "Type":"bounty", "Amount":18060, "Factions":[ { "Faction":"Democrats of LTT 15574", "Amount":9030 }, { "Faction":"Federation", "Amount":9030 } ] }
        # types are bounty, CombatBond, scannable, settlement
        self._SpaceShip__gainMoney(journalentry, 'bounty', journalentry['Amount'])
        self._SpaceShip__addSessionStat(journalentry, 'vouchers_redeemed_%s' % journalentry['Type'].lower())
    def __handleEvent_RefuelAll(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"RefuelAll", "Cost":317, "Amount":6.322901 }
        self._SpaceShip__loseMoney(journalentry, 'fuel', journalentry['Cost'])
        self._SpaceShip__addSessionStat(journalentry, 'fuel_bought', journalentry['Amount'])
    def __handleEvent_RefuelPartial(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"RefuelPartial", "Cost":83, "Amount":1.649000 }
        self._SpaceShip__handleEvent_RefuelAll(journalentry)
    def __handleEvent_Repair(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"Repair", "Item":"int_powerplant_size3_class5", "Cost":1100 }
        self._SpaceShip__loseMoney(journalentry, 'repairs', journalentry['Cost'])
    def __handleEvent_RepairAll(self, journalentry):
        # { "timestamp":"2017-09-08T05:48:04Z", "event":"RepairAll", "Cost":1172 }
        self.__handleEvent_Repair(journalentry)
    def __handleEvent_RestockVehicle(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"RestockVehicle", "Type":"SRV", "Loadout":"starter", "Cost":1030, "Count":1 }
        self._SpaceShip__loseMoney(journalentry, 'restockvehicle', journalentry['Cost'])
    def __handleEvent_Resurrect(self, journalentry):
        # { "timestamp":"2017-08-19T22:26:57Z", "event":"Resurrect", "Option":"rebuy", "Cost":978591, "Bankrupt":false }
        if journalentry['Option'] != 'free': # free rebuys still have a cost for some reason. Don't subtract the cost if you didn't actually pay for a rebuy
            self._SpaceShip__loseMoney(journalentry, 'rebuyship', journalentry['Cost'])
        if journalentry['Bankrupt']:
            self._SpaceShip__addSessionStat(journalentry, 'bankruptcy_declared')
    def __handleEvent_Scan(self, journalentry):
        # { "timestamp":"2016-09-22T10:40:44Z", "event":"Scan", "BodyName":"Bei Dou Sector JH-V b2-1 1", "DistanceFromArrivalLS":392.607605, "TidalLock":false, "TerraformState":"", "PlanetClass":"Icy body", "Atmosphere":"thin neon rich atmosphere", "Volcanism":"", "MassEM":0.190769, "Radius":4412562.000000, "SurfaceGravity":3.905130, "SurfaceTemperature":64.690628, "SurfacePressure":321.596558, "Landable":false, "SemiMajorAxis":117704065024.000000, "Eccentricity":0.000033, "Periapsis":5.692884, "OrbitalPeriod":43704092.000000, "RotationPeriod":104296.351563 }
        self._SpaceShip__addSessionStat(journalentry, 'stellar_object_scanned')
    def __handleEvent_Scanned(self, journalentry):
        # { "timestamp":"2017-09-08T06:02:47Z", "event":"Scanned", "ScanType":"Cargo" }
        # { "timestamp":"2017-09-07T05:51:09Z", "event":"Scanned", "ScanType":"Crime" }
        self._SpaceShip__addSessionStat(journalentry, 'scanned_for_%s' % journalentry['ScanType'].lower())
    def __handleEvent_ScientificResearch(self, journalentry):
        # Not Sure: { "timestamp":"2016-06-10T14:32:03Z", "event":"ScientificResearch", "Name":"materialname", "Category":"Manufactured", "Count":1}
        self._SpaceShip__addSessionStat(journalentry, 'community_goals_scientific_research')
    def __handleEvent_Screenshot(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"Screenshot", "Filename":"_Screenshots/Screenshot_0151.bmp", "Width":1600, "Height":900, "System":"Shinrarta Dezhra", "Body":"Founders World" }
        self._SpaceShip__addSessionStat(journalentry, 'screenshots_taken')
    def __handleEvent_SearchAndRescue(self, journalentry):
        # { "timestamp":"2017-11-08T04:41:26Z", "event":"SearchAndRescue", "Name":"usscargoblackbox", "Count":1, "Reward":2898 }
        # {"timestamp": "2017-11-08T04:41:27Z", "event": "SearchAndRescue", "Name": "personaleffects", "Count": 2, "Reward": 184}
        self._SpaceShip__gainMoney(journalentry, 'search_and_rescue', journalentry['Reward'])
        self._SpaceShip__loseCargo(journalentry, journalentry['Name'], journalentry['Count'], 'sold_search_and_rescue')
    def __handleEvent_SelfDestruct(self, journalentry):
        # { "timestamp":"2017-07-29T21:36:54Z", "event":"SelfDestruct" }
        self._SpaceShip__addSessionStat(journalentry, 'self_destructed')
    def __handleEvent_SellDrones(self, journalentry):
        # {u'Count': 4, u'timestamp': u'2017-09-13T05:14:36Z', u'TotalSale': 404, u'SellPrice': 101, u'Type': u'Drones', u'event': u'SellDrones'}
        # AKA selling limpets
        self._SpaceShip__gainMoney(journalentry,  'selldrones', journalentry['TotalSale'] )
        self._SpaceShip__loseCargo(journalentry, journalentry['Type'], journalentry['Count'], 'sold_drones')
    def __handleEvent_SellExplorationData(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"SellExplorationData", "Systems":[ "HIP 78085", "Praea Euq NW-W b1-3" ], "Discovered":[ "HIP 78085 A", "Praea Euq NW-W b1-3", "Praea Euq NW-W b1-3 3 a", "Praea Euq NW-W b1-3 3" ], "BaseValue":10822, "Bonus":3959 }
        self._SpaceShip__gainMoney(journalentry, 'exploration', journalentry['BaseValue'])
        self._SpaceShip__gainMoney(journalentry, 'exploration_bonus', journalentry['Bonus'])
    def __handleEvent_SendText(self, journalentry):
        # { "timestamp":"2017-09-03T20:14:32Z", "event":"SendText", "To":"$cmdr_decorate:#name=Dr. Knobz;", "To_Localised":"CMDR Dr. Knobz", "Message":"o7 cmdr" }
        self._SpaceShip__addSessionStat(journalentry, 'messages_sent')
    def __handleEvent_SetUserShipName(self, journalentry):
        # {u'timestamp': u'2017-09-08T06:20:25Z', u'UserShipId': u'BL-19P', u'event': u'SetUserShipName', u'UserShipName': u'The chubby pickle', u'ShipID': 7, u'Ship': u'python'}
        self.shipname = journalentry['UserShipName']
        self._SpaceShip__addSessionStat(journalentry, 'ship_name_set')
    def __handleEvent_ShieldState(self, journalentry):
        # { "timestamp":"2016-07-25T14:45:48Z", "event":"ShieldState", "ShieldsUp":false }
        if journalentry['ShieldsUp']:
            self._SpaceShip__addSessionStat(journalentry, 'shields_regained') # Shields_regained whether from combat or charging them back up after silent running.
        else:
            self._SpaceShip__addSessionStat(journalentry, 'shields_depleted')
    def __handleEvent_ShipyardBuy(self, journalentry):
        # { "timestamp":"2016-07-21T14:36:38Z", "event":"ShipyardBuy", "ShipType":"hauler", "ShipPrice":46262, "StoreOldShip":"SideWinder", "StoreShipID":2 }
        self._SpaceShip__loseMoney(journalentry, 'buyship', journalentry['ShipPrice'])
        self._SpaceShip__addSessionStat(journalentry, 'ships_bought')
    def __handleEvent_ShipyardNew(self, journalentry):
        "When you get a new ship, after you buy it"
        # { "timestamp":"2016-07-21T14:36:38Z", "event":"ShipyardNew", "ShipType":"hauler", "ShipID":4 }
        pass
    def __handleEvent_ShipyardSell(self, journalentry):
        # { "timestamp":"2016-07-21T15:12:19Z", "event":"ShipyardSell", "ShipType":"Adder", "SellShipID":6, "ShipPrice":79027, "System":"Eranin" }
        # System is optional
        self._SpaceShip__gainMoney(journalentry, 'shipsell', journalentry['ShipPrice'])
        self._SpaceShip__addSessionStat(journalentry, 'ships_sold')
    def __handleEvent_ShipyardSwap(self, journalentry):
        # { "timestamp":"2016-07-21T14:36:06Z", "event":"ShipyardSwap", "ShipType":"sidewinder", "ShipID":10, "StoreOldShip":"Asp", "StoreShipID":2 }
        self._SpaceShip__addSessionStat(journalentry, 'ships_swapped')
    def __handleEvent_ShipyardTransfer(self, journalentry):
        # { "timestamp":"2016-07-21T15:19:49Z", "event":"ShipyardTransfer", "ShipType":"SideWinder", "ShipID":7, "System":"Eranin", "Distance":85.639145, "TransferPrice":580 }
        self._SpaceShip__loseMoney(journalentry, 'transfership', journalentry['TransferPrice'])
        self._SpaceShip__addSessionStat(journalentry, 'ships_transferred')
    def __handleEvent_StartJump(self, journalentry):
        # { "timestamp":"2017-08-31T04:30:10Z", "event":"StartJump", "JumpType":"Supercruise" }
        self._SpaceShip__addSessionStat(journalentry, 'fsd_jump_started')
    def __handleEvent_SupercruiseEntry(self, journalentry):
        # { "timestamp":"2017-08-31T04:30:15Z", "event":"SupercruiseEntry", "StarSystem":"Wu Guinagi" }
        self._SpaceShip__addSessionStat(journalentry, 'supercruise_entered')
    def __handleEvent_SupercruiseExit(self, journalentry):
        # { "timestamp":"2017-08-31T04:35:15Z", "event":"SupercruiseExit", "StarSystem":"Wu Guinagi", "Body":"Ziegel Dock", "BodyType":"Station" }
        self._SpaceShip__addSessionStat(journalentry, 'supercruise_exited')
    def __handleEvent_Synthesis(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"Synthesis", "Name":"Repair Basic", "Materials":{ "iron":2, "nickel":1 } }
        self._SpaceShip__addSessionStat(journalentry, 'synthesized_something')
        for material in journalentry['Materials']:
            # we call the material raw here, it shouldn't matter if it's manufactured. We just need to specify that it's a physical material and not data
            self._SpaceShip__changeMaterial(journalentry, 'Raw', material['Name'], -material['Count'], 'synthesis')
    def __handleEvent_Touchdown(self, journalentry):
        # { "timestamp":"2017-08-31T04:52:38Z", "event":"Touchdown", "PlayerControlled":true, "Latitude":-4.009590, "Longitude":153.113800 }
        self._SpaceShip__addSessionStat(journalentry, 'planet_landings')
    def __handleEvent_USSDrop(self, journalentry):
        # { "timestamp":"2017-08-31T04:56:56Z", "event":"USSDrop", "USSType":"$USS_Type_Aftermath;", "USSType_Localised":"Combat aftermath detected", "USSThreat":0 }
        self._SpaceShip__addSessionStat(journalentry, 'uss_drops')
    def __handleEvent_Undocked(self, journalentry):
        # { "timestamp":"2017-08-31T04:29:47Z", "event":"Undocked", "StationName":"Bode Hub", "StationType":"Outpost" }
        self._SpaceShip__addSessionStat(journalentry, 'docking_undocked')
    def __handleEvent_VehicleSwitch(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"VehicleSwitch", "To":"Fighter" }
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"VehicleSwitch", "To":"Mothership" }
        pass
    def __handleEvent_WingAdd(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"WingAdd", "Name":"HRC-2" }
        pass
    def __handleEvent_WingInvite(self, journalentry):
        # {u'timestamp': u'2017-07-01T03:17:21Z', u'event': u'WingInvite', u'Name': u'BinaryEpidemic'}
        self._SpaceShip__addSessionStat(journalentry, 'wing_invites_sent')
    def __handleEvent_WingJoin(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"WingJoin", "Others":[ "HRC1" ] }
        self._SpaceShip__addSessionStat(journalentry, 'wings_joined')
    def __handleEvent_WingLeave(self, journalentry):
        # { "timestamp":"2016-06-10T14:32:03Z", "event":"WingLeave" }
        self._SpaceShip__addSessionStat(journalentry, 'wings_left')

if __name__ == '__main__':
    import optparse, sys
    opts = optparse.OptionParser(usage="%prog [options] [log dir]\nlog dir can be a network path or zip file.")
    opts.add_option('-o', '--oldest', action='store_true', dest='oldestonly', help='show the oldest logs only')
    opts.add_option('-n', '--newest', action='store_true', dest='newestonly', help='show the newest logs only')

    options, logdirs = opts.parse_args()
    # sanity check:
    if len(logdirs) > 1:
        print "Multiple log locations were specified. Please only specify one directory. Leaving this blank will use the default location."
        sys.exit(1)
    if options.oldestonly and options.newestonly:
        print "Conflicting options were used. If you want to see both the oldest and newest logs, don't use any options."
        sys.exit(2)
    # set up the logdir
    try:
        logdir = logdirs[0]
    except IndexError:
        logdir = None
    else:
        # check if the logdir is a zip and handle that:
        if logdir.lower().endswith('.zip'):
            if not zipfile.is_zipfile(logdir):
                print "The zip file specified is not actually a zipfile!"
                sys.exit(3)

    def printStat(session, attribute, description=None, forceprint=False, margs=()):
        """
        Print a line of text about a session stat. Do nothing if the stat is not a number or if it's 0. The text is indented 1 tab.
        :param session: a session object
        :param attribute: the str(attribute) from that session to print. This can also be a method that will be called.
        :param description: an optional description of the stat. If none is given, the stat name is printed
        :param forceprint: print this stat even if it's 0 or blank
        :param margs: arguments to pass attribute if it's a method
        :return: nothing
        """
        try: # try calling it as a method
            result = getattr(session, attribute)(*margs)
        except TypeError: # read the variable name
            result = getattr(session, attribute)
        # if DEBUG:
        #     forceprint=True
        if result != 0 or forceprint:
            pre = description
            if not pre:
                pre = attribute
            if margs: # don't print a heading for per hour
                print '\t ',
                pre = ''
            else:
                print '\t%s:' % pre,
            print ' '*(35-len(pre)),
            print format(result, ','),
            if margs:
                print "per hour",
            print

    if logdir:
        s = SpaceShip(journaldir=logdir)
    else:
        s = SpaceShip()
    s.handleEvents(s.parseJournal(startup=True))

    # print out info about the current state of the player and ship:
    print "Stats for CMDR %s" % s.playername
    print "Current Balance: %s" % format(s.moneycurrentbalance, ',')
    print "Current rank:"
    for rank in ('Combat', 'Trade', 'Explore', 'Empire', 'Federation', 'CQC'):
        print "\t%s: %s - %s" % (rank, getattr(s, 'rank_%s' % rank.lower()), getattr(__import__(__name__), '%sRANKS' % rank.upper())[getattr(s, 'rank_%s' % rank.lower())])
    print "Current Cargo:",
    if not s.cargo:
        print "None"
    else:
        print
        for cargo in s.cargo:
            print "\t%s: %s" % (cargo, s.cargo[cargo]['amount'])
            if s.cargo[cargo]['haulage']:
                print '\t\thaulage: %s' % s.cargo[cargo]['haulage']
            if s.cargo[cargo]['haulage']:
                print '\t\thaulage: %s' % s.cargo[cargo]['haulage']

    print "Current Physical Materials: %s/1000" % s.materials.getTotalAmount()
    print "Current Data Materials: %s/500" % s.datamaterials.getTotalAmount()

    # print out info about missions:
    s.missions.purgeExpired()
    print "Current Missions:",
    if not s.missions:
        print "None"
    else:
        print len(s.missions),
        print "\n\tMissions sorted by destination port:"
        missions = s.missions.getSortedDestinations()
        for num in range(len(missions)):
            print "\t\t%d: %s - %s" % (missions[num][0], missions[num][1], missions[num][2])
        print "\tMissions sorted by reward:"
        missions = s.missions.getSortedRewards()
        strlen = len(format(s.missions[missions[0][1]]['Reward'], ',')) # This tells us how much to indent the lesser amounts of money
        for num in range(len(missions)):
            print "\t\t%s%s: %s - %s" % (' '*(strlen-len(format(missions[num][0], ','))), format(missions[num][0], ','), s.missions[missions[num][1]]['DestinationSystem'], s.missions[missions[num][1]]['DestinationStation'])
        print "\tMissions sorted by expiration time:"
        missions = s.missions.getSortedExpiration()
        for num in range(len(missions)):
            print "\t\t%s: %s - %s" % (missions[num][0].strftime('%m/%d/%Y %H:%M:%S %Z'), s.missions[missions[num][1]]['DestinationSystem'], s.missions[missions[num][1]]['DestinationStation'])
        #for mission in s.missions.values():
        #    print "Type: %s\tFaction: %s\t\t\tTo: %s - %s" % (mission['Name'], mission['Faction'], mission['DestinationSystem'], mission['DestinationStation'])
        # print passenger info:
        print "Current Passengers:",
        if not s.passengers:
            print "None"
        else:
            print
            for pax in s.passengers:
                print "\t%s %ss" % (s.passengers[pax]['count'], s.passengers[pax]['type']),
                if s.passengers[pax]['vip']:
                    print '\tVIP',
                if s.passengers[pax]['wanted']:
                    print '\tWanted',
                print

    # print out detailed session statistics:
    for session in (('last game start', 'game', options.oldestonly), ('oldest logs', 'oldest', options.newestonly)):
        if session[2]: # skip reporting on this session if the user requested to only see the other session
            continue
        # print out a nice little session title header with information about when the session started, ended, and it's duration:
        sessionlength = s.sessionstats[session[1]].latesttime - s.sessionstats[session[1]].starttime
        print "\nStats since %s (%s-%0.2d-%0.2d %s:%0.2d" % (session[0], s.sessionstats[session[1]].starttime.year, s.sessionstats[session[1]].starttime.month, s.sessionstats[session[1]].starttime.day, s.sessionstats[session[1]].starttime.hour,
                                                     s.sessionstats[session[1]].starttime.minute),
        # if this session lasted between 2 dates, print both dates. If the session was all on the same day, only print the end time and not the end date
        if (s.sessionstats[session[1]].starttime.year != s.sessionstats[session[1]].latesttime.year) or \
                (s.sessionstats[session[1]].starttime.month != s.sessionstats[session[1]].latesttime.month) or \
                (s.sessionstats[session[1]].starttime.day != s.sessionstats[session[1]].latesttime.day):
            print "- %s-%0.2d-%0.2d" % (s.sessionstats[session[1]].latesttime.year, s.sessionstats[session[1]].latesttime.month, s.sessionstats[session[1]].latesttime.day),
        else: # the session was all in the same day, don't show the date a second time
            sys.stdout.write('-')
        print "%s:%0.2d, duration:" % (s.sessionstats[session[1]].latesttime.hour, s.sessionstats[session[1]].latesttime.minute),
        if sessionlength.days > 0:
            print "%s days" % sessionlength.days,
        print "%sh:%0.2dm):" % (sessionlength.seconds/60/60, sessionlength.seconds/60%60)

        # First print some more important stats with prettier names:
        printStat(s.sessionstats[session[1]], 'getNetMoneyChange', 'Money Net Change', forceprint=True)
        printStat(s.sessionstats[session[1]], 'getScorePerHour', 'Money Net Change per hour', forceprint=True, margs=('getNetMoneyChange',))
        printStat(s.sessionstats[session[1]], 'getTotalMoneyGained', 'Total Money Gained', forceprint=True)
        printStat(s.sessionstats[session[1]], 'getScorePerHour', 'Total Money Gained per hour', forceprint=True, margs=('getTotalMoneyGained',))
        printStat(s.sessionstats[session[1]], 'getTotalMoneySpent', 'Total Money Spent', forceprint=True)
        printStat(s.sessionstats[session[1]], 'getTotalMoneyGainedFromCommoditiesSold', 'Total Money from commodities sold')
        # Now go through all of the stats in the session. Add everything that should be skipped to this big not in tuple. Things that should be skipped include methods that don't return stats and stats already given.
        for stat in [a for a in dir(s.sessionstats[session[1]]) if not a.startswith('_') and a not in ('reset', 'addStat', 'startRecording', 'name', 'isrecording', 'starttime', 'latesttime', 'visited_systems', 'visited_stations', 'mined_elements',
                                                                                                       'getNetMoneyChange', 'getTotalMoneyGained', 'getTotalMoneySpent', 'getTotalMoneyGainedFromCommoditiesSold', 'getScorePerHour')]:
            printStat(s.sessionstats[session[1]], stat)

        # Show the top 5 most visited systems
        for visitedtype in ('systems', 'stations'):
            print "\nTotal %s visited this session: %s" % (visitedtype, getattr(s.sessionstats[session[1]], ''.join(('visited_', visitedtype))).getTotalVisited())
            top5 = getattr(s.sessionstats[session[1]], ''.join(('visited_', visitedtype))).getMostVisited()[:5]

            print "Top 5 most visited %s:" % visitedtype
            for num in range(len(top5)):
                print "%d: %s" % (top5[num][0], top5[num][1]),
                try:
                    print "- %s" % top5[num][2]
                except IndexError:
                    print

        # Show the top 5 most mined things if mining was done:
        if s.sessionstats[session[1]].mined_elements.getTotalMined():
            print "\nTotal mined elements this session: %s" % s.sessionstats[session[1]].mined_elements.getTotalMined()
            top5 = s.sessionstats[session[1]].mined_elements.getMostMined()[:5]
            print "Top 5 most mined elements:"
            for num in range(len(top5)):
                print "%d: %s" % (top5[num][0], top5[num][1])