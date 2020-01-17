#!/usr/bin/env python
# tweepy-bots/bots/autoreply.py

import tweepy
import logging
from config import create_api
import time
from databasefunctions import get_player_list, port, username, password, update_num_subscribers, get_player_id, store_temp_fixture, get_player_name, delete_subscriber, store_schedules
from databasefunctions import dbname, endpoint, set_cursor, open_database, store_subscriber, get_subscriber_list, get_schedule, get_team_name, check_subscription_details, delete_all_schedules
import threading
from datetime import datetime, timezone
import multiprocessing
import sched
import requests
import os
from score_calculation import Stats
import pytz
import schedule

# Initializations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
scheduler = sched.scheduler(time.time, time.sleep)
football_api_key = os.environ.get("rapid_football_api_key")
headers = {'x-rapidapi-key': football_api_key}

# Constants
INITIAL_TWEET_ID = '1216502764886544384' 
INITIAL_TWEET_IMG_ID = '1214695241145552896'
LINEUP_ENDPOINT = 'https://api-football-v1.p.rapidapi.com/v2/lineups/'
PLAYER_EVENTS_ENDPOINT = 'https://api-football-v1.p.rapidapi.com/v2/players/fixture/'
LINEUP_STATUS_STARTXI = 'startingXI'
LINEUP_STATUS_SUBSTITUTES = 'substitutes'
LINEUP_STATUS_NA = 'NA'
STOP_TRACKING_PROMPT = 'stop'
DAY_SECS = 86400 # total seconds in 24 hours
HOUR_SECS = 3600
DELAY_MENTIONS = 600 #delay between checking for new mentions



def match_full_names(tweet_text, keywords):
    '''
    Matches names of players from tweets. Looks for the full name as specified in the bot and in the database. 
    '''
    for keyword in keywords:
        if keyword in tweet_text:
            return keyword
    return None

def check_mentions(api, keywords, since_id):
    '''
    Checks mentions to the bot account and takes action accordingly.
    '''
    connection = open_database(dbname, username, password, endpoint, port)
    cursor = set_cursor(connection)
    print('Started checking mentions')
    new_since_id = since_id
    while True:
        logger.info("Retrieving mentions")
        for tweet in tweepy.Cursor(api.mentions_timeline, since_id=new_since_id).items():

            new_since_id = max(tweet.id, new_since_id)
            # if tweet.in_reply_to_status_id is not None or tweet.id == INITIAL_TWEET_ID: # id for the initial tweet
            #     continue
            # if the tweet has not been replied to and if it is not the initial tweet then continue with 
            # the process else go to the next value in the loop
            if tweet.in_reply_to_status_id is not None:
                continue
            if str(tweet.id) != INITIAL_TWEET_ID:
                # If a user decides to stop tracking, then tracking will stop for all the players he has subscribed to. This can be 
                # modified later. // TO ADD
                if STOP_TRACKING_PROMPT in tweet.text:
                    # remove subscriber from the subscribers table and stop sending any more updates.
                    delete_subscriber(tweet.user.screen_name)
                    continue
                matched_player = match_full_names(tweet.text, keywords)
                if  matched_player is not None:
                    logger.info(f"Answering to {tweet.user.name}")

                    if not tweet.user.following:
                        # follow the user and add his information to the database.
                        store_subscriber(cursor, connection, tweet.user.screen_name, matched_player, tweet.id)
                        tweet.user.follow()
                    try:
                        api.update_status(
                            status=f"@{tweet.user.screen_name} You're now tracking {matched_player}",
                            in_reply_to_status_id=tweet.id,
                            auto_populate_reply_metadata=True
                        )
                    except:
                        logger.info("Moving on...")
                else:

                    logger.info(f"{tweet.id} problematic")
                    # if no player is found, notify the user that he should pick players from the given list. Consecutive duplicate
                    # tweets/replies cannot be posted using Twitter's API.
                    try:
                        api.update_status(
                            status=f"@{tweet.user.screen_name} I could not find the player you're looking for. Please choose a player from the list here: shorturl.at/wCLSU\n",
                            in_reply_to_status_id=tweet.id,
                            auto_populate_reply_metadata=True
                        )
                    except:
                        # check for error code 187 (duplicate tweet)
                        print('Something went wrong here')
                    
        logger.info("Waiting...")
        time.sleep(DELAY_MENTIONS)
    

