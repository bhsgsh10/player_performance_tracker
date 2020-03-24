#!/usr/bin/env python
# tweepy-bots/bots/autoreply.py

import tweepy
import logging
from config import create_api
import time
from databasefunctions import get_player_list, port, username, password, update_num_subscribers, get_player_id, store_temp_fixture, get_player_name, delete_subscriber, store_schedules, update_num_subscribers_from_id, update_tracking_status
from databasefunctions import dbname, endpoint, set_cursor, open_database, store_subscriber, get_subscriber_list, get_schedule, get_team_name, check_subscription_details, delete_all_schedules, check_subscriber_exists, get_player_twitter_handle
import threading
from datetime import datetime, timezone
import multiprocessing
import sched
import requests
import os
from score_calculation import Stats
import pytz
import schedule
import decimal
import pprint
from datetime import date

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
START_TRACKING_PROMPT = 'track'        
DAY_SECS = 86400 # total seconds in 24 hours
HOUR_SECS = 3600
MIN_SECS = 60
DELAY_MENTIONS = 600 #240 #delay between checking for new mentions



def match_full_names(tweet_text, keywords):
    '''
    Matches names of players from tweets. Looks for the full name as specified in the bot and in the database. 
    '''
    for keyword in keywords:
        if keyword in tweet_text:
            return keyword
    return None

def post_tweet(api, tweet_text, in_reply_id):
    try:
        api.update_status(
            status=tweet_text,
            in_reply_to_status_id=in_reply_id,
            auto_populate_reply_metadata=True
        )
    except tweepy.TweepError as e:
        logger.info(e.response.text)

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
            
            # check if tweet text contains 'track' or 'stop'. Should be able to identify if they are separate words
            # The format of the tweet is such that it should contain at least 2 words. First should be the mention and the second would be 
            # either 'track' or 'stop'. Starting from the third word, we will have the player's name. 

            if str(tweet.id) != INITIAL_TWEET_ID:
                # check if the user is trying to subscribe or stop subscription. Split tweet text into words and check the first word.
                words = tweet.text.split()
                print(words)
                if START_TRACKING_PROMPT in words[1]:
                    # check if the subscriber and player already exists in the database. If not post an update tweet and add to the subscribers table
                    # else don't do anything
                    matched_player = match_full_names(tweet.text, keywords)
                    logger.info(f"matched player is {matched_player}")
                    if matched_player is not None:
                        subscriber_exists = check_subscriber_exists(tweet.user.screen_name, matched_player)
                        if subscriber_exists == False:
                            logger.info(f"Answering to {tweet.user.name}")
                            logger.info(f"Tweet text is {tweet.text}")
                            store_subscriber(cursor, connection, tweet.user.screen_name, matched_player, tweet.id)
                            if not tweet.user.following:
                                # follow the user and add his information to the database.
                                tweet.user.follow()
                            
                            logger.info(f"@{tweet.user.screen_name} You're now tracking {matched_player}")
                            post_tweet(api, f"@{tweet.user.screen_name} You're now tracking {matched_player}", tweet.id)
                    else:
                        try_again_text = f"@{tweet.user.screen_name} I could not find the player you're looking for. \
                                         Please choose a player from the list here: shorturl.at/wCLSU\n"
                        logger.info(try_again_text)
                        post_tweet(api, try_again_text, tweet.id)
                
                elif STOP_TRACKING_PROMPT in words[-1]:
                    # remove subscriber from table. It is possible that the stop tweet came before the user subscribed to 
                    logger.info('Found stop')
                    if tweet.id >= new_since_id:
                        logger.info('Deleting subscriber')
                        # remove subscriber from the subscribers table and stop sending any more updates.
                        delete_subscriber(tweet.user.screen_name)
                        api.destroy_friendship(tweet.user.screen_name)
                        continue
                    else:
                        break #mentions before the stop tweet should not be honored
                    
        logger.info("Waiting...")
        time.sleep(DELAY_MENTIONS)
    