def start_tracking(api, cursor, connection):
    '''
    update the players table to include another column that would record number of subscribers who are
    tracking the player. Increment this number when we find a new subscriber who wishes to track this player
    and decrement 1 when a user switches to another player or unsubscribes from the service.
    Should run as per schedule.
    '''
    print('Started tracking')
    connection = open_database(dbname, username, password, endpoint, port)
    cursor = set_cursor(connection)
    # it is possible that a new subscriber joins when a relevant game is about to begin within an hour. He 
    # should also get to know about the lineups instead of getting ignored till the next game
    # get list of subscribers
    while True:
        subscribers = get_subscriber_list(cursor, connection)
        # iterate over subscribers
        for subscriber in subscribers:
            # twitter_handle, player_id, team_id
            team_id = subscriber[2]
            player_id = subscriber[1]
            twitter_handle = subscriber[0]
            original_tweet_id = subscriber[3]
            schedule = get_schedule(cursor, connection, team_id)
            for fixture in schedule:
                # pick the event_timestamp and compare the difference between now and the event_timestamp
                now_utc = datetime.now(timezone.utc).strftime("%b %d %Y %H:%M:%S")
                epoch_now = int(time.mktime(time.strptime(now_utc, "%b %d %Y %H:%M:%S")))
                fixture_timestamp = fixture[7]
                fixture_id = fixture[0]
                # time difference between fixtures
                time_diff = abs(fixture_timestamp - epoch_now)
                #if fixture_timestamp > epoch_now and time_diff <= 86400:
                if time_diff <= 172800: 
                    # this means the game is within 24 hours, add it to temp_fixture table
                    print(f"{fixture[3]} vs {fixture[5]} to start at {fixture[6]}")
                    # store_temp_fixture(cursor, connection, fixture)
                    # once the fixture is stored in the temp_fixtures table, we can schedule a call to look up
                    # the table one hour before the event timestamp. 
                    delay = float(time_diff) - float(HOUR_SECS) if time_diff > HOUR_SECS else 0
                    # delay = 10
                    team_name = get_team_name(cursor, connection, team_id)
                    scheduler.enter(delay, 1, tweet_lineup_update, (api, team_id, team_name, player_id, fixture_id, twitter_handle, original_tweet_id, fixture_timestamp,))
                    scheduler.run()

        time.sleep(DAY_SECS)


def tweet_lineup_update(api, team_id, team_name, player_id, fixture_id, twitter_handle, tweet_id, start_timestamp):
    '''
    Tweets out update on whether player is in the lineup or not
    '''
    logger.info('getting lineup update')
    player_name = get_player_name(player_id)
    player_status = get_team_lineup_status(team_id, team_name, player_id, fixture_id)
    if player_status == LINEUP_STATUS_STARTXI or player_status == LINEUP_STATUS_SUBSTITUTES:
        # tweet out an update saying the player is in the lineup
        logger.info('Player is in the lineup')
        try:
            api.update_status(
                            status=f"@{twitter_handle} {player_name} is playing today. I'll be back with more updates",
                            in_reply_to_status_id=tweet_id,
                            auto_populate_reply_metadata=True
                        )
        except:
            print('Could not publish lineup tweet')
        # Since the player is in the lineup and we should continue monitoring.
        # schedule call to the events API for the given player and fixture id
        delay = HOUR_SECS + 110 * 60 # 105 mins after the game
        # delay = 20
        scheduler.enter(delay, 1, get_fixture_events, (api, fixture_id, player_id, player_name, tweet_id,))
        scheduler.run()
    else:
        print('Player is not in the lineup')
        try:
            api.update_status(
                            status=f"@{twitter_handle} {player_name} is not playing today",
                            in_reply_to_status_id=tweet_id,
                            auto_populate_reply_metadata=True
                        )
        except:
            print('Could not publish lineup tweet')