def start_tracking(api):
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
        logger.info(subscribers)
        # iterate over subscribers
        for subscriber in subscribers:
            tracking_status = subscriber[4]
            if tracking_status == False:
                # twitter_handle, player_id, team_id
                team_id = subscriber[2]
                player_id = subscriber[1]
                twitter_handle = subscriber[0]
                original_tweet_id = subscriber[3]

                schedule = get_schedule(cursor, connection, team_id)
                for fixture in schedule:
                    # pick the event_timestamp and compare the difference between now and the event_timestamp
                    now_utc = datetime.now().strftime("%b %d %Y %H:%M:%S")
                    epoch_now = int(time.mktime(time.strptime(now_utc, "%b %d %Y %H:%M:%S")))
                    
                    fixture_timestamp = fixture[7]
                    
                    fixture_id = fixture[0]
                    # time difference between fixtures
                    time_diff = fixture_timestamp - epoch_now
                    delay = -999
                    if abs(time_diff) < DAY_SECS:
                        if time_diff > 0:
                            if time_diff < HOUR_SECS:
                                update_tracking_status(twitter_handle, player_id, True)
                                delay = 0
                                logger.info("match is about to begin in an hour, delay should be 0")
                            elif time_diff < DAY_SECS:
                                update_tracking_status(twitter_handle, player_id, True)
                                delay = float(time_diff) - float(HOUR_SECS)
                                logger.info("schedule a call for lineups at the appropriate time")
                        elif time_diff < 0:
                            update_tracking_status(twitter_handle, player_id, True)
                            logger.info("match has either begun or has already ended.")
                            estimated_end_time = fixture_timestamp + 120*60
                            if estimated_end_time - epoch_now > 0:
                                delay = 0
                                logger.info("match is ongoing, delay is 0")
                            else:
                                delay = -999
                                logger.info("match is over, nothing to do here")

                    if delay >= 0:
                        team_name = get_team_name(cursor, connection, team_id)
                        player_updates_process = multiprocessing.Process(target=player_updates, args=(delay, api, team_id, team_name, player_id, fixture_id, twitter_handle, original_tweet_id, fixture_timestamp, epoch_now,))
                        player_updates_process.start()

        time.sleep(MIN_SECS*5)


def player_updates(delay, api, team_id, team_name, player_id, fixture_id,
                     twitter_handle, original_tweet_id, fixture_timestamp, current_time):
    scheduler.enter(delay, 1, tweet_lineup_update, (api, team_id, team_name, player_id, fixture_id, twitter_handle, original_tweet_id, fixture_timestamp, current_time))
    scheduler.run()

def tweet_lineup_update(api, team_id, team_name, player_id, fixture_id, twitter_handle, tweet_id, start_timestamp, current_time):
    '''
    Tweets out update on whether player is in the lineup or not
    '''
    logger.info('getting lineup update')
    player_name = get_player_name(player_id)
    player_status = get_team_lineup_status(team_id, team_name, player_id, fixture_id)
    print(player_status)
    if player_status == LINEUP_STATUS_STARTXI or player_status == LINEUP_STATUS_SUBSTITUTES:
        # tweet out an update saying the player is in the lineup
        logger.info('Player is in the lineup')
        post_tweet(api, f"@{twitter_handle} {player_name} is playing today. I'll be back with more updates", tweet_id)
        # Since the player is in the lineup and we should continue monitoring.
        # schedule call to the events API for the given player and fixture id

        delay = float(110*60 + (start_timestamp - current_time))
        logger.info(delay)
        # delay = 20
        scheduler.enter(delay, 1, get_fixture_events, (api, fixture_id, player_id, player_name, tweet_id, twitter_handle,))
        scheduler.run()
    else:
        post_tweet(api, f"@{twitter_handle} {player_name} is not playing today", tweet_id)
        print('Player is not in the lineup')


def get_team_lineup_status(team_id, team_name, player_id, fixture_id):
    '''
    Gets the lineups for the given team for a given fixture. Returns if the player is in the starting line-up
    or among the substitutes.
    '''
    print('getting lineup status')
    endpoint = f"{LINEUP_ENDPOINT}{fixture_id}"
    # get the dictionary of lineups for both teams. Keys of this dictionary are the team names
    lineups = requests.get(endpoint, headers=headers).json()['api']['lineUps']
    print(f"team id is {team_id}")

    teams = list(lineups.keys())
    team1_id = str(lineups[teams[0]]['startXI'][0]['team_id'])
    team2_id = str(lineups[teams[1]]['startXI'][0]['team_id'])

    matched_team_name = ''
    if team_id == team1_id:
        matched_team_name = teams[0]
    elif team_id == team2_id:
        matched_team_name = teams[1]

    if team_id == team1_id or team_id == team2_id:
        startXI = [player['player_id'] for player in lineups[matched_team_name]['startXI']]
        substitutes = [player['player_id'] for player in lineups[matched_team_name]['substitutes']]
        if int(player_id) in startXI:
            logger.info('Found player in startXI')
            return LINEUP_STATUS_STARTXI
        elif int(player_id) in substitutes:
            return LINEUP_STATUS_SUBSTITUTES
            logger.info('Found player in substitutes')
        else:
            logger.info('Did not find player')
            return LINEUP_STATUS_NA
    logger.info('Did not find team')

def get_fixture_events(api, fixture_id, player_id, player_name, tweet_id, twitter_handle):
    '''
    Posts tweet with the relevant statistics of the given player in the given fixture. 
    (later) We'll evaluate the impact score using these metrics.
    '''
    print('getting fixture events')
    # check match finished status here first. If match has not finished, then call this function again with a delay of 10 mins.

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
    tweet_str = f"Here are the updates for {player_name} from the game:\n{create_player_update_tweet_text(player_details)}"
    post_tweet(api, tweet_str, tweet_id)
    delay = HOUR_SECS
    scheduler.enter(delay, 1, repost_popular_tweets, (api, player_id, player_name, tweet_id, twitter_handle,))
    scheduler.run()
    # update tracking status to false once again
    update_tracking_status(twitter_handle, player_id, False)

def create_player_update_tweet_text(player_details):
    player_stats = Stats(player_details)
    impact_score = player_stats.compute_impact_score()
        
    # tweet_str = f"He scored {num_goals_scored} goals and provided {num_assists} assists. He played {num_key_passes} key passes and had {num_shots_on_target} shots on target. He tackled {num_tackles} times, blocked {num_blocks} shots and intercepted {num_interceptions} passes. He was taken off after {mins_played} minutes."
    # print(len(tweet_str))
    # start creating the string. 
    tweet_str = f"Mins played: {player_stats.mins_played}\n\Goals: {player_stats.num_goals_scored}\nAssists: {player_stats.num_assists}\nShots on target: {player_stats.num_shots_on_target}\nPenalties: {player_stats.num_penalties}\nKey passes: {player_stats.num_key_passes}\nDribbles: {player_stats.num_dribbles}\nTackles: {player_stats.num_tackles}\nBlocks: {player_stats.num_blocks}\n\Interceptions: {player_stats.num_interceptions}\n"
    if player_stats.card_yellow == True:
        tweet_str += f"Yellow card: Yes\n"
    if player_stats.card_red == True:
        tweet_str += f"Red card: Yes\n"
    tweet_str += f"Impact score: {impact_score}\n"

    return tweet_str

def repost_popular_tweets(api, player_id, player_name, tweet_id, twitter_handle):
    '''
    Replies with the most popular tweets about the player. Max 5 replies.
    '''
    # this will be an array of tweets that we get using the player's name and twitter handle.
    # let's fetch player's twitter handle from the database
    twitter_handle = get_player_twitter_handle(player_id)
    #URLify the player_name, meaning substitute space between first and last names with %20
    name = player_name.strip().replace(' ', "%20")
    search_str = f'"{name}"'
    if twitter_handle is not None:
        search_str += f'OR {twitter_handle}'
    tweets = tweepy.Cursor(api.search, 
                           q='"Marcos%20Alonso" OR @marcosalonso03',
                           lang="en",
                           since=date.today(),
                           tweet_mode='extended').items(100)
    # we need to collect five tweets that have the highest score among the collected tweets
    # For that first let's iterate over all the tweets and compute score for each of them. Then we can pick the best ones.
    top_tweets = sort_top_tweets(tweets)

    for top_tweet in top_tweets:
        tweet_str = f'https://twitter.com/{top_tweet.user.screen_name}/status/{top_tweet.id}'
        post_tweet(api, tweet_str, tweet_id)

def sort_top_tweets(tweets):
    '''
    Takes a collection of tweets and returns max 5 tweets sorted on the basis of score
    '''
    tweet_score_list = []
    for tweet in tweets:
        score = compute_tweet_popularity_score(tweet) 
        tweet_score_list.append((tweet.id, score))
    
    tweet_score_list.sort(key = lambda tweet_score: tweet_score[1])
    num_tweets = 5 if len(tweet_score_list) >= 5 else len(tweet_score_list)
    top_tweet_tuples = tweet_score_list[:num_tweets]
    top_tweets = [tweet for tweet in tweets if tweet.id in [next((tweet_id for tweet_id, tweet_score in top_tweet_tuples if tweet_id == tweet.id),0)]]

    return top_tweets

def compute_tweet_popularity_score(tweet):
    '''
    Computes score for a given tweet
    '''
    score = tweet.favorite_count + tweet.retweet_count 
    return score

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
        current_utc_time = datetime.now(pytz.utc)
        if current_utc_time.isoweekday() == 2 and current_utc_time.hour == 2: #Update on Tuesday, 2:00AM UTC time
            print('Updating schedules')
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
    '''
    Tweet out the list of players available for tracking
    '''
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
    
    # reset tracking status for all players for all subscribers
    update_tracking_status(None, None, False)

    # start processes. Each process will use its own cursor and db connection.
    # start process to monitor mentions
    mentions_process = multiprocessing.Process(target=check_mentions, args=(api, players, since_id,))
    mentions_process.start()

    # start another process to go through all subscribers
    check_subscriber_process = multiprocessing.Process(target=start_tracking, args=(api,))
    check_subscriber_process.start()

    # start another process to update fixture schedule once every week. Make sure to not update during games.
    # Use scheule library not sched. Update every Tuesday
    update_schedules_process = multiprocessing.Process(target=update_schedules)
    update_schedules_process.start()
    
    # tweets = tweepy.Cursor(api.search, 
    #                        q='"Marcos%20Alonso" OR @marcosalonso03',
    #                        lang="en",
    #                        since=date.today(),
    #                        tweet_mode='extended').items(100)

    # for tweet in tweets:
    #     if (not tweet.retweeted) and ('RT @' not in tweet.full_text) and tweet.in_reply_to_status_id is None:
    #         print(f'https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}', tweet.favorite_count, tweet.retweet_count)


if __name__ == "__main__":
    main()