def get_team_lineup_status(team_id, team_name, player_id, fixture_id):
    '''
    Gets the lineups for the given team for a given fixture. Returns if the player is in the starting line-up
    or among the substitutes.
    '''
    print('getting lineup status')
    endpoint = f"{LINEUP_ENDPOINT}{fixture_id}"
    # get the dictionary of lineups for both teams. Keys of this dictionary are the team names
    lineups = requests.get(endpoint, headers=headers).json()['api']['lineUps']
    print(f"team name is {team_name}")
    if team_name in lineups:
        startXI = [player['player_id'] for player in lineups[team_name]['startXI']]
        print(f"startXI player ids are {startXI}")
        substitutes = [player['player_id'] for player in lineups[team_name]['substitutes']]
        print(f"substitutes are {substitutes}")
        if int(player_id) in startXI:
            return LINEUP_STATUS_STARTXI
        elif int(player_id) in substitutes:
            return LINEUP_STATUS_SUBSTITUTES
        else:
            return LINEUP_STATUS_NA


def get_fixture_events(api, fixture_id, player_id, player_name, tweet_id):
    '''
    Posts tweet with the relevant statistics of the given player in the given fixture. 
    (later) We'll evaluate the impact score using these metrics.
    '''
    print('getting fixture events')
    # it is possible that the game is still underway when this API is called. We have a time duration of 110 minutes after the 
    # call to the lineups API. For knockout games, and for games that have stretched because of long injury times, we may have to schedule
    # another call after delaying it for a few more mins. //TO ADD
    endpoint = f"{PLAYER_EVENTS_ENDPOINT}{fixture_id}"
    print(football_api_key)
    players = requests.get(endpoint, headers=headers).json()['api']['players']
    player_details = {}
    for player_dict in players:
        if player_dict['player_id'] == int(player_id):
            player_details = player_dict
            break
    

   # get the necessary details from player_details and form the string to be shown. We'd also have to compute the total no.
   # of characters in the final string and check if it can be accommodated in one tweet.
    '''
    {'event_id': 157064, 'updateAt': 1578817262, 'player_id': 19194, 'player_name': 'Tammy Abraham', 'team_id': 49,
     'team_name': 'Chelsea', 'number': 9, 'position': 'F', 'rating': '9.2', 'minutes_played': 77,
      'captain': 'False', 'substitute': 'False', 'offsides': None, 'shots': {'total': 4, 'on': 3},
       'goals': {'total': 3, 'conceded': 0, 'assists': 0}, 'passes': {'total': 11, 'key': 0, 'accuracy': 68},
        'tackles': {'total': 0, 'blocks': 1, 'interceptions': 0}, 'duels': {'total': 0, 'won': 0},
         'dribbles': {'attempts': 2, 'success': 1, 'past': 0}, 'fouls': {'drawn': 1, 'committed': 3}, 
         'cards': {'yellow': 1, 'red': 0}, 'penalty': {'won': 0, 'commited': 0, 'success': 0, 'missed': 0, 'saved': 0}}
    '''
    tweet_str = f"Here are the updates for {player_name} from the game:\n {create_player_update_tweet_text(player_details)}"
    try:
        api.update_status(
                        status=tweet_str,
                        in_reply_to_status_id=tweet_id,
                        auto_populate_reply_metadata=True
                    )
    except:
        print('Could not publish player stats')

    

def create_player_update_tweet_text(player_details):
    player_stats = Stats(player_details)
    impact_score = player_stats.compute_impact_score()
        
    # tweet_str = f"He scored {num_goals_scored} goals and provided {num_assists} assists. He played {num_key_passes} key passes and had {num_shots_on_target} shots on target. He tackled {num_tackles} times, blocked {num_blocks} shots and intercepted {num_interceptions} passes. He was taken off after {mins_played} minutes."
    # print(len(tweet_str))
    # start creating the string. 
    tweet_str = f"Mins played: {player_stats.mins_played}\nGoals: {player_stats.num_goals_scored}\n \
                Assists: {player_stats.num_assists}\nShots on target: {player_stats.num_shots_on_target}\nPenalties: {player_stats.num_penalties}\n \
                Key passes: {player_stats.num_key_passes}\nDribbles: {player_stats.num_dribbles}\nTackles: {player_stats.num_tackles}\nBlocks: {player_stats.num_blocks}\n \
                Interceptions: {player_stats.num_interceptions}\n"
    if player_stats.card_yellow == True:
        tweet_str += f"Yellow card: Yes\n"
    if player_stats.card_red == True:
        tweet_str += f"Red card: Yes\n"
    tweet_str += f"Impact score: {impact_score}\n"

    return tweet_str

def get_players_from_db(cursor, connection):
    '''
    Fetches player names from the database and returns them
    '''
    players = get_player_list(cursor, connection)
    return players

def update_schedules():
    '''
    Updates team schedules in the database on every Tuesday morning UTC time
    '''
    while True:
        print('Updating schedules')
        current_utc_time = datetime.now(pytz.utc)
        if current_utc_time.isoweekday() == 2 and current_utc_time.hour == 2: #Update on Tuesday, 2:00AM UTC time
            required_team_ids = [33, 39, 40, 42, 46, 47, 49, 50]
            db_connection = open_database(dbname, username, password, endpoint, port)
            cursor = set_cursor(db_connection)
            delete_all_schedules(cursor, db_connection)
            # get fixtures for all these teams
            for team_id in required_team_ids:
                fixture_dicts = get_fixtures(team_id)
                store_schedules(cursor, db_connection, fixture_dicts)  
            time.sleep(DAY_SECS)

def get_fixtures(team_id):
    '''
    Returns fixtures of given team in the current season
    '''
    fixtures_endpoint = 'https://api-football-v1.p.rapidapi.com/fixtures/team/{}'.format(team_id)
    fixtures_data = requests.get(fixtures_endpoint, headers=headers)
    fixtures = fixtures_data.json()['api']['fixtures']
    fixtures_current = []
    for key, fixture in fixtures.items():
        # get fixtures after 12AM, Aug. 8, 2019.
        if int(fixture['event_timestamp']) > 1565226000:
        # if fixture['league_id'] == '524' or fixture['league_id'] == '530' or fixture['league_id'] == '1063':
            fixtures_current.append(fixture)
    return fixtures_current

def make_first_tweet():
    # Tweet out the list of players available for tracking
    api = create_api()
    # upload image
    image_response = api.media_upload('players.png')
    print(image_response.media_id_string)
    api.update_status(status="""Here are the players available for tracking. To track the players write '@PlayerTracker2 track <player name>'. Please make sure you spell the name correctly.""",
                         media_ids=[image_response.media_id_string])  

def main():
    # make_first_tweet()
    db_connection = open_database(dbname, username, password, endpoint, port)
    cursor = set_cursor(db_connection)
    api = create_api()
    since_id = 1
    players = get_players_from_db(cursor, db_connection)
    cursor.close()
    db_connection.close()

    # start processes. Each process will use its own cursor and db connection.
    # start process to monitor mentions
    mentions_process = multiprocessing.Process(target=check_mentions, args=(api, players, since_id,))
    mentions_process.start()

    # start another process to go through all subscribers
    check_subscriber_process = multiprocessing.Process(target=start_tracking, args=(api, cursor, db_connection,))
    check_subscriber_process.start()

    # start another process to update fixture schedule once every week. Make sure to not update during games.
    # Use scheule library not sched. Update every Tuesday
    update_schedules_process = multiprocessing.Process(target=update_schedules)
    update_schedules_process.start()

if __name__ == "__main__":
    main()
